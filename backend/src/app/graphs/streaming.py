"""LangGraph stream output -> legacy SSE event adapters.

Both helpers yield plain ``dict`` events (the exact keys the frontend's ``parseSSE``
already understands). The route layers wrap them in the ``data: {json}\\n\\n`` envelope.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.domain.paper import paper_to_wire
from app.domain.pipeline import PipelineData


async def agent_stream_events(
    graph,
    initial: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> AsyncIterator[dict]:
    """Stream the agent graph as legacy agent event dicts.

    The graph nodes emit ``plan / thought / tool_call / tool_result / tool_error /
    final_answer / error`` via ``get_stream_writer``; we pass them through and append a
    trailing ``end`` event.

    ``config`` is forwarded to ``graph.astream`` — callers must pass a
    ``recursion_limit`` sized to ``max_steps`` (the LangGraph default of 25 is too
    small for long agent runs, which need roughly ``2 * max_steps`` supersteps).
    """
    try:
        async for event in graph.astream(initial, config=config, stream_mode="custom"):
            yield event
    except Exception as e:  # noqa: BLE001 - surface a terminal error event to the client
        yield {"type": "error", "error": str(e)}
    yield {"type": "end"}


async def pipeline_stream_events(
    graph,
    initial: dict[str, Any],
    *,
    stage_names: list[str],
) -> AsyncIterator[dict]:
    """Stream the pipeline graph as legacy pipeline event dicts.

    Emits ``start``, then ``stage_start`` / ``stage_complete`` (or ``error``) per
    stage, then a terminal ``complete`` carrying the accumulated result.
    """
    name_set = set(stage_names)
    total = len(stage_names)

    yield {
        "type": "start",
        "trace_id": initial.get("trace_id"),
        "query": initial.get("query"),
    }

    data: PipelineData | None = None
    results: list[dict[str, Any]] = []

    async for event in graph.astream_events(initial, version="v2"):
        kind = event.get("event")
        name = event.get("name")
        if name not in name_set:
            continue

        if kind == "on_chain_start":
            idx = stage_names.index(name)
            yield {
                "type": "stage_start",
                "stage": name,
                "stage_index": idx + 1,
                "total_stages": total,
                "progress": (idx / total) if total else 0,
            }
        elif kind == "on_chain_end":
            output = event.get("data", {}).get("output") or {}
            if isinstance(output.get("data"), PipelineData):
                data = output["data"]
            entry = (output.get("stage_results") or [{}])[0] if output.get("stage_results") else {}
            results.append(entry)

            idx = stage_names.index(name)
            stage_success = entry.get("success", True)
            if not stage_success:
                # Surface the failure, but never terminate the SSE stream here:
                # the terminal ``complete`` event below is the frontend's only
                # reliable stop signal. With stop_on_error the graph itself ends
                # after this stage; with continue-on-error later stages follow.
                yield {
                    "type": "error",
                    "stage": name,
                    "error": entry.get("error") or "stage failed",
                }
            yield {
                "type": "stage_complete",
                "stage": name,
                "stage_index": idx + 1,
                "total_stages": total,
                "progress": ((idx + 1) / total) if total else 0,
                "success": bool(stage_success),
                "duration_ms": round(entry.get("duration_ms") or 0, 2),
            }

    success = bool(results) and all(r.get("success", True) for r in results)
    papers = [paper_to_wire(p) for p in data.ranked] if data else []
    answer = data.verified.answer if data and data.verified else ""

    yield {
        "type": "complete",
        "success": success,
        "total_duration_ms": round(
            sum((r.get("duration_ms") or 0) for r in results), 2
        ),
        "answer": answer,
        "papers": papers,
        "stages": [
            {
                "name": r["name"],
                "success": r.get("success", True),
                "duration_ms": round(r.get("duration_ms") or 0, 2),
            }
            for r in results
        ],
    }

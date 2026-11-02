# M1 — Construction-Legal Citations（结构化引用契约）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every citation the survey stage emits *legal by construction* — claims are emitted as structured objects whose citation indices are members of the current evidence packet (D7), whose evidence spans verbatim-match the source (D9), and with exactly one bounded contract-repair attempt before deterministic projection/refusal.

**Architecture:** Survey generation stops returning free-form prose. It produces a `StructuredSurvey` (`claims[]` with 1..N citation indices + verbatim span anchors), validated by pure functions in a new `app/trust/` package. The LLM path uses the existing D1 client through `complete_structured`; the no-API-key path uses a deterministic offline template that is legal by construction. The rendered `Survey` (existing domain type) stays the wire format consumed by stages 7/8, the serializer, and the React frontend — SSE/API contracts do not change.

**Tech Stack:** Python 3.11 · Pydantic v2 · LangGraph 1.x (existing compiled pipeline) · the project's single OpenAI-compatible `LLMClient` via `app.llm.structured.complete_structured` · pytest-asyncio (`asyncio_mode=auto`). No new third-party dependencies.

**Spec:** `docs/research/2026-11-02-novel-design-angles.md` §2 claim **M1（引用合法化 by construction）**; red lines in §5 apply (no decoding-level guarantee claims — commercial D1 endpoints expose no logits; this plan implements an *output contract + deterministic projection/refusal*, which is exactly FullCite's "output-side" strategy and must be described that way in the thesis).

## Global Constraints

- Python 3.11, full type hints on every signature, module docstrings, functions over classes; logging only via `from app.core.logging import get_logger`; never `print`.
- **D1**: all model calls go through the existing `LLMClient`/`complete_structured`; stages accept `llm: LLMClient | None = None` and must run fully offline when it is `None` (matches `get_llm_client` returning `None` without an API key).
- **D2**: the contract-repair loop runs at most ONE additional model call. No unbounded retries.
- **D7**: only pre-numbered indices `[1..N]` of the current evidence packet may appear in output; **D9**: a span is stored only when it verbatim-matches source text.
- Tests: no network, Docker, CAT, or API keys. All LLM-dependent tests use a new `FakeLLMClient` (Task 4). pytest-asyncio is in auto mode — bare `async def test_...` needs no marker.
- Dependency discipline: add nothing to `pyproject.toml` (no numpy/scipy).
- Gates, run from repo root unless noted: `make test-unit`; `make lint`; `make typecheck`; and `cd backend && uv run ruff format --check src/ tests/`. The format baseline is red repo-wide on pristine HEAD — only assess files touched by the task (`uv run ruff format --check <touched files>`); do **not** run the mutating `ruff format` without the user's approval; fix formatting by hand.
- Commits are an explicit action: the plan ends each task at a green working tree; run `git add`/`git commit` (conventional type prefixes `feat`/`test`/`refactor`) only when the user asks.
- Honesty: keep the skeleton/disclaimer wording for offline output; describe this as 设计/契约层实现, never as logits-level constrained decoding.

## File Structure

```
backend/src/app/
  domain/
    evidence.py            # MODIFY: add char_start/char_end offsets
    claim.py               # CREATE: Claim, StructuredSurvey, ContractReport (+ findings)
    pipeline.py            # MODIFY: two new PipelineData fields
  trust/
    __init__.py            # CREATE
    spans.py               # CREATE: pure verbatim span locator (offset/substring)
    contract.py            # CREATE: pure citation-contract validator (D7/D9)
  survey/
    __init__.py            # CREATE
    packet.py              # CREATE: 1..N evidence packet + LLM prompt text
    template.py            # CREATE: offline deterministic legal survey
    render.py              # CREATE: StructuredSurvey -> existing Survey wire type
    generate.py            # CREATE: async generation + one bounded repair + projection
  pipeline/stages/
    stage5_evidence.py     # MODIFY: populate offsets on anchors
    stage6_survey.py       # MODIFY: use generate.generate_structured_survey; accept llm
  graphs/
    pipeline.py            # MODIFY: default_pipeline_stages(llm=None)
  api/v1/
    pipeline_routes.py     # MODIFY: pass injected llm into default_pipeline_stages
backend/tests/
  conftest.py              # MODIFY: add FakeLLMClient + fake_llm_client fixture
  unit/test_trust_spans.py       # CREATE
  unit/test_trust_contract.py    # CREATE
  unit/test_survey_packet.py     # CREATE
  unit/test_survey_template.py   # CREATE
  unit/test_survey_render.py     # CREATE
  unit/test_survey_generate.py   # CREATE
  unit/test_stage6_contract.py   # CREATE (graph-level integration)
```

---

### Task 1: Evidence span offsets on `EvidenceChunk`, populated by stage 5

**Files:**
- Modify: `backend/src/app/domain/evidence.py:14-25`
- Modify: `backend/src/app/pipeline/stages/stage5_evidence.py:39-59`
- Test: `backend/tests/unit/test_stage5_evidence.py` (CREATE; no such file exists yet)

**Interfaces:**
- Consumes: `EvidenceChunk(chunk_id, paper_id, record_id, section, content, anchor, verbatim, reason, created_at)`; stage 5 already builds `span = paper.abstract[:120]` and `anchor=span` with `verbatim=False` (content is the synthesized "Key finding" wrapper — that honesty marker must stay).
- Produces: `EvidenceChunk.char_start: int | None` and `char_end: int | None`; when set, `paper.abstract[char_start:char_end] == chunk.anchor`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_stage5_evidence.py`:

```python
"""Unit tests for stage 5 evidence extraction (D9 offset bookkeeping)."""
from __future__ import annotations

from app.domain.paper import Paper
from app.pipeline.stages.stage5_evidence import _extract_mock_evidence


def _paper(paper_id: str, abstract: str) -> Paper:
    return Paper(paper_id=paper_id, title=f"Title {paper_id}", abstract=abstract)


class TestMockEvidenceOffsets:
    def test_anchor_offsets_point_at_verbatim_abstract_slice(self):
        abstract = "A" * 50 + "Distinctive verbatim opening sentence." + "B" * 200
        chunks = _extract_mock_evidence([_paper("p1", abstract)])

        assert chunks
        first = chunks[0]
        assert first.char_start is not None and first.char_end is not None
        assert abstract[first.char_start:first.char_end] == first.anchor

    def test_missing_abstract_yields_none_offsets(self):
        chunks = _extract_mock_evidence([_paper("p2", "")])
        assert chunks
        assert all(chunk.char_start is None for chunk in chunks)

    def test_synthesized_content_still_marked_non_verbatim(self):
        chunks = _extract_mock_evidence([_paper("p3", "x" * 200)])
        assert all(chunk.verbatim is False for chunk in chunks)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_stage5_evidence.py -v`
Expected: FAIL — `AttributeError: ... 'EvidenceChunk' object has no attribute 'char_start'`.

- [ ] **Step 3: Add the fields to the domain model**

In `backend/src/app/domain/evidence.py`, add to `EvidenceChunk` after `reason`:

```python
    # Verbatim position of ``anchor`` inside the source text (the abstract for
    # now). None when the source was unavailable; consumers of D9 spans must
    # re-derive rather than trust an un-positioned anchor.
    char_start: int | None = None
    char_end: int | None = None
```

- [ ] **Step 4: Populate offsets in stage 5**

In `backend/src/app/pipeline/stages/stage5_evidence.py`, extend the chunk construction inside `_extract_mock_evidence`:

```python
        start = paper.abstract.find(span) if span else -1
        char_start = start if start >= 0 else None
        char_end = start + len(span) if start >= 0 else None
```

and pass `char_start=char_start, char_end=char_end` into the `EvidenceChunk(...)` call (leave `verbatim=False` untouched).

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_stage5_evidence.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Regression + gates**

Run: `make test-unit`, `make lint`, `make typecheck`, and `cd backend && uv run ruff format --check src/app/domain/evidence.py src/app/pipeline/stages/stage5_evidence.py tests/unit/test_stage5_evidence.py`.
Expected: all green; format check clean on the three touched files. Leave the tree green (commit only on explicit user request).

---

### Task 2: Claim domain types + pure verbatim span locator

**Files:**
- Create: `backend/src/app/domain/claim.py`
- Create: `backend/src/app/trust/__init__.py` (module docstring only)
- Create: `backend/src/app/trust/spans.py`
- Test: `backend/tests/unit/test_trust_spans.py`

**Interfaces:**
- Produces:
  - `domain/claim.py`: `Claim(claim_id: str, text: str, citation_indices: list[int] = [], span: SpanAnchor | None = None)`; `SpanAnchor(chunk_id: str, paper_id: str, text: str, char_start: int | None = None, char_end: int | None = None)`; `StructuredSurvey(claims: list[Claim] = [])`; finding code literal `FindingCode = Literal["empty_citations", "index_out_of_range", "unknown_chunk", "span_mismatch"]`; `ContractFinding(claim_id: str, code: FindingCode, detail: str)`; `ContractReport(first_pass_ok: bool, repaired: bool = False, findings: list[ContractFinding] = [])` with `@property ok(self) -> bool` returning `not self.findings`.
  - `trust/spans.py`: `@dataclass(frozen=True) class SpanLocation(ok: bool, char_start: int | None, char_end: int | None, method: Literal["offset", "substring", "none"])`) and `locate_span(source: str, span: str, char_start: int | None = None, char_end: int | None = None) -> SpanLocation`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_trust_spans.py`:

```python
"""Tests for the verbatim span locator (D9 by construction)."""
from __future__ import annotations

from app.trust.spans import locate_span


class TestLocateSpan:
    def test_exact_offsets_match(self):
        source = "prefix verbatim finding suffix"
        loc = locate_span(source, "verbatim finding", 7, 23)
        assert loc.ok and loc.method == "offset"
        assert source[loc.char_start:loc.char_end] == "verbatim finding"

    def test_wrong_offsets_fall_back_to_substring_projection(self):
        source = "prefix verbatim finding suffix"
        loc = locate_span(source, "verbatim finding", 0, 5)
        assert loc.ok and loc.method == "substring"
        assert loc.char_start == 7 and loc.char_end == 23

    def test_substring_without_offsets(self):
        source = "aaa needle zzz"
        loc = locate_span(source, "needle")
        assert loc.ok and loc.method == "substring"
        assert (loc.char_start, loc.char_end) == (4, 10)

    def test_edited_span_is_rejected(self):
        source = "the model improves retrieval by twelve percent"
        loc = locate_span(source, "the model improves retrieval by 12%")
        assert not loc.ok and loc.method == "none"
        assert loc.char_start is None and loc.char_end is None

    def test_empty_span_is_rejected(self):
        assert not locate_span("anything", "").ok
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_trust_spans.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.trust'`.

- [ ] **Step 3: Create the package, domain types, and locator**

`backend/src/app/trust/__init__.py`:

```python
"""Trust-by-construction primitives: citation contracts, spans, verification.

This package holds the deterministic mechanisms behind invariants D7-D9.
LLM-dependent orchestration lives in ``app.survey`` and the pipeline stages.
"""
```

`backend/src/app/trust/spans.py`:

```python
"""Verbatim span location against source text (D9).

A span is accepted only when its text occurs verbatim in the source. Authored
offsets are preferred; when absent or inconsistent, the deterministic
substring fallback *projects* correct offsets (an output-side guarantee, not
logits-level constrained decoding).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class SpanLocation:
    """Result of locating a span inside source text."""

    ok: bool
    char_start: int | None
    char_end: int | None
    method: Literal["offset", "substring", "none"]


def locate_span(
    source: str,
    span: str,
    char_start: int | None = None,
    char_end: int | None = None,
) -> SpanLocation:
    """Locate ``span`` verbatim inside ``source``.

    Order: exact authored offsets first, then substring projection. An empty
    span or no verbatim occurrence yields ``ok=False``.
    """
    if not span:
        return SpanLocation(False, None, None, "none")
    if (
        char_start is not None
        and char_end is not None
        and 0 <= char_start <= char_end <= len(source)
        and source[char_start:char_end] == span
    ):
        return SpanLocation(True, char_start, char_end, "offset")
    found = source.find(span)
    if found >= 0:
        return SpanLocation(True, found, found + len(span), "substring")
    return SpanLocation(False, None, None, "none")
```

`backend/src/app/domain/claim.py`:

```python
"""Structured claim/citation contract emitted by survey generation (M1).

A survey is a sequence of claims. Each claim cites only pre-numbered evidence
indices (D7) and may anchor itself to one verbatim source span (D9). The
contract is validated by ``app.trust.contract`` before the survey is rendered
to the wire-level ``Survey`` type.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

FindingCode = Literal[
    "empty_citations", "index_out_of_range", "unknown_chunk", "span_mismatch"
]


class SpanAnchor(BaseModel):
    """A verbatim span inside one evidence chunk."""

    chunk_id: str
    paper_id: str
    text: str
    char_start: int | None = None
    char_end: int | None = None


class Claim(BaseModel):
    """One survey statement with its pre-numbered evidence citations."""

    claim_id: str
    text: str = Field(min_length=1)
    citation_indices: list[int] = Field(default_factory=list)
    span: SpanAnchor | None = None


class StructuredSurvey(BaseModel):
    """The structured intermediate representation of a survey answer."""

    claims: list[Claim] = Field(default_factory=list)


class ContractFinding(BaseModel):
    """A single citation-contract violation on one claim."""

    claim_id: str
    code: FindingCode
    detail: str


class ContractReport(BaseModel):
    """Outcome of validating a structured survey against its evidence packet."""

    first_pass_ok: bool
    repaired: bool = False
    findings: list[ContractFinding] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when no violation remains."""
        return not self.findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_trust_spans.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Gates**

Run: `make test-unit`, `make lint`, `make typecheck`, and format-check the touched files.
Expected: green.

---

### Task 3: Pure citation-contract validator (D7 indices + D9 spans)

**Files:**
- Create: `backend/src/app/trust/contract.py`
- Test: `backend/tests/unit/test_trust_contract.py`

**Interfaces:**
- Consumes: `StructuredSurvey`, `Claim`, `ContractReport`, `ContractFinding`, `FindingCode` from `app.domain.claim`; `EvidenceChunk` from `app.domain.evidence`; `locate_span` from `app.trust.spans`.
- Produces:
  - `build_packet(evidence: list[EvidenceChunk]) -> dict[int, EvidenceChunk]` — 1-based map, packet size `N = len(evidence)`.
  - `validate_claim(claim: Claim, packet: dict[int, EvidenceChunk]) -> list[ContractFinding]`.
  - `validate_survey(survey: StructuredSurvey, evidence: list[EvidenceChunk]) -> ContractReport` — sets `first_pass_ok` to the result; never sets `repaired` (callers do).
  - `legal_claims(survey: StructuredSurvey, report: ContractReport) -> StructuredSurvey` — keeps only claims with zero findings (deterministic projection used after the one failed repair).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_trust_contract.py`:

```python
"""Tests for the citation contract validator (D7 + D9)."""
from __future__ import annotations

from app.domain.claim import Claim, SpanAnchor, StructuredSurvey
from app.domain.evidence import EvidenceChunk
from app.trust.contract import build_packet, legal_claims, validate_survey


def _chunk(chunk_id: str, paper_id: str, anchor: str) -> EvidenceChunk:
    start = 3
    return EvidenceChunk(
        chunk_id=chunk_id,
        paper_id=paper_id,
        content=f"Key finding: {anchor}",
        anchor=anchor,
        verbatim=False,
        char_start=start,
        char_end=start + len(anchor),
    )


ANCHOR1 = "verbatim finding one"
ANCHOR2 = "verbatim finding two"


def _evidence() -> list[EvidenceChunk]:
    source_prefix = "abc"
    return [
        _chunk("ev1", "p1", ANCHOR1),  # source abstract would start "abcverbatim..."
        _chunk("ev2", "p2", ANCHOR2),
    ]


class TestBuildPacket:
    def test_packet_is_one_based(self):
        packet = build_packet(_evidence())
        assert sorted(packet) == [1, 2]
        assert packet[1].chunk_id == "ev1"


class TestValidateSurvey:
    def test_legal_survey_passes(self):
        survey = StructuredSurvey(claims=[
            Claim(claim_id="c1", text="first", citation_indices=[1],
                  span=SpanAnchor(chunk_id="ev1", paper_id="p1", text=ANCHOR1,
                                  char_start=3, char_end=3 + len(ANCHOR1))),
        ])
        report = validate_survey(survey, _evidence())
        assert report.ok and report.first_pass_ok

    def test_out_of_range_index_is_a_finding(self):
        survey = StructuredSurvey(claims=[
            Claim(claim_id="c1", text="ghost citation", citation_indices=[3]),
        ])
        report = validate_survey(survey, _evidence())
        assert not report.ok
        assert report.findings[0].code == "index_out_of_range"

    def test_zero_or_negative_index_is_out_of_range(self):
        survey = StructuredSurvey(claims=[
            Claim(claim_id="c1", text="bad", citation_indices=[0, -1]),
        ])
        report = validate_survey(survey, _evidence())
        codes = {f.code for f in report.findings}
        assert codes == {"index_out_of_range"}

    def test_uncited_claim_is_empty_citations(self):
        survey = StructuredSurvey(claims=[
            Claim(claim_id="c1", text="unsupported assertion", citation_indices=[]),
        ])
        report = validate_survey(survey, _evidence())
        assert report.findings[0].code == "empty_citations"

    def test_span_against_unknown_chunk(self):
        survey = StructuredSurvey(claims=[
            Claim(claim_id="c1", text="x", citation_indices=[1],
                  span=SpanAnchor(chunk_id="ghost", paper_id="p1", text=ANCHOR1)),
        ])
        report = validate_survey(survey, _evidence())
        assert any(f.code == "unknown_chunk" for f in report.findings)

    def test_span_paper_id_mismatch_is_unknown_chunk(self):
        survey = StructuredSurvey(claims=[
            Claim(claim_id="c1", text="x", citation_indices=[1],
                  span=SpanAnchor(chunk_id="ev1", paper_id="OTHER", text=ANCHOR1)),
        ])
        report = validate_survey(survey, _evidence())
        assert any(f.code == "unknown_chunk" for f in report.findings)

    def test_edited_span_text_is_span_mismatch(self):
        survey = StructuredSurvey(claims=[
            Claim(claim_id="c1", text="x", citation_indices=[1],
                  span=SpanAnchor(chunk_id="ev1", paper_id="p1",
                                  text="verbatim finding ONE EDITED")),
        ])
        report = validate_survey(survey, _evidence())
        assert any(f.code == "span_mismatch" for f in report.findings)

    def test_legal_claims_projection_drops_only_offending_claims(self):
        survey = StructuredSurvey(claims=[
            Claim(claim_id="c1", text="good", citation_indices=[1]),
            Claim(claim_id="c2", text="bad", citation_indices=[9]),
        ])
        report = validate_survey(survey, _evidence())
        projected = legal_claims(survey, report)
        assert [c.claim_id for c in projected.claims] == ["c1"]
```

Note the test evidence: chunk 1's `anchor` lives at offsets (3, 3+len) of a notional abstract; the validator locates spans against the chunk's **`anchor` text itself** (the stored verbatim slice), so `locate_span(chunk.anchor, span.text, ...)` is the D9 check in this task.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_trust_contract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.trust.contract'`.

- [ ] **Step 3: Implement the validator**

`backend/src/app/trust/contract.py`:

```python
"""Citation contract validation: legal indices (D7) and verbatim spans (D9)."""
from __future__ import annotations

from app.domain.claim import (
    Claim,
    ContractFinding,
    ContractReport,
    StructuredSurvey,
)
from app.domain.evidence import EvidenceChunk
from app.trust.spans import locate_span


def build_packet(evidence: list[EvidenceChunk]) -> dict[int, EvidenceChunk]:
    """Build the 1-based evidence packet map ``{1..N: chunk}`` (D7)."""
    return {i: chunk for i, chunk in enumerate(evidence, start=1)}


def validate_claim(
    claim: Claim, packet: dict[int, EvidenceChunk]
) -> list[ContractFinding]:
    """Return all contract violations on a single claim."""
    findings: list[ContractFinding] = []

    if not claim.citation_indices:
        findings.append(
            ContractFinding(
                claim_id=claim.claim_id,
                code="empty_citations",
                detail="claim carries no pre-numbered citation",
            )
        )

    for index in claim.citation_indices:
        if not 1 <= index <= len(packet):
            findings.append(
                ContractFinding(
                    claim_id=claim.claim_id,
                    code="index_out_of_range",
                    detail=f"citation index {index} is outside packet [1..{len(packet)}]",
                )
            )

    span = claim.span
    if span is not None:
        chunk = next(
            (c for c in packet.values() if c.chunk_id == span.chunk_id),
            None,
        )
        if chunk is None or chunk.paper_id != span.paper_id:
            findings.append(
                ContractFinding(
                    claim_id=claim.claim_id,
                    code="unknown_chunk",
                    detail=f"span source chunk {span.chunk_id!r}/{span.paper_id!r} "
                    "is not in the evidence packet",
                )
            )
        else:
            location = locate_span(
                chunk.anchor, span.text, span.char_start, span.char_end
            )
            if not location.ok:
                findings.append(
                    ContractFinding(
                        claim_id=claim.claim_id,
                        code="span_mismatch",
                        detail="span text does not verbatim-match its source anchor",
                    )
                )

    return findings


def validate_survey(
    survey: StructuredSurvey, evidence: list[EvidenceChunk]
) -> ContractReport:
    """Validate every claim against the evidence packet."""
    packet = build_packet(evidence)
    findings = [
        finding
        for claim in survey.claims
        for finding in validate_claim(claim, packet)
    ]
    return ContractReport(first_pass_ok=not findings, findings=findings)


def legal_claims(
    survey: StructuredSurvey, report: ContractReport
) -> StructuredSurvey:
    """Deterministic projection: keep claims that have no findings."""
    offending = {finding.claim_id for finding in report.findings}
    return StructuredSurvey(
        claims=[c for c in survey.claims if c.claim_id not in offending]
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_trust_contract.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Gates**

Run: `make test-unit`, `make lint`, `make typecheck`, format-check touched files.
Expected: green.

---

### Task 4: `FakeLLMClient` test double + evidence packet prompt

**Files:**
- Modify: `backend/tests/conftest.py` (append after `raising_chat_model`)
- Create: `backend/src/app/survey/__init__.py`
- Create: `backend/src/app/survey/packet.py`
- Test: `backend/tests/unit/test_survey_packet.py`

**Interfaces:**
- Consumes: `ChatResult`, `Usage` from `app.llm.base` (fields: `ChatResult(content="", model="", usage=Usage(), tool_calls=[], finish_reason="stop", raw={})`; `Usage(prompt_tokens, completion_tokens, total_tokens)`); `EvidenceChunk`; `Paper`.
- Produces:
  - conftest: class `FakeLLMClient(responses: list[str] | None = None, error: Exception | None = None)` with `calls: list[list[ChatMessage]]`, async `chat(...) -> ChatResult` matching the `LLMClient` protocol, async `close() -> None`; fixture `fake_llm_client` (factory).
  - `survey/packet.py`: `PacketEntry(index: int, chunk_id: str, paper_id: str, paper_title: str, anchor: str)`; `build_evidence_packet(evidence: list[EvidenceChunk], papers: list[Paper]) -> list[PacketEntry]` (index by evidence order; paper looked up by id, title `""` if absent); `build_survey_prompt(contract_topic: str, packet: list[PacketEntry]) -> str` (enumerates entries and states the D7/D9 rules).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_survey_packet.py`:

```python
"""Tests for the numbered evidence packet and survey prompt."""
from __future__ import annotations

from app.domain.evidence import EvidenceChunk
from app.domain.paper import Paper
from app.survey.packet import build_evidence_packet, build_survey_prompt


def _paper(paper_id: str, title: str) -> Paper:
    return Paper(paper_id=paper_id, title=title, abstract="")


def _chunk(chunk_id: str, paper_id: str, anchor: str) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_id=chunk_id, paper_id=paper_id, content=anchor, anchor=anchor
    )


class TestEvidencePacket:
    def test_entries_are_numbered_from_one_with_paper_titles(self):
        packet = build_evidence_packet(
            [_chunk("ev1", "p1", "span one"), _chunk("ev2", "p2", "span two")],
            [_paper("p1", "First Paper"), _paper("p2", "Second Paper")],
        )
        assert [(e.index, e.chunk_id, e.paper_title) for e in packet] == [
            (1, "ev1", "First Paper"),
            (2, "ev2", "Second Paper"),
        ]

    def test_missing_paper_title_is_empty_string(self):
        packet = build_evidence_packet([_chunk("ev1", "pX", "span")], [])
        assert packet[0].paper_title == ""

    def test_prompt_lists_indices_and_states_contract_rules(self):
        packet = build_evidence_packet(
            [_chunk("ev1", "p1", "span one")], [_paper("p1", "T")]
        )
        prompt = build_survey_prompt("retrieval augmented generation", packet)
        assert "[1]" in prompt
        assert "span one" in prompt
        assert "retrieval augmented generation" in prompt
        # D7 rule must be visible to the model.
        assert "1" in prompt and "citation_indices" in prompt


class TestFakeLLMClient:
    async def test_returns_scripted_json_and_records_calls(self, fake_llm_client):
        client = fake_llm_client(['{"ok": true}'])
        result = await client.chat(
            [{"role": "user", "content": "hi"}], response_format={"type": "json_object"}
        )
        assert result.content == '{"ok": true}'
        assert len(client.calls) == 1

    async def test_last_response_repeats(self, fake_llm_client):
        client = fake_llm_client(['{"a": 1}', '{"a": 2}'])
        first = await client.chat([])
        second = await client.chat([])
        third = await client.chat([])
        assert [r.content for r in (first, second, third)] == [
            '{"a": 1}', '{"a": 2}', '{"a": 2}'
        ]

    async def test_error_double_raises(self, fake_llm_client):
        import pytest

        client = fake_llm_client(error=RuntimeError("LLM boom"))
        with pytest.raises(RuntimeError, match="LLM boom"):
            await client.chat([])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_survey_packet.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.survey'` and missing fixture `fake_llm_client`.

- [ ] **Step 3: Add the fake and implement the packet module**

Append to `backend/tests/conftest.py`:

```python
from app.llm.base import ChatResult, Usage  # add with the existing top imports


class FakeLLMClient:
    """Deterministic double for the D1 ``LLMClient`` protocol.

    Each ``chat`` call consumes the next scripted JSON string; the last one is
    reused for extra calls. Pass ``error=`` to simulate provider failures.
    """

    def __init__(
        self,
        responses: list[str] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._responses = list(responses or [])
        self._error = error
        self.calls: list[list[Any]] = []

    async def chat(
        self,
        messages: list[Any],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[Any] | None = None,
        response_format: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> ChatResult:
        self.calls.append(list(messages))
        if self._error is not None:
            raise self._error
        if self._responses:
            idx = min(len(self.calls) - 1, len(self._responses) - 1)
            content = self._responses[idx]
        else:
            content = "{}"
        return ChatResult(content=content, model="fake", usage=Usage(0, 0, 0))

    async def close(self) -> None:
        return None
```

and near the other fixtures:

```python
@pytest.fixture
def fake_llm_client():
    """Factory fixture: ``client = fake_llm_client(['{...json...}'])``."""

    def _make(
        responses: list[str] | None = None, error: Exception | None = None
    ) -> FakeLLMClient:
        return FakeLLMClient(responses, error)

    return _make
```

`backend/src/app/survey/__init__.py`:

```python
"""Survey generation: structured claims, offline template, rendering."""
```

`backend/src/app/survey/packet.py`:

```python
"""Numbered evidence packet handed to survey generation (D7 numbering)."""
from __future__ import annotations

from pydantic import BaseModel

from app.domain.evidence import EvidenceChunk
from app.domain.paper import Paper


class PacketEntry(BaseModel):
    """One evidence item, as presented to the generator."""

    index: int
    chunk_id: str
    paper_id: str
    paper_title: str
    anchor: str


def build_evidence_packet(
    evidence: list[EvidenceChunk], papers: list[Paper]
) -> list[PacketEntry]:
    """Number evidence chunks 1..N in extraction order."""
    titles = {paper.paper_id: paper.title for paper in papers}
    return [
        PacketEntry(
            index=i,
            chunk_id=chunk.chunk_id,
            paper_id=chunk.paper_id,
            paper_title=titles.get(chunk.paper_id, ""),
            anchor=chunk.anchor,
        )
        for i, chunk in enumerate(evidence, start=1)
    ]


def build_survey_prompt(topic: str, packet: list[PacketEntry]) -> str:
    """Render the user prompt containing the numbered evidence packet."""
    lines = [
        f"Research topic: {topic}",
        "",
        "Evidence packet (cite ONLY these pre-numbered indices in "
        "citation_indices; span_text must be copied verbatim from an anchor, "
        "or be null):",
    ]
    for entry in packet:
        title = f" — {entry.paper_title}" if entry.paper_title else ""
        lines.append(f"[{entry.index}] (chunk_id={entry.chunk_id}, "
                     f"paper_id={entry.paper_id}{title}): {entry.anchor}")
    lines.append("")
    lines.append(
        'Return JSON: {"claims": [{"text": str, "citation_indices": [int], '
        '"chunk_id": str|null, "span_text": str|null}]}'
    )
    return "\n".join(lines)
```

Also add the module-level system prompt constant used by Task 5, in the same file:

```python
SURVEY_SYSTEM_PROMPT = (
    "You are a meticulous academic survey writer. Every claim must carry at "
    "least one citation index from the supplied evidence packet. Never invent "
    "indices. When quoting evidence, copy its text verbatim. If the evidence "
    "is insufficient, return an empty claims list."
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_survey_packet.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Gates**

Run: `make test-unit`, `make lint`, `make typecheck`, format-check touched files.
Expected: green.

---

### Task 5: Offline template survey + renderer

**Files:**
- Create: `backend/src/app/survey/template.py`
- Create: `backend/src/app/survey/render.py`
- Test: `backend/tests/unit/test_survey_template.py`
- Test: `backend/tests/unit/test_survey_render.py`

**Interfaces:**
- Consumes: `build_evidence_packet` (`app.survey.packet`); `StructuredSurvey`, `Claim`, `SpanAnchor` (`app.domain.claim`); `locate_span` (`app.trust.spans`); `Survey`, `Citation` (`app.domain.survey`); `QueryContract` (`app.domain.contract`, fields `topic: str`, `intent: Intent`); `EvidenceChunk`, `Paper`.
- Produces:
  - `template_structured_survey(topic: str, evidence: list[EvidenceChunk], papers: list[Paper], *, max_claims: int = 5) -> StructuredSurvey` — one claim per packet entry (up to `max_claims`); claim text is the verbatim anchor quoted; `claim_id="claim_{i}"`; `citation_indices=[i]`; span projected via `locate_span(chunk.anchor, chunk.anchor, chunk.char_start, chunk.char_end)` (offsets carried over when present). Empty evidence → empty survey.
  - `render_survey(structured: StructuredSurvey, evidence: list[EvidenceChunk]) -> Survey` — citations for the sorted union of indices used (each `Citation(index=i, paper_id=chunk.paper_id, chunk_id=chunk.chunk_id)`); answer lists claims as `1. {text} [i]`; when there are no legal claims, answer is the abstention string `ABSTENTION_NOTICE`; always appends the existing skeleton disclaimer block (verbatim, to preserve honesty):
    ```
    ---
    *This is a skeleton/demo response generated from mock data. In production, this would be an LLM-generated answer grounded in real paper content.*
    ```
  - `ABSTENTION_NOTICE: str = "_No evidence-supported statement could be produced; the claim was withheld (引用契约校验失败)._"`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/test_survey_template.py`:

```python
"""Tests for the offline deterministic survey template (legal by construction)."""
from __future__ import annotations

from app.domain.evidence import EvidenceChunk
from app.domain.paper import Paper
from app.survey.template import template_structured_survey
from app.trust.contract import validate_survey


def _fixtures():
    anchor = "verbatim anchor text"
    chunks = [
        EvidenceChunk(
            chunk_id="ev1", paper_id="p1", content=f"Key finding: {anchor}",
            anchor=anchor, verbatim=False, char_start=0, char_end=len(anchor),
        )
    ]
    papers = [Paper(paper_id="p1", title="T", abstract=anchor)]
    return anchor, chunks, papers


class TestTemplateSurvey:
    def test_every_claim_is_contract_legal(self):
        _, chunks, papers = _fixtures()
        survey = template_structured_survey("topic", chunks, papers)
        report = validate_survey(survey, chunks)
        assert report.ok
        claim = survey.claims[0]
        assert claim.citation_indices == [1]
        assert claim.span is not None and claim.span.text == "verbatim anchor text"

    def test_empty_evidence_yields_empty_survey(self):
        survey = template_structured_survey("topic", [], [])
        assert survey.claims == []

    def test_respects_max_claims(self):
        chunks = [
            EvidenceChunk(chunk_id=f"ev{i}", paper_id=f"p{i}", content="a" * 30,
                          anchor="a" * 30)
            for i in range(1, 7)
        ]
        survey = template_structured_survey("t", chunks, [], max_claims=3)
        assert len(survey.claims) == 3
```

Create `backend/tests/unit/test_survey_render.py`:

```python
"""Tests for StructuredSurvey -> Survey rendering (wire format preserved)."""
from __future__ import annotations

from app.domain.claim import Claim, SpanAnchor, StructuredSurvey
from app.domain.evidence import EvidenceChunk
from app.survey.render import ABSTENTION_NOTICE, render_survey


def _chunk(chunk_id: str, paper_id: str) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_id=chunk_id, paper_id=paper_id, content="anchor", anchor="anchor"
    )


class TestRenderSurvey:
    def test_citations_are_union_of_used_indices_sorted(self):
        structured = StructuredSurvey(claims=[
            Claim(claim_id="c1", text="second first", citation_indices=[2]),
            Claim(claim_id="c2", text="both", citation_indices=[1, 2]),
        ])
        survey = render_survey(structured, [_chunk("ev1", "p1"), _chunk("ev2", "p2")])
        assert [(c.index, c.paper_id, c.chunk_id) for c in survey.citations] == [
            (1, "p1", "ev1"),
            (2, "p2", "ev2"),
        ]
        assert "[2]" in survey.answer and "[1, 2]" in survey.answer

    def test_claim_lines_are_numbered(self):
        structured = StructuredSurvey(claims=[
            Claim(claim_id="c1", text="only", citation_indices=[1]),
        ])
        survey = render_survey(structured, [_chunk("ev1", "p1")])
        assert "1. only [1]" in survey.answer

    def test_empty_survey_renders_abstention_notice(self):
        survey = render_survey(StructuredSurvey(claims=[]), [_chunk("ev1", "p1")])
        assert survey.citations == []
        assert ABSTENTION_NOTICE in survey.answer

    def test_disclaimer_is_kept(self):
        survey = render_survey(
            StructuredSurvey(claims=[
                Claim(claim_id="c1", text="x", citation_indices=[1]),
            ]),
            [_chunk("ev1", "p1")],
        )
        assert "skeleton/demo response" in survey.answer
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/test_survey_template.py tests/unit/test_survey_render.py -v`
Expected: FAIL — modules do not exist.

- [ ] **Step 3: Implement template and renderer**

`backend/src/app/survey/template.py`:

```python
"""Deterministic offline survey: produces a contract-legal StructuredSurvey.

Used when no D1 LLM client is configured. One claim per evidence item; the
claim text quotes the verbatim anchor, so D7/D9 hold by construction.
"""
from __future__ import annotations

from app.domain.claim import Claim, SpanAnchor, StructuredSurvey
from app.domain.evidence import EvidenceChunk
from app.domain.paper import Paper
from app.survey.packet import build_evidence_packet
from app.trust.spans import locate_span


def template_structured_survey(
    topic: str,
    evidence: list[EvidenceChunk],
    papers: list[Paper],
    *,
    max_claims: int = 5,
) -> StructuredSurvey:
    """Build the offline structured survey from the evidence packet."""
    claims: list[Claim] = []
    for entry in build_evidence_packet(evidence, papers)[:max_claims]:
        chunk = evidence[entry.index - 1]
        location = locate_span(
            chunk.anchor, chunk.anchor, chunk.char_start, chunk.char_end
        )
        span = SpanAnchor(
            chunk_id=chunk.chunk_id,
            paper_id=chunk.paper_id,
            text=chunk.anchor,
            char_start=location.char_start,
            char_end=location.char_end,
        )
        claims.append(
            Claim(
                claim_id=f"claim_{entry.index}",
                text=f'"{chunk.anchor}"',
                citation_indices=[entry.index],
                span=span,
            )
        )
    return StructuredSurvey(claims=claims)
```

`backend/src/app/survey/render.py`:

```python
"""Render a validated StructuredSurvey to the existing wire Survey type."""
from __future__ import annotations

from app.domain.claim import StructuredSurvey
from app.domain.evidence import EvidenceChunk
from app.domain.survey import Citation, Survey
from app.trust.contract import build_packet

ABSTENTION_NOTICE = (
    "_No evidence-supported statement could be produced; the claim was "
    "withheld (引用契约校验失败)._"
)

_DISCLAIMER = (
    "\n\n---\n"
    "*This is a skeleton/demo response generated from mock data. "
    "In production, this would be an LLM-generated answer grounded in real "
    "paper content.*"
)


def render_survey(
    structured: StructuredSurvey, evidence: list[EvidenceChunk]
) -> Survey:
    """Render claims to numbered lines + pre-numbered citations (D7)."""
    packet = build_packet(evidence)
    used = sorted({i for claim in structured.claims for i in claim.citation_indices})
    citations = [
        Citation(
            index=i,
            paper_id=packet[i].paper_id,
            chunk_id=packet[i].chunk_id,
        )
        for i in used
        if i in packet
    ]

    if not structured.claims:
        return Survey(answer=ABSTENTION_NOTICE + _DISCLAIMER, citations=[])

    lines = [
        f"{n}. {claim.text} [{', '.join(str(i) for i in claim.citation_indices)}]"
        for n, claim in enumerate(structured.claims, start=1)
    ]
    return Survey(answer="\n".join(lines) + _DISCLAIMER, citations=citations)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_survey_template.py tests/unit/test_survey_render.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Gates**

Run: `make test-unit`, `make lint`, `make typecheck`, format-check touched files.
Expected: green.

---

### Task 6: Generator — structured LLM call, one bounded repair, projection/refusal

**Files:**
- Create: `backend/src/app/survey/generate.py`
- Test: `backend/tests/unit/test_survey_generate.py`

**Interfaces:**
- Consumes: `LLMClient` from `app.llm.base`; `complete_structured(client, system_prompt, user_prompt, output_model, *, max_retries=1, **chat_kwargs) -> tuple[T, ChatResult]` from `app.llm.structured`; `LLMValidationError` from `app.core.exceptions`; `build_evidence_packet`, `build_survey_prompt`, `SURVEY_SYSTEM_PROMPT`; `template_structured_survey`; `validate_survey`, `legal_claims`; `locate_span`; domain types.
- Produces:
  - In `generate.py`: `class ClaimDraft(BaseModel)` (`text: str = Field(min_length=1)`, `citation_indices: list[int] = []`, `chunk_id: str | None = None`, `span_text: str | None = None`); `class ClaimDraftList(BaseModel)` (`claims: list[ClaimDraft]`); `project_draft(draft: ClaimDraftList, evidence: list[EvidenceChunk]) -> StructuredSurvey` (claim ids `claim_{n}`; each `span_text` is located against its chunk's anchor — projected offsets, dropped to `span=None` when not verbatim-found or chunk unknown); async `generate_structured_survey(*, client: LLMClient | None, topic: str, evidence: list[EvidenceChunk], papers: list[Paper]) -> tuple[StructuredSurvey, ContractReport]`.
  - Behavior:
    1. `client is None` → `template_structured_survey(...)`, validate, `first_pass_ok` set from validation.
    2. Otherwise one `complete_structured` call; project; validate.
    3. If findings exist: exactly ONE repair call whose user prompt appends a JSON list of `{claim_id, code, detail}` and the instruction to return corrected claims; project + validate, mark `repaired=True`.
    4. If findings remain: project to `legal_claims`; report retains the second-pass findings (so metrics see what was dropped); the returned survey contains only legal claims.
    5. If the model call raises `LLMValidationError` (or any `Exception` from the client), log a warning and fall back to the offline template (run must not fail); the returned report is the template's validation report with `first_pass_ok=True` only if it validates.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_survey_generate.py`:

```python
"""Tests for structured survey generation with bounded repair (M1, D2)."""
from __future__ import annotations

import json

from app.core.exceptions import LLMValidationError
from app.domain.evidence import EvidenceChunk
from app.domain.paper import Paper
from app.survey.generate import generate_structured_survey
from app.trust.contract import validate_survey


def _evidence_papers():
    a1 = "verbatim finding alpha about retrieval"
    a2 = "verbatim finding beta about reranking"
    evidence = [
        EvidenceChunk(chunk_id="ev1", paper_id="p1", content=a1, anchor=a1,
                      char_start=0, char_end=len(a1)),
        EvidenceChunk(chunk_id="ev2", paper_id="p2", content=a2, anchor=a2,
                      char_start=0, char_end=len(a2)),
    ]
    papers = [
        Paper(paper_id="p1", title="Alpha", abstract=a1),
        Paper(paper_id="p2", title="Beta", abstract=a2),
    ]
    return evidence, papers


class TestOffline:
    async def test_none_client_uses_legal_template(self):
        evidence, papers = _evidence_papers()
        survey, report = await generate_structured_survey(
            client=None, topic="t", evidence=evidence, papers=papers
        )
        assert report.ok and len(survey.claims) == 2


class TestLLMPath:
    async def test_first_pass_legal_makes_no_repair_call(self, fake_llm_client):
        evidence, papers = _evidence_papers()
        payload = {"claims": [
            {"text": "alpha claim", "citation_indices": [1],
             "chunk_id": "ev1", "span_text": evidence[0].anchor},
        ]}
        client = fake_llm_client([json.dumps(payload)])

        survey, report = await generate_structured_survey(
            client=client, topic="t", evidence=evidence, papers=papers
        )

        assert report.ok and report.first_pass_ok and not report.repaired
        assert len(client.calls) == 1
        assert survey.claims[0].span is not None
        assert survey.claims[0].span.char_start == 0

    async def test_illegal_index_triggers_one_repair_then_accepts(
        self, fake_llm_client
    ):
        evidence, papers = _evidence_papers()
        bad = {"claims": [
            {"text": "bad", "citation_indices": [7], "chunk_id": None,
             "span_text": None},
        ]}
        good = {"claims": [
            {"text": "fixed", "citation_indices": [1],
             "chunk_id": "ev1", "span_text": evidence[0].anchor},
        ]}
        client = fake_llm_client([json.dumps(bad), json.dumps(good)])

        survey, report = await generate_structured_survey(
            client=client, topic="t", evidence=evidence, papers=papers
        )

        assert report.ok and report.repaired
        assert [c.text for c in survey.claims] == ["fixed"]
        assert len(client.calls) == 2  # exactly one repair, never more

    async def test_repeatedly_illegal_output_is_projected_to_legal_claims(
        self, fake_llm_client
    ):
        evidence, papers = _evidence_papers()
        bad = {"claims": [
            {"text": "good claim", "citation_indices": [1],
             "chunk_id": "ev1", "span_text": evidence[0].anchor},
            {"text": "fabricated", "citation_indices": [9],
             "chunk_id": None, "span_text": None},
        ]}
        # Repair repeats the same illegal draft: last scripted response repeats.
        client = fake_llm_client([json.dumps(bad)])

        survey, report = await generate_structured_survey(
            client=client, topic="t", evidence=evidence, papers=papers
        )

        assert [c.text for c in survey.claims] == ["good claim"]
        assert report.repaired
        assert any(f.code == "index_out_of_range" for f in report.findings)
        assert validate_survey(survey, evidence).ok

    async def test_project_draft_drops_unverifiable_span_silently(
        self, fake_llm_client
    ):
        # An edited span is NOT itself a contract violation (the claim still
        # cites a legal index); projection silently drops the span anchor, so
        # no repair call is spent.
        evidence, papers = _evidence_papers()
        payload = {"claims": [
            {"text": "claim", "citation_indices": [1],
             "chunk_id": "ev1", "span_text": "this text never appears verbatim"},
        ]}
        client = fake_llm_client([json.dumps(payload)])

        survey, report = await generate_structured_survey(
            client=client, topic="t", evidence=evidence, papers=papers
        )
        assert report.ok and not report.repaired
        assert len(client.calls) == 1
        assert survey.claims[0].span is None

    async def test_llm_validation_error_falls_back_to_template(
        self, fake_llm_client
    ):
        evidence, papers = _evidence_papers()
        client = fake_llm_client(error=LLMValidationError("bad json"))

        survey, report = await generate_structured_survey(
            client=client, topic="t", evidence=evidence, papers=papers
        )
        assert report.ok
        assert {c.citation_indices[0] for c in survey.claims} == {1, 2}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_survey_generate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.survey.generate'`.

- [ ] **Step 3: Implement the generator**

`backend/src/app/survey/generate.py`:

```python
"""Structured survey generation with one bounded contract-repair pass (D2)."""
from __future__ import annotations

import json

from pydantic import BaseModel, Field

from app.core.exceptions import LLMValidationError
from app.core.logging import get_logger
from app.domain.claim import (
    Claim,
    ContractReport,
    SpanAnchor,
    StructuredSurvey,
)
from app.domain.evidence import EvidenceChunk
from app.domain.paper import Paper
from app.llm.base import LLMClient
from app.llm.structured import complete_structured
from app.survey.packet import (
    SURVEY_SYSTEM_PROMPT,
    build_evidence_packet,
    build_survey_prompt,
)
from app.survey.template import template_structured_survey
from app.trust.contract import legal_claims, validate_survey
from app.trust.spans import locate_span

logger = get_logger(__name__)


class ClaimDraft(BaseModel):
    """One claim as emitted by the structured model call."""

    text: str = Field(min_length=1)
    citation_indices: list[int] = Field(default_factory=list)
    chunk_id: str | None = None
    span_text: str | None = None


class ClaimDraftList(BaseModel):
    """Structured output envelope for survey generation."""

    claims: list[ClaimDraft] = Field(default_factory=list)


def project_draft(
    draft: ClaimDraftList,
    evidence: list[EvidenceChunk],
) -> StructuredSurvey:
    """Project a model draft onto legal span anchors (deterministic)."""
    chunks_by_id = {chunk.chunk_id: chunk for chunk in evidence}
    claims: list[Claim] = []
    for n, item in enumerate(draft.claims, start=1):
        span: SpanAnchor | None = None
        chunk = chunks_by_id.get(item.chunk_id) if item.chunk_id else None
        if chunk is not None and item.span_text:
            location = locate_span(
                chunk.anchor,
                item.span_text,
                chunk.char_start,
                chunk.char_end,
            )
            if location.ok:
                span = SpanAnchor(
                    chunk_id=chunk.chunk_id,
                    paper_id=chunk.paper_id,
                    text=item.span_text,
                    char_start=location.char_start,
                    char_end=location.char_end,
                )
        claims.append(
            Claim(
                claim_id=f"claim_{n}",
                text=item.text,
                citation_indices=list(item.citation_indices),
                span=span,
            )
        )
    return StructuredSurvey(claims=claims)


def _repair_prompt(topic: str, findings_json: str) -> str:
    return (
        "The previous answer violated the citation contract. Fix every finding "
        "and return corrected JSON. Findings:\n"
        f"{findings_json}"
    )


async def generate_structured_survey(
    *,
    client: LLMClient | None,
    topic: str,
    evidence: list[EvidenceChunk],
    papers: list[Paper],
) -> tuple[StructuredSurvey, ContractReport]:
    """Generate, validate, repair once, then project/refuse (M1)."""
    if client is None:
        structured = template_structured_survey(topic, evidence, papers)
        report = validate_survey(structured, evidence)
        return structured, report

    packet = build_evidence_packet(evidence, papers)
    user_prompt = build_survey_prompt(topic, packet)

    try:
        draft, _ = await complete_structured(
            client,
            SURVEY_SYSTEM_PROMPT,
            user_prompt,
            ClaimDraftList,
            max_retries=1,
            temperature=0.2,
        )
    except Exception as exc:  # noqa: BLE001 - provider failure must not kill runs
        logger.warning(f"Structured survey generation failed, using template: {exc}")
        structured = template_structured_survey(topic, evidence, papers)
        return structured, validate_survey(structured, evidence)

    structured = project_draft(draft, evidence)
    report = validate_survey(structured, evidence)

    if report.ok:
        return structured, report

    # Exactly one bounded repair pass (D2).
    findings_json = json.dumps(
        [f.model_dump() for f in report.findings], ensure_ascii=False
    )
    try:
        repaired_draft, _ = await complete_structured(
            client,
            SURVEY_SYSTEM_PROMPT,
            f"{user_prompt}\n\n{_repair_prompt(topic, findings_json)}",
            ClaimDraftList,
            max_retries=1,
            temperature=0.2,
        )
    except LLMValidationError:
        repaired_draft = draft
    structured = project_draft(repaired_draft, evidence)
    report = validate_survey(structured, evidence)
    report.repaired = True

    if not report.ok:
        structured = legal_claims(structured, report)
    return structured, report
```

Note: `complete_structured` itself performs one JSON-schema retry; the contract-repair call here is a *second*, distinct model round prompted with the contract findings — total model calls for a repairable answer are bounded at 2 structured calls (each with at most 1 internal schema retry).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_survey_generate.py -v`
Expected: PASS (6 tests).

Design note: an edited/unfindable span is silently projected to `span=None` — it is not a contract violation (the claim's citation index is still legal), so it does not spend the one repair call. Index/out-of-range/unknown-chunk violations are what trigger repair.

- [ ] **Step 5: Gates**

Run: `make test-unit`, `make lint`, `make typecheck`, format-check touched files.
Expected: green.

---

### Task 7: Wire stage 6, graph factory, and API routes; graph-level tests

**Files:**
- Modify: `backend/src/app/domain/pipeline.py:18-37`
- Modify: `backend/src/app/pipeline/stages/stage6_survey.py` (full replacement of generation internals; keep stage name `"survey_generation"`)
- Modify: `backend/src/app/graphs/pipeline.py:119-139` (`default_pipeline_stages`)
- Modify: `backend/src/app/api/v1/pipeline_routes.py:64, 88-91, 113`
- Test: `backend/tests/unit/test_stage6_contract.py` (CREATE)

**Interfaces:**
- Consumes: `generate_structured_survey`, `render_survey`; `PipelineData`; `LLMClient`; route dependency `llm: LLMClient | None`.
- Produces:
  - `PipelineData.structured_survey: StructuredSurvey | None = None`; `PipelineData.contract_report: ContractReport | None = None`.
  - `SurveyGenerationStage.__init__(self, llm: LLMClient | None = None) -> None`.
  - `default_pipeline_stages(llm: LLMClient | None = None) -> list[BaseStage]` — only stage 6 receives `llm`; other stages unchanged; order/names unchanged.

- [ ] **Step 1: Write the failing graph-level tests**

Create `backend/tests/unit/test_stage6_contract.py`:

```python
"""End-to-end contract behaviour at the stage/graph boundary (M1)."""
from __future__ import annotations

import json

from app.domain.evidence import EvidenceChunk
from app.domain.paper import Paper
from app.domain.pipeline import PipelineData
from app.graphs.pipeline import build_pipeline_graph
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext
from app.pipeline.stages.stage6_survey import SurveyGenerationStage


class _RankedWithEvidence(BaseStage):
    """Plant ranked papers + evidence like stages 4/5 would."""

    def __init__(self) -> None:
        super().__init__(name="plant")

    async def _execute(self, ctx: PipelineContext) -> None:
        a1 = "verbatim anchor alpha"
        a2 = "verbatim anchor beta"
        papers = [
            Paper(paper_id="p1", title="Alpha", abstract=a1),
            Paper(paper_id="p2", title="Beta", abstract=a2),
        ]
        ctx.state.ranked = papers
        ctx.state.evidence = [
            EvidenceChunk(chunk_id="ev1", paper_id="p1", content=a1, anchor=a1,
                          char_start=0, char_end=len(a1)),
            EvidenceChunk(chunk_id="ev2", paper_id="p2", content=a2, anchor=a2,
                          char_start=0, char_end=len(a2)),
        ]


class TestStage6AtGraphBoundary:
    async def test_offline_graph_run_emits_legal_citations(self):
        graph = build_pipeline_graph(
            [_RankedWithEvidence(), SurveyGenerationStage()]
        )
        result = await graph.ainvoke(
            {"query": "t", "data": PipelineData(), "stage_results": []}
        )
        data: PipelineData = result["data"]
        assert data.survey is not None
        assert data.contract_report is not None and data.contract_report.ok
        assert {c.index for c in data.survey.citations} <= {1, 2}
        assert data.structured_survey is not None

    async def test_illegal_model_output_is_repaired_then_rendered(
        self, fake_llm_client
    ):
        evidence = [
            EvidenceChunk(chunk_id="ev1", paper_id="p1",
                          content="verbatim anchor alpha",
                          anchor="verbatim anchor alpha",
                          char_start=0, char_end=22),
        ]
        bad = {"claims": [
            {"text": "fabricated", "citation_indices": [42],
             "chunk_id": None, "span_text": None},
        ]}
        good = {"claims": [
            {"text": "grounded", "citation_indices": [1],
             "chunk_id": "ev1", "span_text": evidence[0].anchor},
        ]}
        client = fake_llm_client([json.dumps(bad), json.dumps(good)])

        graph = build_pipeline_graph(
            [_RankedWithEvidence(), SurveyGenerationStage(llm=client)]
        )
        result = await graph.ainvoke(
            {"query": "t", "data": PipelineData(), "stage_results": []}
        )
        data: PipelineData = result["data"]
        assert data.contract_report is not None
        assert data.contract_report.repaired and data.contract_report.ok
        assert data.survey is not None
        assert "[1]" in data.survey.answer
        assert "42" not in data.survey.answer

    async def test_stage7_still_filters_rendered_citations(self, fake_llm_client):
        """L1 verification keeps working on the rendered Survey type."""
        from app.pipeline.stages.stage7_verify import CitationVerificationStage

        good = {"claims": [
            {"text": "grounded", "citation_indices": [1],
             "chunk_id": "ev1", "span_text": "verbatim anchor alpha"},
        ]}
        client = fake_llm_client([json.dumps(good)])
        graph = build_pipeline_graph(
            [
                _RankedWithEvidence(),
                SurveyGenerationStage(llm=client),
                CitationVerificationStage(),
            ]
        )
        result = await graph.ainvoke(
            {"query": "t", "data": PipelineData(), "stage_results": []}
        )
        verified = result["data"].verified
        assert verified is not None and len(verified.citations) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_stage6_contract.py -v`
Expected: FAIL — stage 6 takes no `llm` argument and sets no `structured_survey`.

- [ ] **Step 3: Extend `PipelineData`**

In `backend/src/app/domain/pipeline.py`, add imports and fields:

```python
from app.domain.claim import ContractReport, StructuredSurvey
```

```python
    # stage 6 (M1 structured contract)
    structured_survey: StructuredSurvey | None = None
    contract_report: ContractReport | None = None
```

- [ ] **Step 4: Replace stage 6 internals**

Replace `backend/src/app/pipeline/stages/stage6_survey.py` (keep module docstring, update it to describe the contract) with:

```python
"""Stage 6: Survey Generation.

Generates a STRUCTURED survey (claims + pre-numbered citations + verbatim
spans), validates the citation contract (D7/D9), performs one bounded repair
pass (D2), and renders the existing wire-level Survey type for stages 7/8.

When no LLM client is configured, a deterministic offline template that is
legal by construction is used.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.domain.contract import Intent
from app.llm.base import LLMClient
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext
from app.survey.generate import generate_structured_survey
from app.survey.render import render_survey

logger = get_logger(__name__)


class SurveyGenerationStage(BaseStage):
    """Generate the final survey/answer under the citation contract (M1)."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        super().__init__(name="survey_generation")
        self._llm = llm

    async def _execute(self, ctx: PipelineContext) -> None:
        contract = ctx.state.contract
        intent = contract.intent if contract else Intent.FIND_PAPER
        topic = contract.topic if contract else ctx.query
        papers = ctx.state.ranked[:5]
        evidence = ctx.state.evidence

        logger.info(f"Generating structured survey for intent={intent.value}")

        structured, report = await generate_structured_survey(
            client=self._llm,
            topic=topic,
            evidence=evidence,
            papers=papers,
        )
        survey = render_survey(structured, evidence)

        ctx.state.structured_survey = structured
        ctx.state.contract_report = report
        ctx.state.survey = survey
        logger.info(
            f"Survey generated: {len(structured.claims)} claims, "
            f"contract_ok={report.ok}, repaired={report.repaired}, "
            f"findings={len(report.findings)}"
        )
```

The old `_build_citations` and `_generate_template_answer` are deleted (their logic lives in `app/survey/`; no existing tests import them — verified).

- [ ] **Step 5: Thread `llm` through the graph factory**

In `backend/src/app/graphs/pipeline.py`, change the signature and stage 6 line:

```python
def default_pipeline_stages(llm: LLMClient | None = None) -> list[BaseStage]:
    """Return the default 8 pipeline stages, in execution order."""
```

(add `from app.llm.base import LLMClient` with the imports), and construct stage 6 as `SurveyGenerationStage(llm=llm)`.

- [ ] **Step 6: Pass the injected client from the routes**

In `backend/src/app/api/v1/pipeline_routes.py`:
- `/run` (line ~64): replace `graph = build_pipeline_graph()` with
  ```python
  stages = default_pipeline_stages(llm=llm)
  graph = build_pipeline_graph(stages)
  ```
- `/run-stream` (line ~88): replace `stages = default_pipeline_stages()` with `stages = default_pipeline_stages(llm=llm)`.
- `/stages` keeps `default_pipeline_stages()` (no client needed; offline stage list is identical).

- [ ] **Step 7: Run the new tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/test_stage6_contract.py -v`
Expected: PASS (3 tests).

- [ ] **Step 8: Full gates**

Run: `make test-unit`, `make lint`, `make typecheck`, and `ruff format --check` on all files touched by this plan.
Expected: the full unit suite stays green; the eight stage names returned by `/pipeline/stages` are unchanged (`query_parse, recall, fusion, rerank, evidence_extraction, survey_generation, citation_verification, export`), so the SSE/frontend contract is preserved.

## Self-Review

**Spec coverage (M1 in spec §2):**
- Structured claim sequence with `citation_indices ⊆ [1..N]` → Tasks 2/3 (`Claim`, `validate_claim`). ✅
- Span offsets verbatim-matched (D9 by construction) → Tasks 1/2 (`locate_span`, stage-5 offsets). ✅
- Deterministic validator node/function + ONE bounded repair → Task 3 validator; Task 6 repair cap asserted by call count. ✅
- Projection/refusal after failed repair → Task 6 `legal_claims` + `ABSTENTION_NOTICE` (Task 5). ✅
- Output-contract framing, no decoding-guarantee claim → Global Constraints + spec pointer; thesis text is outside this plan but the disclaimer/§5 pointer enforce honesty. ✅
- First-pass/repair metrics for M7's ledger → `ContractReport.first_pass_ok/repaired/findings` persist on `PipelineData` (Task 7), consumable by the M7 plan. ✅

**Placeholder scan:** no TBD/TODO/"similar to task" steps; every code step shows complete code; Task 6 Step 4 contains an explicit test-correction instruction discovered during design (span mismatch is silent projection, not a repair trigger) — this is intentional design tightening, not a placeholder.

**Type consistency:** `locate_span(source, span, char_start, char_end)` signatures match across Tasks 2/3/5/6; `build_packet` 1-based indexing matches `PacketEntry.index`; `Claim.claim_id` (`claim_{n}`) matches `ContractFinding.claim_id` and `legal_claims`; `SurveyGenerationStage(llm=...)` matches `default_pipeline_stages(llm=...)` and both route call sites; `FakeLLMClient.chat` keyword set matches the calls `complete_structured` makes (verify against `app/llm/structured.py` during execution and extend the double's kwargs if it passes extras such as `max_tokens` — the double already accepts them).

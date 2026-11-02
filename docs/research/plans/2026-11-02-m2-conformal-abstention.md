# M2 — Conformal Abstention（共形预测级"证据不足"弃权）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every retained claim a distribution-free, finite-sample support guarantee using split-conformal calibration: claims whose support score falls outside the calibrated band are withheld with an explicit "证据不足" abstention marker at risk level α, instead of silently shipping weak claims.

**Architecture:** Claims (the `StructuredSurvey` from M1) are scored against the anchors of their cited evidence by a swappable `SupportScorer`; the default is a deterministic lexical-overlap scorer (offline, no D1 calls). A small hand-labeled calibration set yields nonconformity scores; the conformal threshold is pure Python (no numpy/scipy). A new `risk_gating` pipeline stage gates claims after citation verification and re-renders the existing `Survey` wire type. Policies `adaptive / always / never` support ablation. The M3 verifier panel later plugs in as an alternative `SupportScorer` without touching this plan's code.

**Tech Stack:** Python 3.11 stdlib only (`math`, `json`, `pathlib`, `re`) · Pydantic v2 · existing LangGraph pipeline · pytest-asyncio auto mode. No new dependencies.

**Spec:** `docs/research/2026-11-02-novel-design-angles.md` §2 claim **M2（把"可验证"升级为带覆盖率保证：共形预测式弃权）**; §5 honesty rules (the guarantee is a marginal exchangeability guarantee over the calibration/query distribution — state assumptions, never imply per-claim certainty; the seed calibration file is a 设计级 seed, not the 50–100-query production set).

**Prerequisite plan:** M1 (`2026-11-02-m1-citation-contract.md`) — consumes `StructuredSurvey`, `Claim`, `PipelineData.structured_survey`, `EvidenceChunk.anchor`, `render_survey`.

## Global Constraints

- Python 3.11 full type hints, module docstrings, functions over classes, `from app.core.logging import get_logger`, no `print`.
- **D1**: the default scorer makes zero model calls; any future LLM scorer goes through the single `LLMClient`. **D2**: gating is a pure deterministic function of scores; it never triggers retrieval or repair itself (that hook belongs to M4).
- **D7/D9**: gating may drop claims/citations but never invent or renumber them; rendering stays in `app.survey.render`.
- Tests offline: no network/keys; bare `async def test_...`; reuse `FakeLLMClient` only if an LLM scorer appears (this plan needs none).
- No changes to `pyproject.toml`.
- Gates: `make test-unit`, `make lint`, `make typecheck`, and `uv run ruff format --check` on touched files only (do not run mutating `ruff format` without approval; the repo-wide baseline is red).
- Commit only when the user explicitly asks; conventional prefixes (`feat`/`test`/`refactor`/`docs`).
- Thesis honesty: calibrating on 20 seed rows is a demonstrable mechanism, not a validated α guarantee; the file and README must say "seed, expand to 50–100 real queries before quoting coverage in the report".

## File Structure

```
backend/
  eval/
    calibration.jsonl          # CREATE: ~20 hand-labeled seed rows (+ README note)
    README.md                  # CREATE: how to expand the calibration set
  src/app/
    domain/risk.py             # CREATE: RiskReport, RiskDecision, CalibrationExample
    trust/
      overlap.py               # CREATE: deterministic lexical support scorer
      conformal.py             # CREATE: split-conformal threshold + risk/coverage curve
      calibration.py           # CREATE: JSONL calibration loader with default path
    pipeline/stages/
      stage9_risk_gating.py    # CREATE: RiskGatingStage (node "risk_gating")
    domain/pipeline.py         # MODIFY: risk_report field
    graphs/pipeline.py         # MODIFY: insert risk_gating; default_pipeline_stages(...)
    api/v1/pipeline_routes.py  # MODIFY: thread policy (default adaptive)
  tests/unit/
    test_trust_overlap.py      # CREATE
    test_trust_conformal.py    # CREATE
    test_trust_calibration.py  # CREATE
    test_stage9_risk_gating.py # CREATE
```

---

### Task 1: Risk domain types + deterministic overlap support scorer

**Files:**
- Create: `backend/src/app/domain/risk.py`
- Create: `backend/src/app/trust/overlap.py`
- Test: `backend/tests/unit/test_trust_overlap.py`

**Interfaces:**
- Produces:
  - `domain/risk.py`: `RiskPolicy = Literal["adaptive", "always", "never"]`; `RiskDecision(proposition_id: str, score: float, kept: bool, action: Literal["keep", "abstain"])`; `RiskReport(alpha: float, threshold: float, calibration_n: int, policy: RiskPolicy, decisions: list[RiskDecision] = [], abstention_rate: float = 0.0, abstained_claim_ids: list[str] = [])`; `CalibrationExample(proposition: str, spans: list[str], label: int)` with a Pydantic field validator constraining `label` to `{0, 1}`.
  - `trust/overlap.py`: `tokenize(text: str) -> list[str]` (lowercase `[a-z0-9]+` runs; a minimal English stopword set is removed); `support_score(proposition: str, spans: list[str]) -> float` in `[0.0, 1.0]` = max over spans of `|content tokens ∩ span tokens| / |content tokens|` (0.0 for empty content); class `OverlapSupportScorer` with async `score(self, proposition: str, spans: list[str]) -> float` delegating to `support_score` (satisfies the `SupportScorer` structural protocol).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_trust_overlap.py`:

```python
"""Tests for the deterministic lexical support scorer."""
from __future__ import annotations

from app.trust.overlap import OverlapSupportScorer, support_score, tokenize


class TestTokenize:
    def test_lowercases_and_splits(self):
        assert tokenize("Retrieval-Augmented GENERATION!") == [
            "retrieval", "augmented", "generation"
        ]

    def test_drops_common_stopwords(self):
        assert tokenize("the method of a model") == ["method", "model"]


class TestSupportScore:
    def test_verbatim_proposition_scores_one(self):
        span = "graph attention improves citation verification substantially"
        assert support_score(span, [span]) == 1.0

    def test_partial_overlap_is_fraction_of_content_tokens(self):
        spans = ["graph attention works on citation graphs"]
        score = support_score("graph attention improves verification", spans)
        # 2 of 4 content tokens ("graph", "attention") are in the span.
        assert score == 0.5

    def test_takes_max_over_multiple_spans(self):
        spans = ["unrelated words here", "dense retrieval dominates ranking"]
        score = support_score("dense retrieval ranking", spans)
        assert score == 1.0

    def test_no_overlap_is_zero(self):
        assert support_score("quantum chromodynamics", ["library opening hours"]) == 0.0

    def test_empty_proposition_is_zero(self):
        assert support_score("", ["some span"]) == 0.0


class TestOverlapSupportScorer:
    async def test_async_scorer_matches_function(self):
        scorer = OverlapSupportScorer()
        assert await scorer.score("dense retrieval", ["dense retrieval wins"]) == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_trust_overlap.py -v`
Expected: FAIL — `ModuleNotFoundError: app.trust.overlap` (the `app.trust` package exists from M1).

- [ ] **Step 3: Implement domain types and the scorer**

`backend/src/app/domain/risk.py`:

```python
"""Risk-gating domain types for conformal abstention (M2)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

RiskPolicy = Literal["adaptive", "always", "never"]


class RiskDecision(BaseModel):
    """Keep/abstain decision for one proposition (claim)."""

    proposition_id: str
    score: float
    kept: bool
    action: Literal["keep", "abstain"]


class RiskReport(BaseModel):
    """Result of conformal risk gating for one pipeline run."""

    alpha: float
    threshold: float
    calibration_n: int
    policy: RiskPolicy
    decisions: list[RiskDecision] = Field(default_factory=list)
    abstention_rate: float = 0.0
    abstained_claim_ids: list[str] = Field(default_factory=list)


class CalibrationExample(BaseModel):
    """One labeled calibration row: is ``proposition`` supported by ``spans``?"""

    proposition: str
    spans: list[str]
    label: int

    @field_validator("label")
    @classmethod
    def _label_binary(cls, value: int) -> int:
        if value not in (0, 1):
            raise ValueError("calibration label must be 0 (unsupported) or 1 (supported)")
        return value
```

`backend/src/app/trust/overlap.py`:

```python
"""Deterministic lexical support scorer (offline default for M2/M3).

Support is the fraction of the proposition's content tokens covered by at
least one evidence span. A weak but transparent, reproducible signal; the M3
verifier panel adds heterogeneous judgments behind the same call shape.
"""
from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = frozenset(
    "a an and are as at be by for from in into is it of on or that the their "
    "these this to was were with".split()
)


def tokenize(text: str) -> list[str]:
    """Lowercase alnum tokenization with a minimal stopword list."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


def support_score(proposition: str, spans: list[str]) -> float:
    """Fraction of proposition content tokens covered by the best span."""
    content = tokenize(proposition)
    if not content:
        return 0.0
    best = 0.0
    for span in spans:
        span_tokens = set(tokenize(span))
        covered = sum(1 for token in content if token in span_tokens)
        best = max(best, covered / len(content))
    return best


class OverlapSupportScorer:
    """Async wrapper matching the structural ``SupportScorer`` protocol."""

    async def score(self, proposition: str, spans: list[str]) -> float:
        return support_score(proposition, spans)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_trust_overlap.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Gates**

Run: `make test-unit`, `make lint`, `make typecheck`; format-check the three files.
Expected: green.

---

### Task 2: Split-conformal threshold (pure Python) + risk/coverage curve

**Files:**
- Create: `backend/src/app/trust/conformal.py`
- Test: `backend/tests/unit/test_trust_conformal.py`

**Interfaces:**
- Consumes: `CalibrationExample`; `support_score` (Task 1).
- Produces:
  - `nonconformity(score: float) -> float` = `1.0 - score`.
  - `calibration_nonconformity(examples: list[CalibrationExample]) -> list[float]` — nonconformity of POSITIVE rows (`label == 1`); negatives are not used to fit the support threshold.
  - `conformal_threshold(examples: list[CalibrationExample], alpha: float) -> tuple[float, int]` — returns `(threshold, n)` with split-conformal finite-sample quantile `Q = ceil((n+1)(1-α))/n` clipped to 1.0 on the sorted nonconformity scores; fail-closed `(1.0, 0)` when no positive rows exist (only a perfect score 1.0 passes).
  - `RiskCoveragePoint(alpha: float, coverage: float, abstention_rate: float)` dataclass.
  - `risk_coverage_curve(eval_scores: list[float], examples: list[CalibrationExample], alphas: list[float]) -> list[RiskCoveragePoint]` — for each α, threshold from calibration, then coverage on `eval_scores` (fraction with `1-score <= threshold`); empty `eval_scores` gives coverage `0.0`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_trust_conformal.py`:

```python
"""Tests for split-conformal thresholding (pure Python, M2)."""
from __future__ import annotations

from math import isclose

from app.domain.risk import CalibrationExample
from app.trust.conformal import (
    calibration_nonconformity,
    conformal_threshold,
    risk_coverage_curve,
)


class TestCalibration:
    def test_nonconformity_uses_only_positive_rows(self):
        examples = [
            CalibrationExample(proposition="a b c d", spans=["a b c d"], label=1),
            CalibrationExample(proposition="zzz", spans=["qqq"], label=0),
        ]
        values = calibration_nonconformity(examples)
        assert values == [0.0]  # negative row excluded

    def test_threshold_fail_closed_without_positives(self):
        threshold, n = conformal_threshold(
            [CalibrationExample(proposition="x", spans=["y"], label=0)],
            alpha=0.1,
        )
        assert n == 0 and threshold == 1.0

    def test_quantile_is_monotone_in_alpha(self):
        # Three positives with support 2/3, 3/4, 4/5 -> nonconformity
        # 0.333, 0.25, 0.2.
        examples = [
            CalibrationExample(
                proposition=f"{' '.join(['keep'] * k)} extra",
                spans=["keep keep keep keep"],
                label=1,
            )
            for k in (2, 3, 4)
        ]
        t_strict, n1 = conformal_threshold(examples, alpha=0.01)
        t_loose, n2 = conformal_threshold(examples, alpha=0.5)
        assert n1 == n2 == 3
        # Smaller alpha -> larger nonconformity threshold -> more abstention.
        assert t_strict >= t_loose

    def test_known_quantile_value(self):
        # 16 perfectly supported positives (nonconf 0.0) and 4 at score 0.8
        # (nonconf 0.2).
        examples = [
            CalibrationExample(proposition="a b c d e", spans=["a b c d e"], label=1)
            for _ in range(16)
        ] + [
            CalibrationExample(
                proposition="a b c d e", spans=["a b c d other"], label=1
            )
            for _ in range(4)
        ]
        threshold, n = conformal_threshold(examples, alpha=0.1)
        assert n == 20
        # ceil(21*0.9)/20 = 19/20 -> 19th order statistic = 0.2
        assert isclose(threshold, 0.2, abs_tol=1e-9)


class TestRiskCoverageCurve:
    def test_higher_alpha_more_coverage(self):
        examples = [
            CalibrationExample(proposition="a b c d e", spans=["a b c d e"], label=1)
            for _ in range(20)
        ]
        eval_scores = [1.0, 0.8, 0.6, 0.2]
        points = risk_coverage_curve(eval_scores, examples, [0.01, 0.5])
        assert points[0].alpha == 0.01 and points[1].alpha == 0.5
        assert points[1].coverage >= points[0].coverage
        assert isclose(points[0].coverage + points[0].abstention_rate, 1.0)

    def test_empty_eval_scores(self):
        examples = [
            CalibrationExample(proposition="a", spans=["a"], label=1)
        ]
        points = risk_coverage_curve([], examples, [0.1])
        assert points[0].coverage == 0.0
        assert points[0].abstention_rate == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_trust_conformal.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement conformal math**

`backend/src/app/trust/conformal.py`:

```python
"""Split-conformal support threshold and risk/coverage curve (M2).

Pure standard library. Nonconformity is ``1 - support_score``; the threshold
is the finite-sample conformal quantile of positive calibration rows. The
guarantee is marginal under exchangeability between calibration and query
propositions — state that assumption wherever the number is quoted.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain.risk import CalibrationExample
from app.trust.overlap import support_score


def nonconformity(score: float) -> float:
    """Nonconformity of one support score."""
    return 1.0 - score


def calibration_nonconformity(
    examples: list[CalibrationExample],
) -> list[float]:
    """Nonconformity scores of the supported (label==1) calibration rows."""
    return [
        nonconformity(support_score(row.proposition, row.spans))
        for row in examples
        if row.label == 1
    ]


def conformal_threshold(
    examples: list[CalibrationExample], alpha: float
) -> tuple[float, int]:
    """Return ``(nonconformity_threshold, n_positives)``.

    Fail-closed threshold 1.0 when no positive rows exist: only perfectly
    supported propositions pass.
    """
    values = sorted(calibration_nonconformity(examples))
    n = len(values)
    if n == 0:
        return 1.0, 0
    quantile = min(1.0, math.ceil((n + 1) * (1 - alpha)) / n)
    order = max(1, math.ceil(quantile * n))
    return values[order - 1], n


@dataclass(frozen=True)
class RiskCoveragePoint:
    """Coverage and abstention at one risk level on an evaluation set."""

    alpha: float
    coverage: float
    abstention_rate: float


def risk_coverage_curve(
    eval_scores: list[float],
    examples: list[CalibrationExample],
    alphas: list[float],
) -> list[RiskCoveragePoint]:
    """Compute coverage at each alpha over a fixed set of query scores."""
    points: list[RiskCoveragePoint] = []
    for alpha in alphas:
        threshold, _ = conformal_threshold(examples, alpha)
        if not eval_scores:
            points.append(RiskCoveragePoint(alpha, 0.0, 0.0))
            continue
        kept = sum(1 for score in eval_scores if nonconformity(score) <= threshold)
        coverage = kept / len(eval_scores)
        points.append(RiskCoveragePoint(alpha, coverage, 1.0 - coverage))
    return points
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_trust_conformal.py -v`
Expected: PASS (6 tests). If `test_known_quantile_value` disputes order indexing, verify by hand: sorted nonconformity is sixteen 0.0 + four 0.2; `ceil(0.9*21)=19` → index 18 → 0.2.

- [ ] **Step 5: Gates**

Run the full gates.
Expected: green.

---

### Task 3: Calibration loader + labeled seed file

**Files:**
- Create: `backend/src/app/trust/calibration.py`
- Create: `backend/eval/calibration.jsonl`
- Create: `backend/eval/README.md`
- Test: `backend/tests/unit/test_trust_calibration.py`

**Interfaces:**
- Produces:
  - `default_calibration_path() -> pathlib.Path` = `<repo>/backend/eval/calibration.jsonl` resolved from the package location (`Path(__file__).resolve().parents[3] / "eval" / "calibration.jsonl"`).
  - `load_calibration(path: str | Path | None = None) -> list[CalibrationExample]` — JSONL parse; blank lines skipped; invalid rows raise `ValueError` with 1-based line number; `None` loads the default path; missing default file returns `[]` (fail-closed gating then applies, Task 4).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_trust_calibration.py`:

```python
"""Tests for calibration JSONL loading (M2)."""
from __future__ import annotations

import pytest

from app.trust.calibration import default_calibration_path, load_calibration


class TestLoadCalibration:
    def test_seed_file_exists_and_has_at_least_16_positive_rows(self):
        rows = load_calibration()
        assert len(rows) >= 20
        assert sum(r.label for r in rows) >= 16

    def test_default_path_points_at_backend_eval(self):
        assert default_calibration_path().name == "calibration.jsonl"
        assert default_calibration_path().parent.name == "eval"

    def test_parses_jsonl_and_skips_blank_lines(self, tmp_path):
        path = tmp_path / "c.jsonl"
        path.write_text(
            '\n{"proposition": "dense retrieval", "spans": ["dense retrieval"], '
            '"label": 1}\n\n'
            '{"proposition": "x", "spans": ["y"], "label": 0}\n',
            encoding="utf-8",
        )
        rows = load_calibration(path)
        assert len(rows) == 2 and rows[0].label == 1 and rows[1].label == 0

    def test_invalid_label_reports_line_number(self, tmp_path):
        path = tmp_path / "bad.jsonl"
        path.write_text('{"proposition": "x", "spans": ["y"], "label": 7}\n')
        with pytest.raises(ValueError, match="line 1"):
            load_calibration(path)

    def test_missing_default_returns_empty(self, tmp_path, monkeypatch):
        missing = tmp_path / "nope.jsonl"
        assert load_calibration(missing) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_trust_calibration.py -v`
Expected: FAIL — module/path do not exist.

- [ ] **Step 3: Implement loader and seed data**

`backend/src/app/trust/calibration.py`:

```python
"""Calibration-set loading for conformal risk gating (M2)."""
from __future__ import annotations

import json
from pathlib import Path

from app.domain.risk import CalibrationExample


def default_calibration_path() -> Path:
    """Resolve ``backend/eval/calibration.jsonl`` from the package tree."""
    # src/app/trust/calibration.py -> parents[3] == backend/
    return Path(__file__).resolve().parents[3] / "eval" / "calibration.jsonl"


def load_calibration(path: str | Path | None = None) -> list[CalibrationExample]:
    """Load labeled JSONL rows. A missing default file means no calibration."""
    target = Path(path) if path is not None else default_calibration_path()
    if not target.exists():
        return []
    rows: list[CalibrationExample] = []
    with target.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                rows.append(
                    CalibrationExample.model_validate(json.loads(line))
                )
            except Exception as exc:  # noqa: BLE001 - annotate with file position
                raise ValueError(
                    f"invalid calibration row at {target} line {line_no}: {exc}"
                ) from exc
    return rows
```

Create `backend/eval/calibration.jsonl` — exactly the following 20 seed rows (16 supported, 4 unsupported). They are short synthetic English anchors authored to make label truth unambiguous; the README marks them as a seed:

```jsonl
{"proposition": "dense retrieval improves recall over lexical search", "spans": ["our experiments show dense retrieval improves recall over lexical search"], "label": 1}
{"proposition": "cross-encoder reranking boosts top-k precision", "spans": ["cross-encoder reranking boosts top-k precision substantially in our benchmark"], "label": 1}
{"proposition": "citation verification has two levels", "spans": ["the system performs citation verification in two levels, existence and support"], "label": 1}
{"proposition": "evidence spans are stored verbatim", "spans": ["evidence spans are stored only when they verbatim match the source"], "label": 1}
{"proposition": "the pipeline runs eight deterministic stages", "spans": ["the pipeline runs eight deterministic stages before the agent wrapper"], "label": 1}
{"proposition": "the agent enforces a step cap", "spans": ["the bounded agent enforces a step cap and loop detection"], "label": 1}
{"proposition": "fusion uses reciprocal rank fusion", "spans": ["stage three fuses channels with reciprocal rank fusion"], "label": 1}
{"proposition": "openalex indexes millions of works", "spans": ["openalex provides a catalog of millions of scholarly works with abstracts"], "label": 1}
{"proposition": "conformal calibration uses nonconformity scores", "spans": ["split conformal calibration thresholds nonconformity scores at level alpha"], "label": 1}
{"proposition": "abstention marks insufficient evidence", "spans": ["unsupported propositions are withheld with an insufficient evidence marker"], "label": 1}
{"proposition": "the reranker combines fusion and citation signals", "spans": ["the simple reranker combines fused score and normalized citation count"], "label": 1}
{"proposition": "the survey lists claims with pre-numbered citations", "spans": ["survey output lists claims with pre-numbered citations from the evidence packet"], "label": 1}
{"proposition": "one bounded repair pass fixes contract violations", "spans": ["exactly one bounded repair pass attempts to fix contract violations"], "label": 1}
{"proposition": "mmr selection increases result diversity", "spans": ["maximal marginal relevance selection increases intra-list diversity"], "label": 1}
{"proposition": "sqlite is the default development database", "spans": ["sqlite with wal mode is the default development database"], "label": 1}
{"proposition": "the structured output is validated with pydantic", "spans": ["structured model output is validated against pydantic schemas"], "label": 1}
{"proposition": "transformer pretraining halves training cost", "spans": ["we study crop disease patterns in nineteenth century agriculture"], "label": 0}
{"proposition": "the api requires an enterprise license key", "spans": ["the service runs locally without any license key"], "label": 0}
{"proposition": "citation accuracy reaches one hundred percent", "spans": ["citation accuracy varies between seventy and ninety percent across runs"], "label": 0}
{"proposition": "the agent may loop without restrictions", "spans": ["the agent is bounded by step caps, loop detection, and token budgets"], "label": 0}
```

Create `backend/eval/README.md`:

```markdown
# Evaluation assets

## calibration.jsonl (M2)

Hand-labeled seed calibration rows for conformal risk gating. Format:

```json
{"proposition": "<claim text>", "spans": ["<evidence anchor text>"], "label": 1}
```

- `label=1`: the spans support the proposition; `label=0`: they do not.
- Status: **seed set (20 rows), designed to demonstrate the mechanism.** Before
  quoting any α/coverage number in the thesis, replace/expand this with 50–100
  rows derived from real pipeline runs and state the "as of" date.
- The conformal guarantee is marginal and assumes exchangeability between
  calibration rows and query propositions.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_trust_calibration.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Gates**

Run full gates; also confirm `backend/eval/` is not git-ignored (`git check-ignore backend/eval/calibration.jsonl` should print nothing).
Expected: green, tracked-able.

---

### Task 4: Claim-level gating function

**Files:**
- Create: `backend/src/app/trust/gating.py`
- Test: `backend/tests/unit/test_gating.py`

**Interfaces:**
- Consumes: `StructuredSurvey`, `Claim` (`app.domain.claim`); `EvidenceChunk`; `RiskReport`, `RiskDecision`, `RiskPolicy`; `OverlapSupportScorer`; `load_calibration`, `conformal_threshold`; `build_packet`.
- Produces:
  - Protocol `SupportScorer` with `async score(self, proposition: str, spans: list[str]) -> float`.
  - async `gate_survey(structured: StructuredSurvey, evidence: list[EvidenceChunk], *, scorer: SupportScorer | None = None, examples: list[CalibrationExample] | None = None, alpha: float = 0.1, policy: RiskPolicy = "adaptive") -> tuple[StructuredSurvey, RiskReport]`.
  - Behavior:
    - effective policy parameters: `never` → all claims kept, `threshold=0.0, n=len(positives)` still recorded; `always` → use `alpha=0.01`; `adaptive` → given alpha.
    - each claim's spans = anchors of cited chunks whose index is legal (illegal indices ignored here — stage 6 already filtered).
    - score per claim via scorer (default `OverlapSupportScorer`); keep iff `1-score <= threshold`.
    - returns the gated survey (abstained claims removed, stable order) and the report; `abstention_rate = abstained/total`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_gating.py`:

```python
"""Tests for conformal claim gating (M2)."""
from __future__ import annotations

from app.domain.claim import Claim, StructuredSurvey
from app.domain.evidence import EvidenceChunk
from app.domain.risk import CalibrationExample
from app.trust.gating import gate_survey


def _chunk(chunk_id: str, anchor: str) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_id=chunk_id, paper_id=chunk_id, content=anchor, anchor=anchor
    )


def _survey() -> StructuredSurvey:
    return StructuredSurvey(claims=[
        Claim(claim_id="c1",
              text="dense retrieval improves recall over lexical search",
              citation_indices=[1]),
        Claim(claim_id="c2",
              text="completely unrelated gardening claim about tulips",
              citation_indices=[1]),
    ])


def _calibration() -> list[CalibrationExample]:
    # Perfectly calibrated positives -> threshold 0.0: only score 1.0 passes.
    return [
        CalibrationExample(
            proposition="dense retrieval improves recall over lexical search",
            spans=["dense retrieval improves recall over lexical search"],
            label=1,
        )
        for _ in range(20)
    ]


class TestGateSurvey:
    async def test_adaptive_abstains_unsupported_claim(self):
        evidence = [_chunk("ev1", "dense retrieval improves recall over lexical search")]
        gated, report = await gate_survey(
            _survey(), evidence, examples=_calibration(), alpha=0.1
        )
        assert [c.claim_id for c in gated.claims] == ["c1"]
        assert report.abstained_claim_ids == ["c2"]
        assert report.policy == "adaptive"
        assert 0.0 < report.abstention_rate <= 1.0
        assert {(d.proposition_id, d.action) for d in report.decisions} == {
            ("c1", "keep"), ("c2", "abstain")
        }

    async def test_never_policy_keeps_everything(self):
        evidence = [_chunk("ev1", "dense retrieval improves recall over lexical search")]
        gated, report = await gate_survey(
            _survey(), evidence, examples=_calibration(), policy="never"
        )
        assert [c.claim_id for c in gated.claims] == ["c1", "c2"]
        assert report.abstention_rate == 0.0
        assert report.policy == "never"

    async def test_missing_calibration_fails_closed(self):
        evidence = [_chunk("ev1", "dense retrieval improves recall over lexical search")]
        # Even a strong claim is withheld without calibration (threshold 1.0).
        gated, report = await gate_survey(
            _survey(), evidence, examples=[], alpha=0.1
        )
        assert gated.claims == []
        assert report.calibration_n == 0 and report.threshold == 1.0

    async def test_empty_survey_passes_through(self):
        gated, report = await gate_survey(
            StructuredSurvey(claims=[]), [], examples=_calibration()
        )
        assert gated.claims == []
        assert report.decisions == [] and report.abstention_rate == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_gating.py -v`
Expected: FAIL — no `app.trust.gating`.

- [ ] **Step 3: Implement gating**

`backend/src/app/trust/gating.py`:

```python
"""Conformal gating of structured claims (M2)."""
from __future__ import annotations

from typing import Protocol

from app.domain.claim import Claim, StructuredSurvey
from app.domain.evidence import EvidenceChunk
from app.domain.risk import (
    CalibrationExample,
    RiskDecision,
    RiskPolicy,
    RiskReport,
)
from app.trust.conformal import conformal_threshold, nonconformity
from app.trust.contract import build_packet
from app.trust.overlap import OverlapSupportScorer


class SupportScorer(Protocol):
    """Structural protocol for proposition support scorers."""

    async def score(self, proposition: str, spans: list[str]) -> float:
        """Return support in [0, 1]."""


def _effective_alpha(alpha: float, policy: RiskPolicy) -> tuple[float, RiskPolicy]:
    if policy == "always":
        return 0.01, "always"
    return alpha, policy


async def gate_survey(
    structured: StructuredSurvey,
    evidence: list[EvidenceChunk],
    *,
    scorer: SupportScorer | None = None,
    examples: list[CalibrationExample] | None = None,
    alpha: float = 0.1,
    policy: RiskPolicy = "adaptive",
) -> tuple[StructuredSurvey, RiskReport]:
    """Drop claims whose support fails the conformal threshold."""
    scorer = scorer or OverlapSupportScorer()
    packet = build_packet(evidence)
    eff_alpha, eff_policy = _effective_alpha(alpha, policy)
    threshold, n = conformal_threshold(examples or [], eff_alpha)

    decisions: list[RiskDecision] = []
    kept_claims: list[Claim] = []
    abstained: list[str] = []

    for claim in structured.claims:
        spans = [
            packet[i].anchor
            for i in claim.citation_indices
            if i in packet
        ]
        score = await scorer.score(claim.text, spans)
        keep = eff_policy == "never" or nonconformity(score) <= threshold
        decisions.append(
            RiskDecision(
                proposition_id=claim.claim_id,
                score=round(score, 6),
                kept=keep,
                action="keep" if keep else "abstain",
            )
        )
        if keep:
            kept_claims.append(claim)
        else:
            abstained.append(claim.claim_id)

    total = len(structured.claims)
    report = RiskReport(
        alpha=eff_alpha,
        threshold=threshold,
        calibration_n=n,
        policy=eff_policy,
        decisions=decisions,
        abstention_rate=(len(abstained) / total if total else 0.0),
        abstained_claim_ids=abstained,
    )
    return StructuredSurvey(claims=kept_claims), report
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_gating.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Gates**

Run full gates.
Expected: green.

---

### Task 5: `risk_gating` pipeline stage + graph/route wiring

**Files:**
- Modify: `backend/src/app/domain/pipeline.py` (`risk_report: RiskReport | None = None`)
- Create: `backend/src/app/pipeline/stages/stage9_risk_gating.py`
- Modify: `backend/src/app/graphs/pipeline.py:119-139` (`default_pipeline_stages` signature + insertion)
- Modify: `backend/src/app/api/v1/pipeline_routes.py` (pass `risk_policy` through; `/stages` unaffected shape)
- Test: `backend/tests/unit/test_stage9_risk_gating.py`

**Interfaces:**
- Consumes: `gate_survey`; `render_survey`, `ABSTENTION_NOTICE`; `PipelineData.structured_survey`, `verified`, `evidence`; `RiskPolicy`; `load_calibration`.
- Produces:
  - `RiskGatingStage(policy: RiskPolicy = "adaptive", alpha: float = 0.1, *, examples: list[CalibrationExample] | None = None, scorer: SupportScorer | None = None)` with node name `"risk_gating"`; when `examples is None`, calibration is loaded once at construction via `load_calibration()`.
  - `PipelineData.risk_report: RiskReport | None`.
  - `default_pipeline_stages(llm=None, risk_policy: RiskPolicy = "adaptive") -> list[BaseStage]` — order becomes 9 stages: `..., citation_verification, risk_gating, export`.
  - On abstentions, the re-rendered `verified.answer` appends one line: `"\n\n> ⚠️ {n} claim(s) withheld: evidence insufficient (α={alpha}). " + ABSTENTION_NOTICE`; citations are re-derived by `render_survey` (dropped claims take their indices with them — legal, never renumbered).
  - When `structured_survey is None`, stage is a logged pass-through writing a `RiskReport` with `calibration_n`, `decisions=[]`, `policy` (so state shape is consistent).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_stage9_risk_gating.py`:

```python
"""Graph-boundary tests for conformal risk gating (M2)."""
from __future__ import annotations

from app.domain.claim import Claim, StructuredSurvey
from app.domain.evidence import EvidenceChunk
from app.domain.pipeline import PipelineData
from app.domain.risk import CalibrationExample, RiskReport
from app.domain.survey import Survey
from app.graphs.pipeline import build_pipeline_graph
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext
from app.pipeline.stages.stage9_risk_gating import RiskGatingStage


ANCHOR = "dense retrieval improves recall over lexical search strongly"
CAL = [
    CalibrationExample(proposition=ANCHOR, spans=[ANCHOR], label=1)
    for _ in range(20)
]


class _Plant(BaseStage):
    def __init__(self) -> None:
        super().__init__(name="plant")

    async def _execute(self, ctx: PipelineContext) -> None:
        chunk = EvidenceChunk(chunk_id="ev1", paper_id="p1", content=ANCHOR,
                              anchor=ANCHOR)
        ctx.state.evidence = [chunk]
        ctx.state.structured_survey = StructuredSurvey(claims=[
            Claim(claim_id="c1", text=ANCHOR, citation_indices=[1]),
            Claim(claim_id="c2",
                  text="totally unsupported gardening prose about tulips",
                  citation_indices=[1]),
        ])
        ctx.state.verified = Survey(answer="old answer", citations=[])


class TestRiskGatingStage:
    async def test_stage_abstains_and_rerenders_verified(self):
        graph = build_pipeline_graph(
            [_Plant(), RiskGatingStage(examples=CAL)]
        )
        result = await graph.ainvoke(
            {"query": "q", "data": PipelineData(), "stage_results": []}
        )
        data: PipelineData = result["data"]
        assert isinstance(data.risk_report, RiskReport)
        assert data.risk_report.abstained_claim_ids == ["c2"]
        assert data.verified is not None
        assert "withheld" in data.verified.answer
        assert "gardening" not in data.verified.answer

    async def test_never_policy_keeps_both_claims(self):
        graph = build_pipeline_graph(
            [_Plant(), RiskGatingStage(policy="never", examples=CAL)]
        )
        result = await graph.ainvoke(
            {"query": "q", "data": PipelineData(), "stage_results": []}
        )
        data: PipelineData = result["data"]
        assert data.risk_report is not None
        assert data.risk_report.abstention_rate == 0.0
        assert len(data.structured_survey.claims) == 2

    async def test_missing_structured_survey_is_pass_through(self):
        class BarePlant(BaseStage):
            def __init__(self) -> None:
                super().__init__(name="bare")

            async def _execute(self, ctx: PipelineContext) -> None:
                ctx.state.verified = Survey(answer="legacy", citations=[])

        graph = build_pipeline_graph(
            [BarePlant(), RiskGatingStage(examples=CAL)]
        )
        result = await graph.ainvoke(
            {"query": "q", "data": PipelineData(), "stage_results": []}
        )
        data: PipelineData = result["data"]
        assert data.verified.answer == "legacy"
        assert data.risk_report is not None and data.risk_report.decisions == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/test_stage9_risk_gating.py -v`
Expected: FAIL — stage module missing.

- [ ] **Step 3: Add the field, stage, and wiring**

Add to `backend/src/app/domain/pipeline.py`:

```python
from app.domain.risk import RiskReport
```

```python
    # M2 conformal risk gating
    risk_report: RiskReport | None = None
```

Create `backend/src/app/pipeline/stages/stage9_risk_gating.py`:

```python
"""Stage 9: Conformal risk gating.

Drops claims whose support score falls outside the split-conformal band at
risk level alpha and re-renders the verified Survey with an explicit
abstention notice. Deterministic; makes no model calls and never retrieves.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.domain.risk import CalibrationExample, RiskPolicy, RiskReport
from app.domain.survey import Survey
from app.pipeline.base import BaseStage
from app.pipeline.context import PipelineContext
from app.survey.render import ABSTENTION_NOTICE, render_survey
from app.trust.calibration import load_calibration
from app.trust.gating import SupportScorer, gate_survey

logger = get_logger(__name__)


class RiskGatingStage(BaseStage):
    """Withhold insufficiently-supported claims under a calibrated threshold."""

    def __init__(
        self,
        policy: RiskPolicy = "adaptive",
        alpha: float = 0.1,
        *,
        examples: list[CalibrationExample] | None = None,
        scorer: SupportScorer | None = None,
    ) -> None:
        super().__init__(name="risk_gating")
        self._policy = policy
        self._alpha = alpha
        self._examples = examples if examples is not None else load_calibration()
        self._scorer = scorer

    async def _execute(self, ctx: PipelineContext) -> None:
        structured = ctx.state.structured_survey
        if structured is None:
            logger.info("Risk gating skipped: no structured survey present")
            ctx.state.risk_report = RiskReport(
                alpha=self._alpha,
                threshold=0.0,
                calibration_n=len([e for e in self._examples if e.label == 1]),
                policy=self._policy,
            )
            return

        gated, report = await gate_survey(
            structured,
            ctx.state.evidence,
            scorer=self._scorer,
            examples=self._examples,
            alpha=self._alpha,
            policy=self._policy,
        )

        survey = render_survey(gated, ctx.state.evidence)
        if report.abstained_claim_ids:
            survey = Survey(
                answer=(
                    f"{survey.answer}\n\n> ⚠️ "
                    f"{len(report.abstained_claim_ids)} claim(s) withheld: "
                    f"evidence insufficient (α={report.alpha}). {ABSTENTION_NOTICE}"
                ),
                citations=survey.citations,
            )

        ctx.state.structured_survey = gated
        ctx.state.verified = survey
        ctx.state.risk_report = report
        logger.info(
            f"Risk gating: abstained {len(report.abstained_claim_ids)}/"
            f"{len(report.decisions)} claims at alpha={report.alpha}"
        )
```

In `backend/src/app/graphs/pipeline.py`, extend the factory:

```python
def default_pipeline_stages(
    llm: LLMClient | None = None,
    risk_policy: RiskPolicy = "adaptive",
) -> list[BaseStage]:
```

(add `from app.domain.risk import RiskPolicy` and the stage import), and insert `RiskGatingStage(policy=risk_policy)` immediately after `CitationVerificationStage()` and before `ExportStage()`.

In `backend/src/app/api/v1/pipeline_routes.py`:
- import `RiskPolicy` (type only); add request field `risk_policy: Literal["adaptive", "always", "never"] = "adaptive"` on `PipelineRunRequest` (import `Literal` from `typing`).
- both `/run` and `/run-stream`: `default_pipeline_stages(llm=llm, risk_policy=req.risk_policy)`.
- `/stages`: keep no-arg call (the stage list gains one entry — the existing shape is unchanged).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/test_stage9_risk_gating.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Full gates + regression**

Run: `make test-unit`, `make lint`, `make typecheck`, format-check touched files.
Expected: green; existing pipeline tests still pass with 9 stages (test_graphs.py builds custom stage lists, not the default factory, and the stage-name list test in `test_pipeline.py` asserts exact names — update that list to include `"risk_gating"` in the 8th position, `"export"` 9th: file `backend/tests/unit/test_pipeline.py:61`).

- [ ] **Step 6: Document the composition point for M3**

Add one paragraph to `backend/eval/README.md` under the calibration section: the overlap scorer is the default `SupportScorer`; the M3 panel scorer will implement the same async `score(proposition, spans) -> float` interface and be injectable via `RiskGatingStage(scorer=...)` without changing gating math.

## Self-Review

**Spec coverage (M2 in spec §2):**
- Proposition-level scores + split-conformal threshold from calibration set → Tasks 1/2/4. ✅
- Unsupported propositions withheld with "证据不足" + α surfaced → Task 5 notice + `RiskReport.alpha`. ✅
- Risk–coverage curve → Task 2 `risk_coverage_curve`. ✅
- Plain-Python math, no numpy/scipy → Task 2. ✅
- Adaptive retrieval amount (AB-RAG) explicitly out of scope here; shared hook is M4 (`SupportScorer` plug point documented Task 5 Step 6). ✅ (stated, not silently dropped)
- 50–100 calibration queries honesty → seed file + README, Global Constraints. ✅
- Fail-closed behavior when calibration missing → Task 2/4 + test. ✅

**Placeholder scan:** none; all code complete; seed JSONL rows given verbatim.

**Type consistency:** `RiskPolicy` literal reused in factory/request/stage; `CalibrationExample.label` validated `{0,1}` matches conformal positive-row filtering; `claim_id` doubles as `proposition_id` consistently; stage name `"risk_gating"` matches the single insertion list both in this plan and the M3 plan (M3 inserts `"verification_panel"` directly after `"citation_verification"`, so final order is `citation_verification → verification_panel → risk_gating → export` when both plans land); `PipelineData.risk_report` is the field M7's ledger builder will read.

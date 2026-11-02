"""Unit tests for the typed domain contracts (``app.domain``)."""
from __future__ import annotations

from app.domain.contract import Intent, QueryContract
from app.domain.evidence import EvidenceChunk
from app.domain.export import Export
from app.domain.paper import Paper, paper_to_wire
from app.domain.pipeline import PipelineData
from app.domain.record import SearchRecord
from app.domain.survey import Citation, Survey


class TestIntent:
    def test_values_match_classifier(self) -> None:
        # stage1._classify_intent returns these exact strings.
        assert {i.value for i in Intent} == {
            "survey",
            "compare",
            "find_method",
            "explain",
            "find_paper",
        }

    def test_construct_from_value(self) -> None:
        assert Intent("survey") is Intent.SURVEY


class TestQueryContract:
    def test_defaults(self) -> None:
        q = QueryContract(topic="transformers")
        assert q.topic == "transformers"
        assert q.methods == []
        assert q.exclusions == []
        assert q.venue is None
        assert q.year_start is None
        assert q.year_end is None
        assert q.intent is Intent.FIND_PAPER

    def test_full_contract(self) -> None:
        q = QueryContract(
            topic="attention mechanisms",
            methods=["self-attention"],
            venue="NeurIPS",
            year_start=2020,
            year_end=2024,
            exclusions=["survey"],
            intent=Intent.COMPARE,
        )
        assert q.methods == ["self-attention"]
        assert q.intent is Intent.COMPARE


class TestPaper:
    def test_authors_is_list(self) -> None:
        p = Paper(paper_id="p1", title="t", authors=["Alice", "Bob"])
        assert p.authors == ["Alice", "Bob"]

    def test_defaults(self) -> None:
        p = Paper(paper_id="p1", title="t")
        assert p.authors == []
        assert p.abstract == ""
        assert p.citation_count == 0
        assert p.score is None
        assert p.fused_score is None
        assert p.rerank_score is None
        assert p.rank is None

    def test_wire_mapping(self) -> None:
        p = Paper(
            paper_id="p1",
            title="t",
            authors=["Alice", "Bob"],
            venue="NeurIPS",
            year=2024,
            abstract="abs",
            doi="10.0/x",
            score=0.9,
            rerank_score=0.88,
            rank=3,
        )
        wire = paper_to_wire(p)
        assert wire["id"] == "p1"
        assert wire["authors"] == "Alice, Bob"  # frontend expects a joined string
        assert wire["score"] == 0.9
        assert wire["rerank_score"] == 0.88
        assert wire["rank"] == 3


class TestSearchRecord:
    def test_fields(self) -> None:
        r = SearchRecord(record_id="r1", query_text="q", result_paper_ids=["p1", "p2"])
        assert r.result_paper_ids == ["p1", "p2"]
        assert r.filters == {}


class TestEvidenceChunk:
    def test_verbatim_defaults_true(self) -> None:
        # D9: evidence is stored only on verbatim match -> flag defaults True.
        e = EvidenceChunk(
            chunk_id="c1",
            paper_id="p1",
            section="abstract",
            content="claim",
            anchor="claim",
        )
        assert e.verbatim is True


class TestSurvey:
    def test_pre_numbered_citations(self) -> None:
        # D7: citations are pre-numbered [1..N].
        s = Survey(
            answer="summary",
            citations=[
                Citation(index=1, paper_id="p1", chunk_id="c1"),
                Citation(index=2, paper_id="p2", chunk_id="c2"),
            ],
        )
        assert [c.index for c in s.citations] == [1, 2]
        assert s.citations[0].paper_id == "p1"


class TestExport:
    def test_formats(self) -> None:
        e = Export(formats={"markdown": "md", "bibtex": "bib", "json": "{}"})
        assert set(e.formats) == {"markdown", "bibtex", "json"}


class TestPipelineData:
    def test_defaults(self) -> None:
        d = PipelineData()
        assert d.contract is None
        assert d.recalled == []
        assert d.ranked == []
        assert d.evidence == []
        assert d.survey is None
        assert d.verified is None
        assert d.exports is None

    def test_round_trip(self) -> None:
        d = PipelineData(
            contract=QueryContract(topic="t"),
            recalled=[Paper(paper_id="p1", title="t")],
            survey=Survey(answer="a", citations=[Citation(index=1, paper_id="p1")]),
        )
        out = PipelineData.model_validate(d.model_dump())
        assert out.contract.topic == "t"
        assert out.recalled[0].paper_id == "p1"
        assert out.survey.citations[0].index == 1

import pytest
from learn_wiki.extract.base import validate_extraction
from learn_wiki.extract.fake import FakeExtractor
from learn_wiki.models import SourceDocument, Extraction, ExtractedNode
from learn_wiki.errors import ExtractionError


def test_validate_good_payload():
    raw = {
        "nodes": [{"type": "Concept", "name": "A", "description": "d"}],
        "edges": [{"source_name": "A", "target_name": "A", "type": "requires", "quote": "q"}],
    }
    ex = validate_extraction(raw)
    assert ex.nodes[0].name == "A"
    assert ex.edges[0].quote == "q"


def test_validate_rejects_edge_without_quote():
    raw = {
        "nodes": [{"type": "Concept", "name": "A", "description": "d"}],
        "edges": [{"source_name": "A", "target_name": "A", "type": "requires", "quote": ""}],
    }
    with pytest.raises(ExtractionError):
        validate_extraction(raw)


def test_validate_rejects_missing_field():
    with pytest.raises(ExtractionError):
        validate_extraction({"nodes": [{"name": "A"}], "edges": []})


def test_fake_extractor_returns_canned():
    canned = Extraction(nodes=[ExtractedNode("Concept", "A", "d")], edges=[])
    fake = FakeExtractor(canned)
    out = fake.extract(SourceDocument("u", "web", "t", "body"))
    assert out is canned

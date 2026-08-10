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


def test_validate_rejects_non_string_quote():
    """Regression: non-string quote (e.g. 123) must raise ExtractionError."""
    raw = {
        "nodes": [{"type": "Concept", "name": "A", "description": "d"}],
        "edges": [{"source_name": "A", "target_name": "A", "type": "requires", "quote": 123}],
    }
    with pytest.raises(ExtractionError):
        validate_extraction(raw)


def test_validate_accepts_node_without_description():
    """Regression: node without description is optional and defaults to empty string."""
    raw = {
        "nodes": [{"type": "Concept", "name": "A"}],
        "edges": [],
    }
    ex = validate_extraction(raw)
    assert ex.nodes[0].name == "A"
    assert ex.nodes[0].description == ""


def test_validate_rejects_node_missing_type():
    """Regression: node missing required type field must raise ExtractionError."""
    raw = {
        "nodes": [{"name": "A", "description": "d"}],
        "edges": [],
    }
    with pytest.raises(ExtractionError):
        validate_extraction(raw)


def test_validate_rejects_node_missing_name():
    """Regression: node missing required name field must raise ExtractionError."""
    raw = {
        "nodes": [{"type": "Concept", "description": "d"}],
        "edges": [],
    }
    with pytest.raises(ExtractionError):
        validate_extraction(raw)

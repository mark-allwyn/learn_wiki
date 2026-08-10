import pytest
from learn_wiki.extract.claude import build_prompt, parse_response
from learn_wiki.models import SourceDocument
from learn_wiki.errors import ExtractionError


def test_build_prompt_includes_ontology_and_text():
    doc = SourceDocument("u", "web", "Title", "Chunking improves context use.")
    p = build_prompt(doc)
    assert "Technique" in p          # a starter node type
    assert "improves" in p           # a starter edge type
    assert "Chunking improves" in p  # the source text


def test_parse_response_extracts_json_block():
    reply = 'Here is the graph:\n{"nodes": [{"type":"Concept","name":"A","description":"d"}], "edges": []}\nDone.'
    ex = parse_response(reply)
    assert ex.nodes[0].name == "A"


def test_parse_response_raises_without_json():
    with pytest.raises(ExtractionError):
        parse_response("no json here")

import pytest
from learn_wiki.graph.store import GraphStore
from learn_wiki.models import SourceDocument, ExtractedNode, ExtractedEdge, Extraction
from learn_wiki.errors import ExtractionError


def make_store():
    store = GraphStore(":memory:")
    store.init_schema()
    return store


def test_upsert_and_get_graph():
    store = make_store()
    sid = store.upsert_source(SourceDocument("https://x", "web", "T", "text"))
    ex = Extraction(
        nodes=[ExtractedNode("Concept", "Context window", "d1"),
               ExtractedNode("Technique", "Chunking", "d2")],
        edges=[ExtractedEdge("Chunking", "Context window", "improves", "chunking improves it")],
    )
    store.upsert_extraction(sid, ex)
    g = store.get_graph()
    assert len(g["nodes"]) == 2
    assert len(g["edges"]) == 1
    assert g["edges"][0]["quote"] == "chunking improves it"


def test_reingest_same_url_does_not_duplicate():
    store = make_store()
    doc = SourceDocument("https://x", "web", "T", "text")
    sid1 = store.upsert_source(doc)
    store.upsert_extraction(sid1, Extraction(
        nodes=[ExtractedNode("Concept", "A", "d")], edges=[]))
    sid2 = store.upsert_source(doc)  # same url again
    store.upsert_extraction(sid2, Extraction(
        nodes=[ExtractedNode("Concept", "A", "d")], edges=[]))
    assert sid1 == sid2
    g = store.get_graph()
    assert len(g["nodes"]) == 1  # node A not duplicated


def test_reingest_replaces_that_sources_edges():
    store = make_store()
    doc = SourceDocument("https://x", "web", "T", "text")
    sid = store.upsert_source(doc)
    store.upsert_extraction(sid, Extraction(
        nodes=[ExtractedNode("Concept", "A", "d"), ExtractedNode("Concept", "B", "d")],
        edges=[ExtractedEdge("A", "B", "improves", "q1")]))
    sid = store.upsert_source(doc)
    store.upsert_extraction(sid, Extraction(
        nodes=[ExtractedNode("Concept", "A", "d"), ExtractedNode("Concept", "B", "d")],
        edges=[ExtractedEdge("A", "B", "requires", "q2")]))
    g = store.get_graph()
    assert len(g["edges"]) == 1
    assert g["edges"][0]["type"] == "requires"


def test_same_name_different_type_raises_extraction_error():
    """Same node name with different types in one extraction is an error - nothing fails silently."""
    store = make_store()
    sid = store.upsert_source(SourceDocument("https://x", "web", "T", "text"))
    # Try to upsert extraction with same name "A" but two different types
    with pytest.raises(ExtractionError):
        store.upsert_extraction(sid, Extraction(
            nodes=[ExtractedNode("Concept", "A", "d1"),
                   ExtractedNode("Technique", "A", "d2")],
            edges=[],
        ))


def test_empty_quote_raises_error():
    """Edge quotes must be non-empty - nothing fails silently."""
    store = make_store()
    sid = store.upsert_source(SourceDocument("https://x", "web", "T", "text"))
    # Empty string quote should raise
    with pytest.raises(Exception):  # Could be ExtractionError or sqlite3.IntegrityError
        store.upsert_extraction(sid, Extraction(
            nodes=[ExtractedNode("Concept", "A", "d"),
                   ExtractedNode("Concept", "B", "d")],
            edges=[ExtractedEdge("A", "B", "improves", "")],
        ))


def test_whitespace_only_quote_raises_error():
    """Edge quotes must be non-empty (whitespace-only is considered empty)."""
    store = make_store()
    sid = store.upsert_source(SourceDocument("https://x", "web", "T", "text"))
    # Whitespace-only quote should also raise
    with pytest.raises(Exception):
        store.upsert_extraction(sid, Extraction(
            nodes=[ExtractedNode("Concept", "A", "d"),
                   ExtractedNode("Concept", "B", "d")],
            edges=[ExtractedEdge("A", "B", "improves", "   ")],
        ))

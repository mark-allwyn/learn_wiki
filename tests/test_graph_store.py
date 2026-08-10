from learn_wiki.graph.store import GraphStore
from learn_wiki.models import SourceDocument, ExtractedNode, ExtractedEdge, Extraction


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

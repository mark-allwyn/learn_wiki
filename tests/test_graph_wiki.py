from learn_wiki.graph.store import GraphStore
from learn_wiki.models import SourceDocument, ExtractedNode, ExtractedEdge, Extraction


def build_store():
    store = GraphStore(":memory:")
    store.init_schema()
    sid = store.upsert_source(SourceDocument("https://src.example/a", "web", "Source A", "text"))
    store.upsert_extraction(sid, Extraction(
        nodes=[ExtractedNode("Concept", "Context window", "how much a model sees"),
               ExtractedNode("Technique", "Chunking", "splitting text"),
               ExtractedNode("Technique", "Summarizing", "condensing text")],
        edges=[ExtractedEdge("Chunking", "Context window", "improves", "chunking improves context use"),
               ExtractedEdge("Summarizing", "Context window", "improves", "summarizing improves it too")],
    ))
    return store


def test_list_entities_with_degree():
    store = build_store()
    ents = store.list_entities()
    by_name = {e["name"]: e for e in ents}
    assert by_name["Context window"]["degree"] == 2   # two edges point at it
    assert by_name["Chunking"]["degree"] == 1
    assert by_name["Chunking"]["type"] == "Technique"
    # ordered by (type, name)
    assert [e["name"] for e in ents] == ["Context window", "Chunking", "Summarizing"]


def test_entity_detail_relationships_and_sources():
    store = build_store()
    ents = {e["name"]: e for e in store.list_entities()}
    detail = store.entity_detail(ents["Context window"]["id"])
    assert detail["node"]["name"] == "Context window"
    assert len(detail["relationships"]) == 2
    rel = detail["relationships"][0]
    assert rel["direction"] == "in"                 # Context window is the target
    assert rel["type"] == "improves"
    assert rel["other"]["name"] in {"Chunking", "Summarizing"}
    assert rel["quote"]                              # provenance present
    assert rel["source_url"] == "https://src.example/a"
    assert rel["source_title"] == "Source A"
    assert detail["sources"] == [{"url": "https://src.example/a", "title": "Source A"}]


def test_entity_detail_out_direction():
    store = build_store()
    ents = {e["name"]: e for e in store.list_entities()}
    detail = store.entity_detail(ents["Chunking"]["id"])
    assert len(detail["relationships"]) == 1
    assert detail["relationships"][0]["direction"] == "out"   # Chunking is the source
    assert detail["relationships"][0]["other"]["name"] == "Context window"


def test_entity_detail_missing_returns_none():
    store = build_store()
    assert store.entity_detail(99999) is None

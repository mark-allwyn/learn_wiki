from fastapi.testclient import TestClient
from learn_wiki.web.app import create_app
from learn_wiki.graph.store import GraphStore
from learn_wiki.extract.fake import FakeExtractor
from learn_wiki.models import SourceDocument, Extraction, ExtractedNode, ExtractedEdge


def build_client():
    store = GraphStore(":memory:")
    store.init_schema()
    sid = store.upsert_source(SourceDocument("https://src.example/a", "web", "Source A", "t"))
    store.upsert_extraction(sid, Extraction(
        nodes=[ExtractedNode("Concept", "Context window", "d"),
               ExtractedNode("Technique", "Chunking", "d")],
        edges=[ExtractedEdge("Chunking", "Context window", "improves", "chunking improves it")],
    ))
    app = create_app(store, FakeExtractor(Extraction([], [])))
    return TestClient(app), store


def test_api_entities():
    client, _ = build_client()
    r = client.get("/api/entities")
    assert r.status_code == 200
    names = {e["name"] for e in r.json()}
    assert names == {"Context window", "Chunking"}


def test_api_entity_detail_and_404():
    client, store = build_client()
    eid = next(e["id"] for e in store.list_entities() if e["name"] == "Context window")
    r = client.get(f"/api/entity/{eid}")
    assert r.status_code == 200
    body = r.json()
    assert body["node"]["name"] == "Context window"
    assert body["relationships"][0]["quote"] == "chunking improves it"

    missing = client.get("/api/entity/99999")
    assert missing.status_code == 404
    assert "error" in missing.json()


def test_index_includes_nav():
    client, _ = build_client()
    r = client.get("/")
    assert r.status_code == 200
    assert "/static/nav.js" in r.text
    assert 'id="nav"' in r.text

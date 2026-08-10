from fastapi.testclient import TestClient
from learn_wiki.web.app import create_app
from learn_wiki.graph.store import GraphStore
from learn_wiki.extract.fake import FakeExtractor
from learn_wiki.models import SourceDocument, Extraction, ExtractedNode, ExtractedEdge


def build_client():
    store = GraphStore(":memory:")
    store.init_schema()
    extraction = Extraction(
        nodes=[ExtractedNode("Technique", "Chunking", "d"),
               ExtractedNode("Concept", "Context window", "d")],
        edges=[ExtractedEdge("Chunking", "Context window", "improves", "chunking improves it")],
    )
    extractor = FakeExtractor(extraction)
    fake_ingest = lambda url: SourceDocument(url, "web", "T", "body text")
    app = create_app(store, extractor, ingest_fn=fake_ingest)
    return TestClient(app)


def test_ingest_then_graph():
    client = build_client()
    r = client.post("/ingest", json={"url": "https://blog.example/p"})
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "nodes": 2, "edges": 1}

    g = client.get("/graph").json()
    assert len(g["nodes"]) == 2
    assert g["edges"][0]["quote"] == "chunking improves it"


def test_ingest_error_returns_422():
    store = GraphStore(":memory:")
    store.init_schema()
    from learn_wiki.errors import IngestError

    def boom(url):
        raise IngestError("dead link")

    app = create_app(store, FakeExtractor(Extraction([], [])), ingest_fn=boom)
    client = TestClient(app)
    r = client.post("/ingest", json={"url": "https://x"})
    assert r.status_code == 422
    assert "dead link" in r.json()["error"]

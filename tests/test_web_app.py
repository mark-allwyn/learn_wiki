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
    fake_ingest = lambda url, prefer_captions=False: SourceDocument(url, "web", "T", "body text")
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


def test_logs_endpoint_captures_ingest_lines():
    client = build_client()
    before = client.get("/logs").json()
    assert "seq" in before and "lines" in before
    client.post("/ingest", json={"url": "https://blog.example/p"})
    after = client.get("/logs", params={"after": before["seq"]}).json()
    joined = "\n".join(after["lines"])
    assert "ingest:" in joined
    assert "START" in joined and "DONE" in joined


def test_ingest_error_returns_422():
    store = GraphStore(":memory:")
    store.init_schema()
    from learn_wiki.errors import IngestError

    def boom(url, prefer_captions=False):
        raise IngestError("dead link")

    app = create_app(store, FakeExtractor(Extraction([], [])), ingest_fn=boom)
    client = TestClient(app)
    r = client.post("/ingest", json={"url": "https://x"})
    assert r.status_code == 422
    assert "dead link" in r.json()["error"]


def test_store_collision_error_returns_422():
    """Same node name with different types in extraction should return 422, not 500."""
    store = GraphStore(":memory:")
    store.init_schema()

    # Extraction with same name but different types - will raise ExtractionError in store
    extraction = Extraction(
        nodes=[ExtractedNode("Concept", "A", "d1"),
               ExtractedNode("Technique", "A", "d2")],
        edges=[],
    )
    extractor = FakeExtractor(extraction)
    fake_ingest = lambda url, prefer_captions=False: SourceDocument(url, "web", "T", "body text")
    app = create_app(store, extractor, ingest_fn=fake_ingest)
    client = TestClient(app)

    r = client.post("/ingest", json={"url": "https://x"})
    assert r.status_code == 422
    assert "error" in r.json()
    assert "collision" in r.json()["error"].lower()


def test_non_string_url_returns_422():
    """Non-string or null URL should return 422, not 500."""
    client = build_client()

    # Test with null URL
    r = client.post("/ingest", json={"url": None})
    assert r.status_code == 422
    assert "error" in r.json()

    # Test with number URL
    r = client.post("/ingest", json={"url": 123})
    assert r.status_code == 422
    assert "error" in r.json()


def test_empty_url_returns_422():
    """Empty string URL should return 422."""
    client = build_client()
    r = client.post("/ingest", json={"url": ""})
    assert r.status_code == 422
    assert "error" in r.json()


def test_fast_flag_threaded_as_prefer_captions():
    """The page's 'fast' flag reaches ingest as prefer_captions."""
    store = GraphStore(":memory:")
    store.init_schema()
    seen = {}

    def rec_ingest(url, prefer_captions=False):
        seen["prefer_captions"] = prefer_captions
        return SourceDocument(url, "video", "T", "body")

    app = create_app(store, FakeExtractor(Extraction([], [])), ingest_fn=rec_ingest)
    client = TestClient(app)
    client.post("/ingest", json={"url": "https://youtu.be/x", "fast": True})
    assert seen["prefer_captions"] is True
    client.post("/ingest", json={"url": "https://youtu.be/x", "fast": False})
    assert seen["prefer_captions"] is False

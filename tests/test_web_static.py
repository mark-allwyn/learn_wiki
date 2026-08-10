from fastapi.testclient import TestClient
from learn_wiki.web.app import create_app
from learn_wiki.graph.store import GraphStore
from learn_wiki.extract.fake import FakeExtractor
from learn_wiki.models import Extraction


def test_index_served_and_references_graph_lib():
    store = GraphStore(":memory:")
    store.init_schema()
    app = create_app(store, FakeExtractor(Extraction([], [])))
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "forcegraph3d" in r.text.lower()  # 3D graph library
    assert "/graph" in r.text  # the page fetches the graph endpoint
    assert "/logs" in r.text  # the page polls the log endpoint

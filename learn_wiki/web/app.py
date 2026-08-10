from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from learn_wiki.graph.store import GraphStore
from learn_wiki.extract.base import Extractor
from learn_wiki.ingest import ingest as default_ingest
from learn_wiki.errors import LearnWikiError

_STATIC = Path(__file__).parent / "static"


def create_app(store: GraphStore, extractor: Extractor, ingest_fn=default_ingest) -> FastAPI:
    app = FastAPI()

    @app.post("/ingest")
    def ingest_endpoint(body: dict):
        url = body.get("url", "").strip()
        if not url:
            return JSONResponse({"error": "no url provided"}, status_code=422)
        try:
            doc = ingest_fn(url)
            extraction = extractor.extract(doc)
        except LearnWikiError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        source_id = store.upsert_source(doc)
        store.upsert_extraction(source_id, extraction)
        return {"status": "ok", "nodes": len(extraction.nodes), "edges": len(extraction.edges)}

    @app.get("/graph")
    def graph_endpoint():
        return store.get_graph()

    @app.get("/")
    def index():
        return FileResponse(_STATIC / "index.html")

    return app

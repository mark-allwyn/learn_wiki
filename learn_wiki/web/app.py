import collections
import logging
import time
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from learn_wiki.graph.store import GraphStore
from learn_wiki.extract.base import Extractor
from learn_wiki.ingest import ingest as default_ingest
from learn_wiki.errors import LearnWikiError

_STATIC = Path(__file__).parent / "static"
logger = logging.getLogger("uvicorn.error")

# In-memory ring buffer of ingest log lines, exposed via GET /logs so the
# browser can show live progress. Attached once at import (not per create_app).
_LOG_BUFFER: collections.deque = collections.deque(maxlen=300)
_log_seq = 0


class _BufferLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        global _log_seq
        if "ingest:" not in record.getMessage():
            return
        _log_seq += 1
        _LOG_BUFFER.append({"seq": _log_seq, "line": self.format(record)})


_buffer_handler = _BufferLogHandler()
_buffer_handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))


def _attach_buffer_handler() -> None:
    # uvicorn reconfigures the uvicorn.error logger when the server starts,
    # which drops any handler added at import time. Attach idempotently both at
    # import (for TestClient, which never runs uvicorn's logging setup) and
    # again on app startup (after uvicorn has configured logging) so ingest
    # lines are captured in every run mode.
    if _buffer_handler not in logger.handlers:
        logger.addHandler(_buffer_handler)
    if logger.level == logging.NOTSET or logger.level > logging.INFO:
        logger.setLevel(logging.INFO)


_attach_buffer_handler()


def create_app(store: GraphStore, extractor: Extractor, ingest_fn=default_ingest) -> FastAPI:
    app = FastAPI()

    @app.post("/ingest")
    def ingest_endpoint(body: dict):
        # Re-attach the log buffer here (idempotent) - uvicorn's startup logging
        # config drops import-time handlers, and this runs after that, before the
        # first ingest line is logged.
        _attach_buffer_handler()
        url_raw = body.get("url", "")
        if not isinstance(url_raw, str):
            return JSONResponse({"error": "url must be a string"}, status_code=422)
        url = url_raw.strip()
        if not url:
            return JSONResponse({"error": "no url provided"}, status_code=422)
        t0 = time.monotonic()
        logger.info("ingest: START %s", url)
        try:
            doc = ingest_fn(url)
            t1 = time.monotonic()
            logger.info(
                "ingest: fetched [%s] '%s' (%d chars) in %.1fs",
                doc.source_type, doc.title, len(doc.text), t1 - t0,
            )
            extraction = extractor.extract(doc)
            t2 = time.monotonic()
            logger.info(
                "ingest: extracted %d nodes, %d edges in %.1fs (Claude)",
                len(extraction.nodes), len(extraction.edges), t2 - t1,
            )
            source_id = store.upsert_source(doc)
            store.upsert_extraction(source_id, extraction)
            t3 = time.monotonic()
            logger.info(
                "ingest: stored in %.2fs -- DONE total %.1fs (%s)",
                t3 - t2, t3 - t0, url,
            )
        except LearnWikiError as exc:
            logger.warning("ingest: FAILED %s -- %s", url, exc)
            return JSONResponse({"error": str(exc)}, status_code=422)
        return {"status": "ok", "nodes": len(extraction.nodes), "edges": len(extraction.edges)}

    @app.get("/graph")
    def graph_endpoint():
        return store.get_graph()

    @app.get("/logs")
    def logs_endpoint(after: int = 0):
        entries = [e for e in list(_LOG_BUFFER) if e["seq"] > after]
        latest = _LOG_BUFFER[-1]["seq"] if _LOG_BUFFER else after
        return {"seq": latest, "lines": [e["line"] for e in entries]}

    @app.get("/")
    def index():
        return FileResponse(_STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

    return app

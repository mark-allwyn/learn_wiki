# Knowledge-Graph Wiki - Slice 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Paste a URL (web page or video), extract a typed entity graph with citations, store it, and see it as an interactive diagram in a local browser.

**Architecture:** Four modules with small explicit interfaces - `ingest` (URL to clean text), `extract` (text to entities/relations behind a swappable `Extractor` interface), `graph` (SQLite storage and queries), `web` (FastAPI + one static Cytoscape.js page). Data flows one way: ingest -> extract -> store -> render. The LLM sits behind `Extractor` so unit tests run with a `FakeExtractor` and never touch the network.

**Tech Stack:** Python 3.11+, `httpx` + `trafilatura` (web), `yt-dlp` + `faster-whisper` (video, local Whisper), `youtube-transcript-api` (optional caption fallback), stdlib `sqlite3` (no ORM), `claude-agent-sdk` (extraction on the Claude subscription), `FastAPI` + `uvicorn`, Cytoscape.js (vendored, no build step), `pytest`.

## Global Constraints

- Python 3.11 or newer.
- Lean and fast: only the dependencies named in the Tech Stack. No ORM, no frontend framework, no build step, no extra abstraction layers.
- Every edge stores a provenance `quote` (the source sentence it came from). An edge without a quote is invalid.
- The LLM is only ever called through the `Extractor` interface. Unit tests use `FakeExtractor` and must not hit the network or the Claude subscription.
- Ingestion is idempotent: re-ingesting the same URL updates its source and reconciles its nodes/edges, never duplicates.
- Nothing fails silently. Fetch, transcription, and validation failures raise clear, typed errors.
- `ffmpeg` is a system dependency for the video path.
- No em dash characters anywhere; use a plain dash.

---

## File Structure

```
learn_wiki/
├── pyproject.toml                 # deps + pytest config
├── learn_wiki/
│   ├── __init__.py
│   ├── models.py                  # dataclasses: SourceDocument, ExtractedNode, ExtractedEdge, Extraction
│   ├── ontology.py                # starter node/edge type lists
│   ├── errors.py                  # typed errors (IngestError, ExtractionError)
│   ├── ingest/
│   │   ├── __init__.py            # ingest(url) dispatch + is_video_url
│   │   ├── web.py                 # fetch_web(url)
│   │   └── video.py               # transcribe_video(url), caption fallback, injectable seams
│   ├── extract/
│   │   ├── __init__.py
│   │   ├── base.py                # Extractor Protocol + validate_extraction
│   │   ├── fake.py                # FakeExtractor
│   │   └── claude.py              # ClaudeExtractor (claude-agent-sdk)
│   ├── graph/
│   │   ├── __init__.py
│   │   └── store.py               # GraphStore (SQLite)
│   └── web/
│       ├── __init__.py
│       ├── app.py                 # create_app(store, extractor) -> FastAPI
│       └── static/
│           └── index.html         # Cytoscape.js page (vendored lib)
└── tests/
    ├── conftest.py
    ├── test_models.py
    ├── test_graph_store.py
    ├── test_extract.py
    ├── test_ingest_web.py
    ├── test_ingest_video.py
    ├── test_ingest_dispatch.py
    ├── test_web_app.py
    └── smoke/
        ├── test_claude_extractor.py   # live, run deliberately
        └── test_video_transcribe.py   # live, run deliberately
```

---

## Task 1: Project scaffold, models, ontology, errors

**Files:**
- Create: `pyproject.toml`, `learn_wiki/__init__.py`, `learn_wiki/models.py`, `learn_wiki/ontology.py`, `learn_wiki/errors.py`
- Test: `tests/test_models.py`, `tests/conftest.py`

**Interfaces:**
- Produces:
  - `SourceDocument(url: str, source_type: str, title: str, text: str)` - frozen dataclass. `source_type` is `"web"` or `"video"`.
  - `ExtractedNode(type: str, name: str, description: str)` - frozen dataclass.
  - `ExtractedEdge(source_name: str, target_name: str, type: str, quote: str)` - frozen dataclass; `source_name`/`target_name` reference `ExtractedNode.name`.
  - `Extraction(nodes: list[ExtractedNode], edges: list[ExtractedEdge], proposed_node_types: list[str], proposed_edge_types: list[str])` - frozen dataclass; the two `proposed_*` lists default to empty.
  - `ontology.NODE_TYPES: list[str]`, `ontology.EDGE_TYPES: list[str]`.
  - `errors.IngestError`, `errors.ExtractionError` (both subclass a base `LearnWikiError(Exception)`).

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "learn_wiki"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "httpx",
    "trafilatura",
    "yt-dlp",
    "faster-whisper",
    "youtube-transcript-api",
    "claude-agent-sdk",
    "fastapi",
    "uvicorn",
    "networkx",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--ignore=tests/smoke"
asyncio_mode = "auto"
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_models.py
from learn_wiki.models import SourceDocument, ExtractedNode, ExtractedEdge, Extraction
from learn_wiki import ontology


def test_source_document_fields():
    doc = SourceDocument(url="https://x.com", source_type="web", title="T", text="body")
    assert doc.source_type == "web"


def test_extraction_defaults_empty_proposals():
    ex = Extraction(nodes=[ExtractedNode("Concept", "Context window", "d")], edges=[])
    assert ex.proposed_node_types == []
    assert ex.proposed_edge_types == []


def test_edge_carries_quote():
    edge = ExtractedEdge("A", "B", "improves", "A improves B because ...")
    assert edge.quote


def test_ontology_has_starter_types():
    assert "Technique" in ontology.NODE_TYPES
    assert "contradicts" in ontology.EDGE_TYPES
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'learn_wiki.models'`

- [ ] **Step 4: Write the implementation**

```python
# learn_wiki/__init__.py
# (empty)
```

```python
# learn_wiki/models.py
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceDocument:
    url: str
    source_type: str  # "web" | "video"
    title: str
    text: str


@dataclass(frozen=True)
class ExtractedNode:
    type: str
    name: str
    description: str


@dataclass(frozen=True)
class ExtractedEdge:
    source_name: str
    target_name: str
    type: str
    quote: str


@dataclass(frozen=True)
class Extraction:
    nodes: list[ExtractedNode]
    edges: list[ExtractedEdge]
    proposed_node_types: list[str] = field(default_factory=list)
    proposed_edge_types: list[str] = field(default_factory=list)
```

```python
# learn_wiki/ontology.py
NODE_TYPES = ["Technique", "Concept", "Model", "Tool", "Person", "Pattern", "Pitfall"]
EDGE_TYPES = ["improves", "contradicts", "requires", "part-of", "alternative-to", "used-with"]
```

```python
# learn_wiki/errors.py
class LearnWikiError(Exception):
    """Base error for the project."""


class IngestError(LearnWikiError):
    """Fetching or transcribing a source failed."""


class ExtractionError(LearnWikiError):
    """The LLM returned output that could not be validated."""
```

```python
# tests/conftest.py
# (empty for now; shared fixtures added in later tasks)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml learn_wiki/ tests/
git commit -m "feat: project scaffold, models, ontology, errors"
```

---

## Task 2: Graph store (SQLite)

**Files:**
- Create: `learn_wiki/graph/__init__.py`, `learn_wiki/graph/store.py`
- Test: `tests/test_graph_store.py`

**Interfaces:**
- Consumes: `SourceDocument`, `Extraction`, `ExtractedNode`, `ExtractedEdge` (Task 1); `ontology.NODE_TYPES`, `ontology.EDGE_TYPES` (Task 1).
- Produces:
  - `GraphStore(path: str)` - `path` is a file path or `":memory:"`.
  - `store.init_schema() -> None` - creates tables and seeds ontology; safe to call repeatedly.
  - `store.upsert_source(doc: SourceDocument) -> int` - returns the source row id; re-ingesting the same URL updates in place and removes that source's prior edges.
  - `store.upsert_extraction(source_id: int, extraction: Extraction) -> None` - upserts nodes by `(type, name)`, inserts edges tagged with `source_id`, and records any proposed types as pending.
  - `store.get_graph() -> dict` - returns `{"nodes": [{"id","type","name","description"}], "edges": [{"source","target","type","quote"}]}` (Cytoscape-ready shape).
  - `store.close() -> None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_graph_store.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_graph_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'learn_wiki.graph.store'`

- [ ] **Step 3: Write the implementation**

```python
# learn_wiki/graph/__init__.py
# (empty)
```

```python
# learn_wiki/graph/store.py
import sqlite3
from learn_wiki.models import SourceDocument, Extraction
from learn_wiki import ontology

_SCHEMA = """
CREATE TABLE IF NOT EXISTS node_types (name TEXT PRIMARY KEY, pending INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS edge_types (name TEXT PRIMARY KEY, pending INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,
    title TEXT,
    fetched_at TEXT DEFAULT (datetime('now')),
    raw_text TEXT
);
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    UNIQUE(type, name)
);
CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY,
    source_node INTEGER NOT NULL REFERENCES nodes(id),
    target_node INTEGER NOT NULL REFERENCES nodes(id),
    type TEXT NOT NULL,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    quote TEXT NOT NULL
);
"""


class GraphStore:
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    def init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        for t in ontology.NODE_TYPES:
            self._conn.execute("INSERT OR IGNORE INTO node_types(name, pending) VALUES (?, 0)", (t,))
        for t in ontology.EDGE_TYPES:
            self._conn.execute("INSERT OR IGNORE INTO edge_types(name, pending) VALUES (?, 0)", (t,))
        self._conn.commit()

    def upsert_source(self, doc: SourceDocument) -> int:
        cur = self._conn.execute(
            """INSERT INTO sources(url, type, title, raw_text) VALUES (?, ?, ?, ?)
               ON CONFLICT(url) DO UPDATE SET
                   type=excluded.type, title=excluded.title, raw_text=excluded.raw_text,
                   fetched_at=datetime('now')
               RETURNING id""",
            (doc.url, doc.source_type, doc.title, doc.text),
        )
        source_id = cur.fetchone()["id"]
        # Idempotency: drop this source's prior edges before re-adding.
        self._conn.execute("DELETE FROM edges WHERE source_id = ?", (source_id,))
        self._conn.commit()
        return source_id

    def _node_id(self, type_: str, name: str, description: str) -> int:
        cur = self._conn.execute(
            """INSERT INTO nodes(type, name, description) VALUES (?, ?, ?)
               ON CONFLICT(type, name) DO UPDATE SET description=excluded.description
               RETURNING id""",
            (type_, name, description),
        )
        return cur.fetchone()["id"]

    def upsert_extraction(self, source_id: int, extraction: Extraction) -> None:
        ids: dict[str, int] = {}
        for n in extraction.nodes:
            ids[n.name] = self._node_id(n.type, n.name, n.description)
        for e in extraction.edges:
            src = ids.get(e.source_name) or self._node_id("Concept", e.source_name, "")
            tgt = ids.get(e.target_name) or self._node_id("Concept", e.target_name, "")
            self._conn.execute(
                "INSERT INTO edges(source_node, target_node, type, source_id, quote) VALUES (?, ?, ?, ?, ?)",
                (src, tgt, e.type, source_id, e.quote),
            )
        for t in extraction.proposed_node_types:
            self._conn.execute("INSERT OR IGNORE INTO node_types(name, pending) VALUES (?, 1)", (t,))
        for t in extraction.proposed_edge_types:
            self._conn.execute("INSERT OR IGNORE INTO edge_types(name, pending) VALUES (?, 1)", (t,))
        self._conn.commit()

    def get_graph(self) -> dict:
        nodes = [
            {"id": r["id"], "type": r["type"], "name": r["name"], "description": r["description"]}
            for r in self._conn.execute("SELECT id, type, name, description FROM nodes")
        ]
        edges = [
            {"source": r["source_node"], "target": r["target_node"], "type": r["type"], "quote": r["quote"]}
            for r in self._conn.execute("SELECT source_node, target_node, type, quote FROM edges")
        ]
        return {"nodes": nodes, "edges": edges}

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_graph_store.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add learn_wiki/graph/ tests/test_graph_store.py
git commit -m "feat: SQLite graph store with idempotent upserts"
```

---

## Task 3: Extractor interface, validation, FakeExtractor

**Files:**
- Create: `learn_wiki/extract/__init__.py`, `learn_wiki/extract/base.py`, `learn_wiki/extract/fake.py`
- Test: `tests/test_extract.py`

**Interfaces:**
- Consumes: `SourceDocument`, `Extraction`, `ExtractedNode`, `ExtractedEdge`, `ExtractionError` (Task 1).
- Produces:
  - `Extractor` (typing.Protocol) with `extract(self, doc: SourceDocument) -> Extraction`.
  - `validate_extraction(raw: dict) -> Extraction` - parses a raw dict (as returned by an LLM) into an `Extraction`, raising `ExtractionError` on any missing field or on an edge without a non-empty `quote`.
  - `FakeExtractor(result: Extraction)` - returns the given `Extraction` from `extract()`, ignoring the document. Used by all non-LLM tests.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_extract.py
import pytest
from learn_wiki.extract.base import validate_extraction
from learn_wiki.extract.fake import FakeExtractor
from learn_wiki.models import SourceDocument, Extraction, ExtractedNode
from learn_wiki.errors import ExtractionError


def test_validate_good_payload():
    raw = {
        "nodes": [{"type": "Concept", "name": "A", "description": "d"}],
        "edges": [{"source_name": "A", "target_name": "A", "type": "requires", "quote": "q"}],
    }
    ex = validate_extraction(raw)
    assert ex.nodes[0].name == "A"
    assert ex.edges[0].quote == "q"


def test_validate_rejects_edge_without_quote():
    raw = {
        "nodes": [{"type": "Concept", "name": "A", "description": "d"}],
        "edges": [{"source_name": "A", "target_name": "A", "type": "requires", "quote": ""}],
    }
    with pytest.raises(ExtractionError):
        validate_extraction(raw)


def test_validate_rejects_missing_field():
    with pytest.raises(ExtractionError):
        validate_extraction({"nodes": [{"name": "A"}], "edges": []})


def test_fake_extractor_returns_canned():
    canned = Extraction(nodes=[ExtractedNode("Concept", "A", "d")], edges=[])
    fake = FakeExtractor(canned)
    out = fake.extract(SourceDocument("u", "web", "t", "body"))
    assert out is canned
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'learn_wiki.extract.base'`

- [ ] **Step 3: Write the implementation**

```python
# learn_wiki/extract/__init__.py
# (empty)
```

```python
# learn_wiki/extract/base.py
from typing import Protocol
from learn_wiki.models import SourceDocument, Extraction, ExtractedNode, ExtractedEdge
from learn_wiki.errors import ExtractionError


class Extractor(Protocol):
    def extract(self, doc: SourceDocument) -> Extraction: ...


def validate_extraction(raw: dict) -> Extraction:
    try:
        nodes = [
            ExtractedNode(type=n["type"], name=n["name"], description=n.get("description", ""))
            for n in raw["nodes"]
        ]
        edges = []
        for e in raw["edges"]:
            quote = e["quote"]
            if not quote or not quote.strip():
                raise ExtractionError(f"edge {e.get('source_name')}->{e.get('target_name')} has no quote")
            edges.append(ExtractedEdge(
                source_name=e["source_name"], target_name=e["target_name"],
                type=e["type"], quote=quote))
    except (KeyError, TypeError) as exc:
        raise ExtractionError(f"malformed extraction payload: {exc}") from exc
    return Extraction(
        nodes=nodes,
        edges=edges,
        proposed_node_types=list(raw.get("proposed_node_types", [])),
        proposed_edge_types=list(raw.get("proposed_edge_types", [])),
    )
```

```python
# learn_wiki/extract/fake.py
from learn_wiki.models import SourceDocument, Extraction


class FakeExtractor:
    def __init__(self, result: Extraction):
        self._result = result

    def extract(self, doc: SourceDocument) -> Extraction:
        return self._result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_extract.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add learn_wiki/extract/ tests/test_extract.py
git commit -m "feat: Extractor interface, payload validation, FakeExtractor"
```

---

## Task 4: Web ingest

**Files:**
- Create: `learn_wiki/ingest/__init__.py` (empty for now), `learn_wiki/ingest/web.py`
- Test: `tests/test_ingest_web.py`

**Interfaces:**
- Consumes: `SourceDocument`, `IngestError` (Task 1).
- Produces:
  - `fetch_web(url: str, *, fetch=None) -> SourceDocument` with `source_type="web"`. `fetch` is an injectable seam: a callable `(url) -> str` returning raw HTML (defaults to an `httpx` GET). Raises `IngestError` if the page cannot be fetched or no readable text is extracted.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest_web.py
import pytest
from learn_wiki.ingest.web import fetch_web
from learn_wiki.errors import IngestError

HTML = """
<html><head><title>My Post</title></head>
<body><article><h1>Context Windows</h1>
<p>A context window is the amount of text a model can attend to at once.
Chunking improves how much relevant content fits.</p></article></body></html>
"""


def test_fetch_web_extracts_title_and_text():
    doc = fetch_web("https://blog.example/post", fetch=lambda url: HTML)
    assert doc.source_type == "web"
    assert doc.url == "https://blog.example/post"
    assert "context window" in doc.text.lower()


def test_fetch_web_raises_on_empty_content():
    with pytest.raises(IngestError):
        fetch_web("https://blog.example/empty", fetch=lambda url: "<html></html>")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingest_web.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'learn_wiki.ingest.web'`

- [ ] **Step 3: Write the implementation**

```python
# learn_wiki/ingest/__init__.py
# (dispatch added in Task 6)
```

```python
# learn_wiki/ingest/web.py
import httpx
import trafilatura
from learn_wiki.models import SourceDocument
from learn_wiki.errors import IngestError


def _http_get(url: str) -> str:
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=30.0)
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPError as exc:
        raise IngestError(f"could not fetch {url}: {exc}") from exc


def fetch_web(url: str, *, fetch=None) -> SourceDocument:
    fetch = fetch or _http_get
    html = fetch(url)
    text = trafilatura.extract(html) or ""
    if not text.strip():
        raise IngestError(f"no readable content extracted from {url}")
    meta = trafilatura.extract_metadata(html)
    title = (meta.title if meta and meta.title else url)
    return SourceDocument(url=url, source_type="web", title=title, text=text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ingest_web.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add learn_wiki/ingest/ tests/test_ingest_web.py
git commit -m "feat: web ingest via httpx + trafilatura"
```

---

## Task 5: Video ingest (local Whisper + caption fallback)

**Files:**
- Create: `learn_wiki/ingest/video.py`
- Test: `tests/test_ingest_video.py`, `tests/smoke/test_video_transcribe.py`

**Interfaces:**
- Consumes: `SourceDocument`, `IngestError` (Task 1).
- Produces:
  - `transcribe_video(url: str, *, model_size="small", prefer_captions=False, download=None, transcribe=None, captions=None) -> SourceDocument` with `source_type="video"`. Three injectable seams so the network/Whisper/captions can be faked in tests:
    - `download(url) -> str` returns a local audio file path (defaults to a `yt-dlp` download).
    - `transcribe(audio_path, model_size) -> tuple[str, str]` returns `(title, text)` (defaults to `faster-whisper`).
    - `captions(url) -> str | None` returns caption text or `None` (defaults to `youtube-transcript-api`).
  - When `prefer_captions=True` and captions are available, use them; otherwise download audio and transcribe locally. Raises `IngestError` if both paths yield nothing.
  - `_default_download`, `_default_transcribe`, `_default_captions` - the real implementations, exercised only by the live smoke test.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest_video.py
import pytest
from learn_wiki.ingest.video import transcribe_video
from learn_wiki.errors import IngestError


def test_local_transcription_is_default_path():
    doc = transcribe_video(
        "https://youtu.be/abc",
        download=lambda url: "/tmp/audio.m4a",
        transcribe=lambda path, model_size: ("Talk Title", "spoken words here"),
        captions=lambda url: "caption text",  # present, but not preferred
    )
    assert doc.source_type == "video"
    assert doc.text == "spoken words here"  # transcription used, not captions


def test_prefer_captions_uses_captions_when_available():
    doc = transcribe_video(
        "https://youtu.be/abc",
        prefer_captions=True,
        captions=lambda url: "caption text",
        download=lambda url: pytest.fail("should not download"),
        transcribe=lambda path, model_size: pytest.fail("should not transcribe"),
    )
    assert doc.text == "caption text"


def test_prefer_captions_falls_back_to_transcription():
    doc = transcribe_video(
        "https://youtu.be/abc",
        prefer_captions=True,
        captions=lambda url: None,  # no captions
        download=lambda url: "/tmp/a.m4a",
        transcribe=lambda path, model_size: ("T", "transcribed"),
    )
    assert doc.text == "transcribed"


def test_raises_when_nothing_available():
    with pytest.raises(IngestError):
        transcribe_video(
            "https://youtu.be/abc",
            download=lambda url: "/tmp/a.m4a",
            transcribe=lambda path, model_size: ("T", "  "),  # empty transcript
            captions=lambda url: None,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingest_video.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'learn_wiki.ingest.video'`

- [ ] **Step 3: Write the implementation**

```python
# learn_wiki/ingest/video.py
import tempfile
from learn_wiki.models import SourceDocument
from learn_wiki.errors import IngestError


def _default_download(url: str) -> str:
    import yt_dlp
    tmp = tempfile.mkdtemp()
    out = f"{tmp}/audio.%(ext)s"
    opts = {"format": "bestaudio/best", "outtmpl": out, "quiet": True, "noprogress": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


def _default_transcribe(audio_path: str, model_size: str) -> tuple[str, str]:
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(audio_path)
    text = " ".join(seg.text.strip() for seg in segments)
    return (audio_path, text)


def _default_captions(url: str) -> str | None:
    from youtube_transcript_api import YouTubeTranscriptApi
    try:
        vid = url.rsplit("/", 1)[-1].split("?")[0].split("&")[0]
        parts = YouTubeTranscriptApi.get_transcript(vid)
        return " ".join(p["text"] for p in parts)
    except Exception:
        return None


def transcribe_video(
    url: str,
    *,
    model_size: str = "small",
    prefer_captions: bool = False,
    download=None,
    transcribe=None,
    captions=None,
) -> SourceDocument:
    download = download or _default_download
    transcribe = transcribe or _default_transcribe
    captions = captions or _default_captions

    if prefer_captions:
        cap = captions(url)
        if cap and cap.strip():
            return SourceDocument(url=url, source_type="video", title=url, text=cap)

    audio_path = download(url)
    title, text = transcribe(audio_path, model_size)
    if text and text.strip():
        return SourceDocument(url=url, source_type="video", title=title or url, text=text)

    raise IngestError(f"could not obtain a transcript for {url}")
```

- [ ] **Step 4: Write the live smoke test (skipped by default)**

```python
# tests/smoke/test_video_transcribe.py
# Run deliberately: pytest tests/smoke/test_video_transcribe.py -v
# Requires ffmpeg installed and network access. Uses a short public clip.
from learn_wiki.ingest.video import transcribe_video

SHORT_CLIP = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"  # replace with a short clip you trust


def test_real_transcription_produces_text():
    doc = transcribe_video(SHORT_CLIP, model_size="tiny")
    assert doc.source_type == "video"
    assert len(doc.text) > 0
```

- [ ] **Step 5: Run unit tests to verify they pass**

Run: `pytest tests/test_ingest_video.py -v`
Expected: PASS (4 tests). The smoke test is ignored by the `--ignore=tests/smoke` addopt.

- [ ] **Step 6: Commit**

```bash
git add learn_wiki/ingest/video.py tests/test_ingest_video.py tests/smoke/test_video_transcribe.py
git commit -m "feat: local Whisper video transcription with caption fallback"
```

---

## Task 6: Ingest dispatch

**Files:**
- Modify: `learn_wiki/ingest/__init__.py`
- Test: `tests/test_ingest_dispatch.py`

**Interfaces:**
- Consumes: `fetch_web` (Task 4), `transcribe_video` (Task 5), `SourceDocument` (Task 1).
- Produces:
  - `is_video_url(url: str) -> bool` - true for YouTube URLs (`youtube.com`, `youtu.be`).
  - `ingest(url: str, *, web=fetch_web, video=transcribe_video) -> SourceDocument` - routes to the video or web path. `web`/`video` are injectable for tests.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest_dispatch.py
from learn_wiki.ingest import ingest, is_video_url
from learn_wiki.models import SourceDocument


def test_is_video_url():
    assert is_video_url("https://youtu.be/abc")
    assert is_video_url("https://www.youtube.com/watch?v=abc")
    assert not is_video_url("https://blog.example/post")


def test_dispatch_routes_video():
    doc = SourceDocument("https://youtu.be/abc", "video", "t", "x")
    out = ingest("https://youtu.be/abc",
                 video=lambda url: doc,
                 web=lambda url: (_ for _ in ()).throw(AssertionError("web called")))
    assert out is doc


def test_dispatch_routes_web():
    doc = SourceDocument("https://blog.example/p", "web", "t", "x")
    out = ingest("https://blog.example/p",
                 web=lambda url: doc,
                 video=lambda url: (_ for _ in ()).throw(AssertionError("video called")))
    assert out is doc
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingest_dispatch.py -v`
Expected: FAIL with `ImportError: cannot import name 'ingest'`

- [ ] **Step 3: Write the implementation**

```python
# learn_wiki/ingest/__init__.py
from learn_wiki.ingest.web import fetch_web
from learn_wiki.ingest.video import transcribe_video
from learn_wiki.models import SourceDocument

_VIDEO_HOSTS = ("youtube.com", "youtu.be")


def is_video_url(url: str) -> bool:
    return any(host in url for host in _VIDEO_HOSTS)


def ingest(url: str, *, web=fetch_web, video=transcribe_video) -> SourceDocument:
    if is_video_url(url):
        return video(url)
    return web(url)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ingest_dispatch.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add learn_wiki/ingest/__init__.py tests/test_ingest_dispatch.py
git commit -m "feat: ingest dispatch by URL type"
```

---

## Task 7: ClaudeExtractor (claude-agent-sdk)

**Files:**
- Create: `learn_wiki/extract/claude.py`
- Test: `tests/smoke/test_claude_extractor.py`

**Interfaces:**
- Consumes: `SourceDocument`, `Extraction` (Task 1); `validate_extraction` (Task 3); `ontology.NODE_TYPES`, `ontology.EDGE_TYPES` (Task 1); `ExtractionError` (Task 1).
- Produces:
  - `build_prompt(doc: SourceDocument) -> str` - pure function that builds the extraction prompt from the document and the current ontology. Unit-testable with no network.
  - `parse_response(text: str) -> Extraction` - extracts the JSON object from the model's text reply and runs it through `validate_extraction`; raises `ExtractionError` if no JSON object is found. Unit-testable.
  - `ClaudeExtractor(model_size_hint: str = "")` implementing `Extractor.extract(doc) -> Extraction` by running Claude via `claude-agent-sdk` on the local subscription. One retry on `ExtractionError`.

> **SDK note for the implementer:** `claude-agent-sdk` is the Claude Agent SDK (Claude Code as a library), authenticating via the same login as Claude Code (the owner is logged into their Claude subscription). Confirm the exact import and call surface against the installed version's docs (`code.claude.com/docs/en/agent-sdk`) before finalizing `_run_claude`. The async `query(prompt, options=...)` generator shown below matches the current SDK; adjust only if the installed version differs. The prompt-building and JSON-parsing logic below is authoritative and fully unit-tested regardless of SDK surface.

- [ ] **Step 1: Write the unit tests for the pure functions**

```python
# tests/test_extract_claude.py
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
```

Add this file to `pyproject.toml`'s test run implicitly (it lives under `tests/`).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_extract_claude.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'learn_wiki.extract.claude'`

- [ ] **Step 3: Write the implementation**

```python
# learn_wiki/extract/claude.py
import json
import asyncio
from learn_wiki.models import SourceDocument, Extraction
from learn_wiki.extract.base import validate_extraction
from learn_wiki.errors import ExtractionError
from learn_wiki import ontology

_INSTRUCTIONS = """You extract a knowledge graph from a source document.

Return ONLY a single JSON object with this exact shape:
{{
  "nodes": [{{"type": "<node type>", "name": "<short name>", "description": "<one sentence>"}}],
  "edges": [{{"source_name": "<node name>", "target_name": "<node name>",
              "type": "<edge type>", "quote": "<the exact source sentence supporting this link>"}}],
  "proposed_node_types": ["<any new node type you needed>"],
  "proposed_edge_types": ["<any new edge type you needed>"]
}}

Rules:
- Prefer these node types: {node_types}. If none fit, use a new one and list it in proposed_node_types.
- Prefer these edge types: {edge_types}. If none fit, use a new one and list it in proposed_edge_types.
- Every edge MUST include a quote copied verbatim from the source text. No quote, no edge.
- Only assert links the source actually supports.

SOURCE TITLE: {title}
SOURCE TEXT:
{text}
"""


def build_prompt(doc: SourceDocument) -> str:
    return _INSTRUCTIONS.format(
        node_types=", ".join(ontology.NODE_TYPES),
        edge_types=", ".join(ontology.EDGE_TYPES),
        title=doc.title,
        text=doc.text,
    )


def parse_response(text: str) -> Extraction:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ExtractionError("no JSON object found in model reply")
    try:
        raw = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"model reply was not valid JSON: {exc}") from exc
    return validate_extraction(raw)


async def _run_claude(prompt: str) -> str:
    # Verify against the installed claude-agent-sdk version's docs.
    from claude_agent_sdk import query, ClaudeAgentOptions
    chunks: list[str] = []
    async for message in query(prompt=prompt, options=ClaudeAgentOptions()):
        text = getattr(message, "text", None)
        if text:
            chunks.append(text)
    return "".join(chunks)


class ClaudeExtractor:
    def __init__(self, model_size_hint: str = ""):
        self._hint = model_size_hint

    def extract(self, doc: SourceDocument) -> Extraction:
        prompt = build_prompt(doc)
        reply = asyncio.run(_run_claude(prompt))
        try:
            return parse_response(reply)
        except ExtractionError:
            reply = asyncio.run(_run_claude(prompt + "\n\nReturn ONLY the JSON object, nothing else."))
            return parse_response(reply)
```

- [ ] **Step 4: Write the live smoke test (skipped by default)**

```python
# tests/smoke/test_claude_extractor.py
# Run deliberately: pytest tests/smoke/test_claude_extractor.py -v
# Requires Claude Code logged into the subscription on this machine.
from learn_wiki.extract.claude import ClaudeExtractor
from learn_wiki.models import SourceDocument


def test_real_extraction_returns_nodes_and_cited_edges():
    doc = SourceDocument(
        "u", "web", "Context management",
        "Chunking is a technique that improves how much relevant content fits in a model's "
        "context window. It requires splitting documents into passages first.",
    )
    ex = ClaudeExtractor().extract(doc)
    assert len(ex.nodes) >= 2
    assert all(e.quote.strip() for e in ex.edges)
```

- [ ] **Step 5: Run unit tests to verify they pass**

Run: `pytest tests/test_extract_claude.py -v`
Expected: PASS (3 tests). Smoke test ignored by default.

- [ ] **Step 6: Commit**

```bash
git add learn_wiki/extract/claude.py tests/test_extract_claude.py tests/smoke/test_claude_extractor.py
git commit -m "feat: ClaudeExtractor via claude-agent-sdk on the subscription"
```

---

## Task 8: Web app (FastAPI pipeline endpoints)

**Files:**
- Create: `learn_wiki/web/__init__.py`, `learn_wiki/web/app.py`
- Test: `tests/test_web_app.py`

**Interfaces:**
- Consumes: `GraphStore` (Task 2), `Extractor` (Task 3), `ingest` (Task 6), `SourceDocument`, `IngestError`, `ExtractionError` (Task 1).
- Produces:
  - `create_app(store: GraphStore, extractor: Extractor, ingest_fn=ingest) -> FastAPI` with:
    - `POST /ingest` body `{"url": "..."}` -> runs `ingest_fn(url)`, then `extractor.extract(doc)`, then `store.upsert_source` + `store.upsert_extraction`; returns `{"status": "ok", "nodes": <int>, "edges": <int>}`. Ingest/extraction errors return HTTP 422 with `{"error": "..."}`.
    - `GET /graph` -> `store.get_graph()`.
    - `GET /` -> serves `static/index.html`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_web_app.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_web_app.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'learn_wiki.web.app'`

- [ ] **Step 3: Write the implementation**

```python
# learn_wiki/web/__init__.py
# (empty)
```

```python
# learn_wiki/web/app.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_web_app.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add learn_wiki/web/__init__.py learn_wiki/web/app.py tests/test_web_app.py
git commit -m "feat: FastAPI ingest/graph endpoints wiring the pipeline"
```

---

## Task 9: Frontend graph view (Cytoscape.js, no build step)

**Files:**
- Create: `learn_wiki/web/static/index.html`, `learn_wiki/web/static/cytoscape.min.js` (vendored)
- Test: `tests/test_web_static.py`

**Interfaces:**
- Consumes: `GET /graph` JSON shape (Task 8): `{"nodes":[{"id","type","name","description"}], "edges":[{"source","target","type","quote"}]}`; `POST /ingest` (Task 8).
- Produces: a single page with a URL input, an "Ingest" button, and a Cytoscape canvas that loads `/graph` and colours nodes by `type`. Edges show their `type`; clicking an edge shows its `quote`.

- [ ] **Step 1: Vendor the Cytoscape library**

Run:
```bash
mkdir -p learn_wiki/web/static
curl -L https://unpkg.com/cytoscape@3/dist/cytoscape.min.js -o learn_wiki/web/static/cytoscape.min.js
test -s learn_wiki/web/static/cytoscape.min.js && echo "vendored ok"
```
Expected: `vendored ok` (file is non-empty). Vendoring keeps the page working offline and avoids a CDN dependency at runtime.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_web_static.py
from fastapi.testclient import TestClient
from learn_wiki.web.app import create_app
from learn_wiki.graph.store import GraphStore
from learn_wiki.extract.fake import FakeExtractor
from learn_wiki.models import Extraction


def test_index_served_and_references_cytoscape():
    store = GraphStore(":memory:")
    store.init_schema()
    app = create_app(store, FakeExtractor(Extraction([], [])))
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "cytoscape" in r.text.lower()
    assert "/graph" in r.text  # the page fetches the graph endpoint
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_web_static.py -v`
Expected: FAIL - `index.html` does not exist yet, so `FileResponse` 404s / the assertion on body fails.

- [ ] **Step 4: Write `index.html`**

```html
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Knowledge Graph Wiki</title>
  <script src="/static/cytoscape.min.js"></script>
  <style>
    body { margin: 0; font-family: system-ui, sans-serif; }
    #bar { padding: 8px; display: flex; gap: 8px; border-bottom: 1px solid #ddd; }
    #url { flex: 1; padding: 6px; }
    #cy { width: 100vw; height: calc(100vh - 90px); }
    #status { padding: 4px 8px; color: #555; font-size: 13px; }
  </style>
</head>
<body>
  <div id="bar">
    <input id="url" placeholder="Paste a URL (web page or YouTube link)" />
    <button id="go">Ingest</button>
  </div>
  <div id="status"></div>
  <div id="cy"></div>
  <script>
    const COLORS = {
      Technique: "#2b8cbe", Concept: "#41ab5d", Model: "#e6550d", Tool: "#756bb1",
      Person: "#d94801", Pattern: "#31a354", Pitfall: "#d7301f",
    };
    const cy = cytoscape({
      container: document.getElementById("cy"),
      style: [
        { selector: "node", style: {
            "label": "data(name)", "background-color": ele => COLORS[ele.data("type")] || "#888",
            "color": "#fff", "text-outline-width": 2, "text-outline-color": "#333", "font-size": 11 } },
        { selector: "edge", style: {
            "label": "data(type)", "curve-style": "bezier", "target-arrow-shape": "triangle",
            "width": 1.5, "line-color": "#bbb", "target-arrow-color": "#bbb", "font-size": 9 } },
      ],
      layout: { name: "cose" },
    });

    async function loadGraph() {
      const g = await (await fetch("/graph")).json();
      const els = [];
      for (const n of g.nodes)
        els.push({ data: { id: String(n.id), name: n.name, type: n.type, description: n.description } });
      for (const e of g.edges)
        els.push({ data: { source: String(e.source), target: String(e.target), type: e.type, quote: e.quote } });
      cy.elements().remove();
      cy.add(els);
      cy.layout({ name: "cose" }).run();
    }

    cy.on("tap", "edge", ev => {
      document.getElementById("status").textContent = "Source: " + ev.target.data("quote");
    });

    document.getElementById("go").onclick = async () => {
      const url = document.getElementById("url").value.trim();
      if (!url) return;
      const status = document.getElementById("status");
      status.textContent = "Ingesting ...";
      const r = await fetch("/ingest", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await r.json();
      status.textContent = r.ok
        ? `Added ${data.nodes} nodes, ${data.edges} edges.`
        : `Error: ${data.error}`;
      if (r.ok) { document.getElementById("url").value = ""; await loadGraph(); }
    };

    loadGraph();
  </script>
</body>
</html>
```

- [ ] **Step 5: Mount the static directory in the app**

Modify `learn_wiki/web/app.py` - add near the top of `create_app`, before returning:

```python
    from fastapi.staticfiles import StaticFiles
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_web_static.py -v`
Expected: PASS (1 test)

- [ ] **Step 7: Commit**

```bash
git add learn_wiki/web/static/ learn_wiki/web/app.py tests/test_web_static.py
git commit -m "feat: Cytoscape.js graph view served by the app"
```

---

## Task 10: Runnable entry point and end-to-end verification

**Files:**
- Create: `learn_wiki/__main__.py`, `README.md`
- Test: manual end-to-end run

**Interfaces:**
- Consumes: `create_app` (Task 8), `GraphStore` (Task 2), `ClaudeExtractor` (Task 7), `ingest` (Task 6).
- Produces: `python -m learn_wiki` starts the local server against a persistent `learn_wiki.db` using the real `ClaudeExtractor`.

- [ ] **Step 1: Write the entry point**

```python
# learn_wiki/__main__.py
import uvicorn
from learn_wiki.web.app import create_app
from learn_wiki.graph.store import GraphStore
from learn_wiki.extract.claude import ClaudeExtractor

store = GraphStore("learn_wiki.db")
store.init_schema()
app = create_app(store, ClaudeExtractor())

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
```

- [ ] **Step 2: Write the README**

```markdown
# learn_wiki

A personal knowledge-graph wiki. Paste a URL (web page or video); it extracts a
typed entity graph with citations and draws it in your browser.

## Setup

    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"
    # system dependency for video: ffmpeg (e.g. `brew install ffmpeg`)
    # Claude Code must be logged into your subscription on this machine.

## Run

    python -m learn_wiki
    # open http://127.0.0.1:8000

## Test

    pytest                       # fast unit tests (no network, no subscription)
    pytest tests/smoke -v        # live tests: real Claude extraction and video transcription
```

- [ ] **Step 3: Run the full unit suite**

Run: `pytest -v`
Expected: all unit tests PASS; `tests/smoke` ignored.

- [ ] **Step 4: Manual end-to-end check**

1. `python -m learn_wiki`
2. Open `http://127.0.0.1:8000`.
3. Paste a short blog URL, click Ingest - status shows nodes/edges added and the graph draws.
4. Click an edge - its source quote shows in the status bar.
5. Paste a short YouTube URL - it transcribes locally and the graph grows.
6. Re-paste the same URL - node count does not double (idempotency holds).

- [ ] **Step 5: Commit**

```bash
git add learn_wiki/__main__.py README.md
git commit -m "feat: runnable entry point and README; Slice 1 end to end"
```

---

## Self-Review

**Spec coverage:**
- Ingest (web + full local video transcription + caption fallback): Tasks 4, 5, 6. ✓
- Extract behind swappable interface with validation and provenance: Tasks 3, 7. ✓
- Graph store (5 tables, idempotent, provenance quote per edge): Task 2. ✓
- Web UI + interactive graph visualization (no build step): Tasks 8, 9. ✓
- Starter ontology + proposed-type capture: Tasks 1, 2, 7. ✓
- Errors surface, never silent: `errors.py` (Task 1), used in Tasks 4, 5, 7, 8. ✓
- Subscription auth via Agent SDK, no API key: Task 7 + README (Task 10). ✓
- Fast tests without network/subscription: `FakeExtractor` + injectable ingest seams throughout; live paths isolated under `tests/smoke`. ✓

**Type consistency:** `SourceDocument`/`ExtractedNode`/`ExtractedEdge`/`Extraction` field names are used identically across Tasks 1-9. `get_graph()` returns `{"nodes","edges"}` with node key `id` and edge keys `source`/`target` in Task 2, consumed exactly that way by the frontend in Task 9. `Extractor.extract` signature matches `FakeExtractor` (Task 3) and `ClaudeExtractor` (Task 7).

**Placeholder scan:** No TBD/TODO. The only "verify against installed version" note (Task 7 `_run_claude`) concerns the third-party SDK call surface, not this project's logic; the prompt-building and parsing logic it depends on is fully specified and unit-tested.

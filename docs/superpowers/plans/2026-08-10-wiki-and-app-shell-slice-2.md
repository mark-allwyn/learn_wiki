# App Shell + Wiki View - Slice 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shared navigation menu and a browsable Wiki view (one deterministic, graph-driven page per entity) to the existing knowledge-graph app.

**Architecture:** Separate static HTML pages share one `nav.js` menu. FastAPI gains two read-only JSON endpoints (`/api/entities`, `/api/entity/{id}`) and a `/wiki` page route, all backed by two new read-only `GraphStore` methods that read SQLite only. No LLM, no new dependencies, no build step. Existing routes are untouched.

**Tech Stack:** Python 3.11+, stdlib `sqlite3`, FastAPI, vanilla JS (no framework), `pytest`.

## Global Constraints

- Python 3.11+. The virtualenv is at `venv/` (use `venv/bin/python`, `venv/bin/pytest`).
- Lean: no new dependencies, no frontend framework, no build step.
- The Wiki is assembled deterministically from SQLite - no LLM call anywhere in this slice.
- Every relationship shown carries its provenance: the source `quote` and the source URL/title.
- Additive only: do not change the behavior of existing routes (`/`, `/ingest`, `/graph`, `/logs`) except to add the nav bar to the graph page.
- Nothing fails silently.
- No em dash characters anywhere; use a plain dash.

## Existing code this slice builds on

- `learn_wiki/graph/store.py` - `GraphStore(path)` with `self._conn` (sqlite3, `row_factory = sqlite3.Row`) and a `self._lock` (`threading.Lock`). Public methods acquire `self._lock`; the private `_node_id` does not (it runs while the lock is held). Schema: `nodes(id, type, name, description)`, `edges(id, source_node, target_node, type, source_id, quote)`, `sources(id, url, type, title, fetched_at, raw_text)`.
- `learn_wiki/web/app.py` - `create_app(store, extractor, ingest_fn)` returns a FastAPI app with `POST /ingest`, `GET /graph`, `GET /logs`, `GET /`, and a `/static` mount. `_STATIC = Path(__file__).parent / "static"`.
- `learn_wiki/web/static/index.html` - the graph page (3D ForceGraph + log panel). Its `<body>` starts with `<div id="bar">...`.

---

## File Structure

```
learn_wiki/graph/store.py         # + list_entities(), entity_detail(id)   (modify)
learn_wiki/web/app.py             # + /api/entities, /api/entity/{id}, /wiki  (modify)
learn_wiki/web/static/nav.js      # shared menu (create)
learn_wiki/web/static/wiki.html   # index + entity page (create)
learn_wiki/web/static/index.html  # add nav include (modify)
tests/test_graph_wiki.py          # store read-method tests (create)
tests/test_web_wiki.py            # api + static tests (create)
```

---

## Task 1: GraphStore read methods for the Wiki

**Files:**
- Modify: `learn_wiki/graph/store.py`
- Test: `tests/test_graph_wiki.py`

**Interfaces:**
- Consumes: existing `GraphStore` (`self._conn`, `self._lock`), models `SourceDocument`, `Extraction`, `ExtractedNode`, `ExtractedEdge`.
- Produces:
  - `GraphStore.list_entities() -> list[dict]` - one dict per node `{"id": int, "type": str, "name": str, "description": str, "degree": int}`, ordered by `(type, name)`. `degree` counts edges where the node is source or target.
  - `GraphStore.entity_detail(node_id: int) -> dict | None` - `None` if the node is absent, else `{"node": {"id","type","name","description"}, "relationships": [{"direction": "out"|"in", "type": str, "other": {"id","name","type"}, "quote": str, "source_url": str, "source_title": str}], "sources": [{"url","title"}]}`. `direction` is `"out"` when the node is the edge source, `"in"` when it is the target. `sources` is the distinct set of relationship sources, first-seen order.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_graph_wiki.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_graph_wiki.py -v`
Expected: FAIL with `AttributeError: 'GraphStore' object has no attribute 'list_entities'`

- [ ] **Step 3: Add the two methods to `GraphStore`**

Add these methods to the `GraphStore` class in `learn_wiki/graph/store.py` (place them after `get_graph`):

```python
    def list_entities(self) -> list:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT n.id, n.type, n.name, n.description,
                       (SELECT COUNT(*) FROM edges e
                        WHERE e.source_node = n.id OR e.target_node = n.id) AS degree
                FROM nodes n
                ORDER BY n.type, n.name
                """
            ).fetchall()
        return [
            {"id": r["id"], "type": r["type"], "name": r["name"],
             "description": r["description"], "degree": r["degree"]}
            for r in rows
        ]

    def entity_detail(self, node_id: int):
        with self._lock:
            node = self._conn.execute(
                "SELECT id, type, name, description FROM nodes WHERE id = ?", (node_id,)
            ).fetchone()
            if node is None:
                return None
            rows = self._conn.execute(
                """
                SELECT 'out' AS direction, e.type AS type, e.quote AS quote,
                       n2.id AS other_id, n2.name AS other_name, n2.type AS other_type,
                       s.url AS source_url, s.title AS source_title
                FROM edges e
                JOIN nodes n2 ON n2.id = e.target_node
                JOIN sources s ON s.id = e.source_id
                WHERE e.source_node = ?
                UNION ALL
                SELECT 'in', e.type, e.quote,
                       n2.id, n2.name, n2.type, s.url, s.title
                FROM edges e
                JOIN nodes n2 ON n2.id = e.source_node
                JOIN sources s ON s.id = e.source_id
                WHERE e.target_node = ?
                ORDER BY type, other_name
                """,
                (node_id, node_id),
            ).fetchall()
        relationships = [
            {"direction": r["direction"], "type": r["type"],
             "other": {"id": r["other_id"], "name": r["other_name"], "type": r["other_type"]},
             "quote": r["quote"], "source_url": r["source_url"], "source_title": r["source_title"]}
            for r in rows
        ]
        sources = []
        seen = set()
        for r in relationships:
            key = r["source_url"]
            if key not in seen:
                seen.add(key)
                sources.append({"url": r["source_url"], "title": r["source_title"]})
        return {
            "node": {"id": node["id"], "type": node["type"],
                     "name": node["name"], "description": node["description"]},
            "relationships": relationships,
            "sources": sources,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_graph_wiki.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full suite to confirm no regressions, then commit**

```bash
venv/bin/pytest -q
git add learn_wiki/graph/store.py tests/test_graph_wiki.py
git commit -m "feat: GraphStore read methods for the wiki (list_entities, entity_detail)"
```

---

## Task 2: Wiki JSON endpoints + /wiki route

**Files:**
- Modify: `learn_wiki/web/app.py`
- Test: `tests/test_web_wiki.py`

**Interfaces:**
- Consumes: `GraphStore.list_entities()`, `GraphStore.entity_detail(id)` (Task 1); existing `create_app(store, extractor, ingest_fn)` and `_STATIC`.
- Produces:
  - `GET /api/entities` -> `store.list_entities()` (JSON list).
  - `GET /api/entity/{node_id}` -> `store.entity_detail(node_id)`; HTTP 404 `{"error": "..."}` if it returns `None`.
  - `GET /wiki` -> `FileResponse(_STATIC / "wiki.html")`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_web_wiki.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_web_wiki.py -v`
Expected: FAIL (404 for `/api/entities`, since the route does not exist yet)

- [ ] **Step 3: Add the routes**

In `learn_wiki/web/app.py`, inside `create_app`, add these routes next to the existing `@app.get("/graph")` block (before the `/static` mount and `return app`):

```python
    @app.get("/api/entities")
    def entities_endpoint():
        return store.list_entities()

    @app.get("/api/entity/{node_id}")
    def entity_endpoint(node_id: int):
        detail = store.entity_detail(node_id)
        if detail is None:
            return JSONResponse({"error": f"entity {node_id} not found"}, status_code=404)
        return detail

    @app.get("/wiki")
    def wiki_page():
        return FileResponse(_STATIC / "wiki.html")
```

(`JSONResponse` and `FileResponse` are already imported at the top of the file.)

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_web_wiki.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
venv/bin/pytest -q
git add learn_wiki/web/app.py tests/test_web_wiki.py
git commit -m "feat: wiki JSON endpoints and /wiki route"
```

---

## Task 3: Shared nav menu (nav.js) + add it to the graph page

**Files:**
- Create: `learn_wiki/web/static/nav.js`
- Modify: `learn_wiki/web/static/index.html`
- Test: add to `tests/test_web_wiki.py`

**Interfaces:**
- Consumes: nothing (pure frontend). Pages include it via `<div id="nav"></div>` + `<script src="/static/nav.js"></script>`.
- Produces: a menu rendered into `#nav` with links `Graph` (`/`) and `Wiki` (`/wiki`), the current page marked active by `location.pathname`.

- [ ] **Step 1: Write `nav.js`**

```javascript
// learn_wiki/web/static/nav.js
// Shared top navigation. Include on every page:
//   <div id="nav"></div>
//   <script src="/static/nav.js"></script>
(function () {
  var LINKS = [
    { label: "Graph", href: "/" },
    { label: "Wiki", href: "/wiki" },
  ];
  var path = location.pathname;
  var el = document.getElementById("nav");
  if (!el) return;
  el.style.cssText =
    "display:flex;gap:4px;align-items:center;padding:6px 10px;" +
    "background:#0d1017;border-bottom:1px solid #1e2430;font-family:system-ui,sans-serif";
  var brand = document.createElement("span");
  brand.textContent = "Knowledge Graph Wiki";
  brand.style.cssText = "color:#e6e9ef;font-weight:600;font-size:13px;margin-right:14px";
  el.appendChild(brand);
  LINKS.forEach(function (link) {
    var a = document.createElement("a");
    a.textContent = link.label;
    a.href = link.href;
    var active = path === link.href;
    a.style.cssText =
      "color:" + (active ? "#fff" : "#aab2c0") + ";text-decoration:none;" +
      "font-size:13px;padding:4px 10px;border-radius:6px;" +
      "background:" + (active ? "#2f6feb" : "transparent");
    el.appendChild(a);
  });
})();
```

- [ ] **Step 2: Add the nav to `index.html`**

In `learn_wiki/web/static/index.html`, add the nav container as the first child of `<body>`, immediately before `<div id="bar">`:

```html
  <div id="nav"></div>
```

And add the script include immediately after the existing `<script src="/static/3d-force-graph.min.js"></script>` line in `<head>`:

```html
  <script defer src="/static/nav.js"></script>
```

Use `defer` so it runs after the DOM is parsed and `#nav` exists.

- [ ] **Step 3: Write the failing test (graph page references nav.js)**

Add to `tests/test_web_wiki.py`:

```python
def test_index_includes_nav():
    client, _ = build_client()
    r = client.get("/")
    assert r.status_code == 200
    assert "/static/nav.js" in r.text
    assert 'id="nav"' in r.text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_web_wiki.py::test_index_includes_nav -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
venv/bin/pytest -q
git add learn_wiki/web/static/nav.js learn_wiki/web/static/index.html tests/test_web_wiki.py
git commit -m "feat: shared nav menu and add it to the graph page"
```

---

## Task 4: Wiki page (index + entity detail)

**Files:**
- Create: `learn_wiki/web/static/wiki.html`
- Test: add to `tests/test_web_wiki.py`

**Interfaces:**
- Consumes: `GET /api/entities`, `GET /api/entity/{id}` (Task 2); `nav.js` (Task 3).
- Produces: `wiki.html` - shows the entity index when there is no `?id`, and the entity page when `?id=N` is present.

- [ ] **Step 1: Write `wiki.html`**

```html
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Wiki - Knowledge Graph</title>
  <script defer src="/static/nav.js"></script>
  <style>
    html, body { margin: 0; background: #0b0e14; color: #e6e9ef; font-family: system-ui, sans-serif; }
    #content { max-width: 820px; margin: 0 auto; padding: 20px 24px 60px; }
    a { color: #79b8ff; }
    #filter { width: 100%; padding: 8px 10px; margin: 8px 0 18px; background: #11151f;
              border: 1px solid #2a3140; border-radius: 6px; color: #e6e9ef; box-sizing: border-box; }
    .type-group h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .05em; color: #8892a0;
                     border-bottom: 1px solid #1e2430; padding-bottom: 4px; margin: 22px 0 8px; }
    .ent { display: block; padding: 4px 0; text-decoration: none; }
    .ent .deg { color: #8892a0; font-size: 12px; margin-left: 6px; }
    .badge { display: inline-block; font-size: 12px; padding: 2px 8px; border-radius: 10px;
             background: #1e2430; color: #aab2c0; margin-left: 8px; vertical-align: middle; }
    .desc { color: #c9d1e0; margin: 10px 0 20px; }
    .rel-group h3 { font-size: 14px; color: #cdd5e0; margin: 18px 0 6px; }
    .rel { border-left: 2px solid #2a3140; padding: 2px 0 2px 12px; margin: 10px 0; }
    .rel blockquote { margin: 5px 0; color: #aab2c0; font-style: italic; font-size: 13px; }
    .muted { color: #8892a0; }
    .src { font-size: 13px; }
  </style>
</head>
<body>
  <div id="nav"></div>
  <div id="content">Loading ...</div>
  <script>
    const content = document.getElementById("content");
    const params = new URLSearchParams(location.search);
    const id = params.get("id");

    function esc(s) {
      return String(s == null ? "" : s).replace(/[&<>"]/g, c =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
    }

    async function renderIndex() {
      const ents = await (await fetch("/api/entities")).json();
      if (!ents.length) {
        content.innerHTML = "<p class='muted'>No entities yet - ingest some sources on the Graph page.</p>";
        return;
      }
      const groups = {};
      for (const e of ents) (groups[e.type] = groups[e.type] || []).push(e);
      let html = "<h1>Wiki</h1><input id='filter' placeholder='Filter entities ...' />";
      for (const type of Object.keys(groups).sort()) {
        html += `<div class="type-group"><h2>${esc(type)}</h2>`;
        for (const e of groups[type]) {
          html += `<a class="ent" href="/wiki?id=${e.id}" data-name="${esc(e.name).toLowerCase()}">`
                + `${esc(e.name)}<span class="deg">${e.degree} link${e.degree === 1 ? "" : "s"}</span></a>`;
        }
        html += "</div>";
      }
      content.innerHTML = html;
      const filter = document.getElementById("filter");
      filter.oninput = () => {
        const q = filter.value.trim().toLowerCase();
        for (const a of content.querySelectorAll(".ent"))
          a.style.display = a.dataset.name.includes(q) ? "block" : "none";
        for (const g of content.querySelectorAll(".type-group")) {
          const anyVisible = [...g.querySelectorAll(".ent")].some(a => a.style.display !== "none");
          g.style.display = anyVisible ? "block" : "none";
        }
      };
    }

    async function renderEntity(nodeId) {
      const r = await fetch("/api/entity/" + encodeURIComponent(nodeId));
      if (r.status === 404) {
        content.innerHTML = "<p class='muted'>Entity not found.</p><p><a href='/wiki'>Back to index</a></p>";
        return;
      }
      const d = await r.json();
      let html = `<p><a href="/wiki">&larr; All entities</a></p>`
               + `<h1>${esc(d.node.name)}<span class="badge">${esc(d.node.type)}</span></h1>`;
      if (d.node.description) html += `<div class="desc">${esc(d.node.description)}</div>`;

      const byType = {};
      for (const rel of d.relationships) (byType[rel.type] = byType[rel.type] || []).push(rel);
      if (!d.relationships.length) {
        html += "<p class='muted'>No relationships recorded yet.</p>";
      }
      for (const type of Object.keys(byType).sort()) {
        html += `<div class="rel-group"><h3>${esc(type)}</h3>`;
        for (const rel of byType[type]) {
          const arrow = rel.direction === "out" ? "&rarr;" : "&larr;";
          html += `<div class="rel">${arrow} <a href="/wiki?id=${rel.other.id}">${esc(rel.other.name)}</a>`
                + `<span class="badge">${esc(rel.other.type)}</span>`
                + `<blockquote>${esc(rel.quote)}</blockquote>`
                + `<div class="src muted">Source: <a href="${esc(rel.source_url)}" target="_blank" rel="noopener">${esc(rel.source_title || rel.source_url)}</a></div>`
                + `</div>`;
        }
        html += "</div>";
      }

      if (d.sources.length) {
        html += "<div class='rel-group'><h3>Sources</h3>";
        for (const s of d.sources)
          html += `<div class="src"><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title || s.url)}</a></div>`;
        html += "</div>";
      }
      content.innerHTML = html;
    }

    (id ? renderEntity(id) : renderIndex()).catch(e => {
      content.innerHTML = "<p class='muted'>Failed to load: " + esc(e) + "</p>";
    });
  </script>
</body>
</html>
```

- [ ] **Step 2: Write the failing test (wiki page served + references)**

Add to `tests/test_web_wiki.py`:

```python
def test_wiki_page_served():
    client, _ = build_client()
    r = client.get("/wiki")
    assert r.status_code == 200
    assert "/static/nav.js" in r.text
    assert "/api/entity/" in r.text     # entity detail fetch
    assert "/api/entities" in r.text    # index fetch
```

- [ ] **Step 3: Run test to verify it fails then passes**

Run: `venv/bin/pytest tests/test_web_wiki.py::test_wiki_page_served -v`
Expected: FAIL before `wiki.html` exists (the `/wiki` route from Task 2 returns a FileResponse to a missing file -> error), PASS once `wiki.html` is created.

- [ ] **Step 4: Run the full suite**

Run: `venv/bin/pytest -q`
Expected: all pass.

- [ ] **Step 5: Manual check (server)**

1. `venv/bin/python -m learn_wiki`
2. Open `http://127.0.0.1:8000/wiki` - the index lists entities grouped by type; the filter box narrows them.
3. Click an entity - its page shows description, relationships grouped by type (each with a quote and source link), and a Sources list. The `&larr;`/`&rarr;` arrows reflect direction.
4. The nav bar switches between Graph and Wiki, highlighting the current page.

- [ ] **Step 6: Commit**

```bash
git add learn_wiki/web/static/wiki.html tests/test_web_wiki.py
git commit -m "feat: wiki index and entity pages"
```

---

## Self-Review

**Spec coverage:**
- Shared menu defined once, included on every page: Task 3 (`nav.js`), added to graph page (Task 3) and wiki page (Task 4). ✓
- Wiki index grouped by type + client-side filter: Task 4. ✓
- Entity page: name/type, description, relationships grouped by type with quote + source link, sources list: Task 4, backed by `entity_detail` (Task 1). ✓
- Read-only JSON endpoints + `/wiki` route: Task 2. ✓
- Deterministic from SQLite, no LLM: Tasks 1-2 read-only SQL. ✓
- Provenance on every relationship (quote + source url/title): `entity_detail` (Task 1), rendered in Task 4. ✓
- Additive, existing routes untouched: Tasks only add routes; index.html change is limited to the nav include. ✓
- Errors: 404 for missing entity (Task 2), "not found" and empty-graph messages (Task 4). ✓

**Type consistency:** `list_entities()` keys (`id,type,name,description,degree`) are consumed exactly in Task 4's `renderIndex`. `entity_detail` shape (`node`, `relationships[].direction/type/other/quote/source_url/source_title`, `sources[].url/title`) is consumed exactly in Task 4's `renderEntity` and asserted in Task 1/Task 2 tests. `/api/entity/{node_id}` typed as `int` matches the int ids from `list_entities`.

**Placeholder scan:** No TBD/TODO; all code blocks are complete. HTML is escaped via `esc()` to avoid broken markup from entity names/quotes.

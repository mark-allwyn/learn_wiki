# App Shell (menu) + Wiki View - Design (Slice 2)

Date: 2026-08-10
Status: Approved for planning

## Goal

Turn the single graph page into a multi-view app with a shared menu, and add the first new view: a browsable Wiki generated from the knowledge graph.

The Wiki makes the graph readable as pages - one page per entity - so the owner can browse what has been extracted and follow the connections and their sources, rather than only seeing the 3D graph.

## Principles

- Lean and fast: no build step, no frontend framework, minimal dependencies. Wiki pages are assembled deterministically from SQLite with no LLM call.
- Every relationship shown on a wiki page carries its provenance (the source quote and a link to the source), consistent with the rest of the project.
- Additive: existing routes (`/`, `/ingest`, `/graph`, `/logs`) and behavior are untouched.

## Scope

### In scope

- A shared top navigation menu across pages, defined once and included on every page.
- A Wiki view:
  - An index listing all entities grouped by type, with a client-side filter box, each linking to its entity page.
  - An entity page showing the entity's name and type, its description, its relationships grouped by relationship type (each with the source quote and a link to the source), and the list of sources that mention it.
- Read-only JSON endpoints backing the Wiki, plus a route serving the Wiki page.

### Out of scope (later slices)

- The Ask (Q&A) view.
- The Patterns view.
- On-demand LLM prose synthesis for entity pages.
- Editing or deleting graph data from the Wiki.

## Architecture

Separate static HTML pages share one navigation menu, rather than a single-page app.
The graph page is heavy (Three.js); the Wiki is light.
Keeping them as separate documents means neither pays for the other's weight.

A single small `nav.js` holds the menu markup in one place and injects it into each page, so the menu is defined once (DRY) with no build step.

FastAPI serves the pages and new read-only JSON endpoints.
The Wiki content is assembled deterministically from the existing SQLite data - no LLM call, so pages load instantly and always reflect the graph.

```
  Browser page (/, /wiki)
        |
        v  fetch JSON
  FastAPI routes  ---- read-only ---->  GraphStore (SQLite)
```

Menu at launch: `Graph | Wiki`.
Ask and Patterns tabs are added to `nav.js` when those slices are built.

## Components and interfaces

### GraphStore (two new read-only methods)

- `list_entities() -> list[dict]`
  Returns one dict per node: `{"id", "type", "name", "description", "degree"}`, where `degree` is the number of edges touching the node (in or out).
  Used by the Wiki index.

- `entity_detail(node_id: int) -> dict | None`
  Returns `None` if the node does not exist, otherwise:
  ```
  {
    "node": {"id", "type", "name", "description"},
    "relationships": [
      {"direction": "out"|"in", "type": "<edge type>",
       "other": {"id", "name", "type"},
       "quote": "<source sentence>",
       "source_url": "<url>", "source_title": "<title>"}
    ],
    "sources": [{"url", "title"}]   # distinct sources across the relationships
  }
  ```
  `direction` is `"out"` when the node is the edge's source, `"in"` when it is the target.

Both methods are read-only and acquire the existing `GraphStore` lock for consistency with the writer.

### FastAPI routes (added to `create_app`)

- `GET /api/entities` -> `list_entities()`.
- `GET /api/entity/{node_id}` -> `entity_detail(node_id)`; returns HTTP 404 `{"error": "..."}` when the entity does not exist.
- `GET /wiki` -> serves `static/wiki.html`.

Existing routes are unchanged.

### Frontend

- `static/nav.js`
  Renders the navigation menu into a `#nav` element on the page, marking the current page active (based on `location.pathname`).
  Self-contained: it carries its own minimal styling so no shared stylesheet is needed.

- `static/wiki.html`
  One page that behaves two ways based on a `?id=` query parameter:
  - No `?id`: fetches `/api/entities`, renders the index grouped by type, with a text filter box that hides non-matching entities client-side.
    Each entity links to `/wiki?id=<id>` and shows its degree.
  - `?id=N`: fetches `/api/entity/N`, renders the entity page - name with a type badge, description, relationships grouped by type (each rendered as the related entity name, linked to its own wiki page, with the source quote as a blockquote and a link to the source), and a Sources list.
    Includes a link back to the index.

- `static/index.html` (existing graph page)
  Gains a `#nav` element and the `nav.js` include at the top, so the menu appears there too.
  The 3D graph, log panel, and ingest controls are otherwise unchanged.

## Data flow

1. The browser loads a page (`/` or `/wiki`), which includes `nav.js` for the menu.
2. The Wiki page fetches `/api/entities` (index) or `/api/entity/{id}` (entity page) and renders the result.
3. Endpoints read from `GraphStore` (SQLite) only.

## Error handling

- `GET /api/entity/{id}` for a missing node returns HTTP 404 with `{"error": "..."}`; the entity page shows a "not found" message and a link back to the index.
- An empty graph: the index shows "No entities yet - ingest some sources."
- Nothing fails silently.

## Testing

- `GraphStore.list_entities`: build a small graph and assert the returned entities and their `degree` (edges in and out counted).
- `GraphStore.entity_detail`: assert the node, the relationships with correct `direction`, `type`, `other` entity, and `quote`, the joined `source_url`/`source_title`, and the distinct `sources`; assert `None` for a missing id.
- API: `GET /api/entities` returns the expected list shape; `GET /api/entity/{id}` returns the detail shape and 404 for a missing id.
- Static: `GET /wiki` serves HTML that references `nav.js` and the entity API; `GET /` serves HTML that references `nav.js`.

Unit tests use in-memory SQLite and never hit the network or an LLM.

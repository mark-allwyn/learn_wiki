# Knowledge-Graph Wiki - Design

Date: 2026-08-10
Status: Approved for planning (Slice 1)

## Goal

Build a personal wiki backed by a knowledge graph.
The owner curates sources (YouTube videos, blogs, websites) about vibe coding, AI models, context management, prompting, and related topics.
The system extracts a real entity graph from those sources and uses it to find patterns and links for the best ways to engineer AI products.

The graph is the foundation.
Three views sit on top of it, to be built in later slices: ask questions, browse an auto-generated wiki, and surface patterns.

## Principles

- Lean and fast: minimal, focused dependencies; no framework bloat; clear module boundaries; hand-written SQL over an ORM.
- Every extracted link carries provenance (the exact source sentence) so pattern-finding is always traceable.
- The LLM sits behind an interface so it is swappable and tests never hit the network.

## Scope

### In scope (Slice 1: Ingest -> Extract -> Graph -> Visualize)

Paste a URL.
The system fetches and cleans the content, Claude extracts typed entities and relationships with citations, the result is stored in a graph, and the graph is rendered as an interactive diagram in a local browser view.

Video is handled completely from day one: audio is downloaded and transcribed locally with Whisper, so any video extracts fully whether or not it has captions.

### Out of scope (later slices)

- Ask-questions view (query the graph, synthesize an answer with citations).
- Auto-generated wiki pages per entity.
- Pattern-surfacing view.
- Bulk import, feed monitoring, hosting, and multi-user access.

## Architecture

```
  Paste URL
     |
     v
  1. ingest      fetch + clean text (per source type)
     |
     v
  2. extract     Claude reads text + current ontology -> entities + relations + citations
     |
     v
  3. graph       upsert nodes, edges, sources, ontology (SQLite)
     |
     v
  4. web         FastAPI serves graph JSON; one static page draws it with Cytoscape.js
```

### Module layout

```
learn_wiki/
├── ingest/       URL -> clean text (per-source-type fetchers)
├── extract/      clean text -> entities + relations + citations (LLM behind an interface)
├── graph/        storage + queries (SQLite, stdlib only)
├── web/          FastAPI app + one static page (Cytoscape.js graph view)
└── ontology.py   the starter node/edge types
```

Each module has one job and a small, explicit interface.
Any module can be understood and tested without reading the internals of the others.

### Dependencies (deliberately minimal)

| Piece | Choice | Rationale |
|---|---|---|
| Fetch web/blog | `httpx` + `trafilatura` | Extracts just the article text; no headless browser. |
| Transcribe video | `yt-dlp` (audio) + `faster-whisper` (local transcription) | Fully local, free after a one-time model download; transcribes any video, captioned or not. `faster-whisper` is ~4x lighter/faster than reference Whisper with the same accuracy, and integrates in-process. Requires `ffmpeg` (system dependency). |
| Fast video fallback | `youtube-transcript-api` | Optional captions-only path for when speed matters more than completeness; tiny dependency. |
| Extract | Claude Agent SDK behind an `Extractor` interface | Runs on the owner's Claude subscription; interface enables a `FakeExtractor` in tests and a later swap to the metered API. |
| Graph store | stdlib `sqlite3` (no ORM) | One file, no server, transparent SQL; sufficient for low-hundreds of nodes. |
| Analysis/traversal | `networkx`, loaded from SQLite on demand | Pure-Python and light; SQLite remains the source of truth. |
| Web + viz | `FastAPI` + vanilla-JS page with `Cytoscape.js` | No build step, no frontend framework; backend returns graph JSON, the page renders it. |

## Components and interfaces

### ingest

- Input: a URL.
- Output: a normalized source document (url, source type, title, clean text).
- Dispatch by URL: video links are transcribed locally (audio via `yt-dlp`, transcription via `faster-whisper`); other links use `httpx` + `trafilatura`.
- Local transcription is the default video path and works with or without captions. An optional captions-first fast path (`youtube-transcript-api`) can be used when speed matters more than completeness.
- The Whisper model size is configurable (default `small` or `medium`), trading speed against accuracy.
- Fetch and transcription failures (dead link, unavailable audio, missing `ffmpeg`) are reported as clear, recoverable errors, not silently skipped.

### extract

- `Extractor` interface: given clean text and the current ontology, return a validated set of nodes and edges, each edge carrying a source sentence (quote).
- `ClaudeExtractor`: implemented with the Claude Agent SDK, running on the owner's subscription.
- `FakeExtractor`: returns canned data for fast tests.
- Output is validated against a schema; malformed model output is retried once, then reported as an error.
- Hybrid ontology: the model maps onto the starter vocabulary and may propose new node/edge types, which are surfaced for approval rather than added silently.

### graph (SQLite)

Five small tables:

- `sources` (url, type, title, fetched_at, raw_text)
- `nodes` (id, type, name, description)
- `edges` (source_node, target_node, type, source_id, quote)
- `node_types`, `edge_types` (the ontology, so the hybrid schema can grow)

Upserts are idempotent: re-pasting a URL updates the source and reconciles its nodes/edges rather than creating duplicates.

### web

- FastAPI backend: an endpoint to submit a URL (runs the ingest -> extract -> graph pipeline) and an endpoint that returns the graph as JSON.
- One static page renders the graph with Cytoscape.js and re-renders after an ingest.
- No build step and no frontend framework.

## Starter ontology

- Node types: Technique, Concept, Model, Tool, Person, Pattern, Pitfall.
- Edge types: improves, contradicts, requires, part-of, alternative-to, used-with.
- The AI proposes new types as it reads; the owner approves them before they enter the ontology.

## Error handling

- Fetch failures (dead link, no captions) surface as clear, recoverable errors.
- Extraction output is validated against the schema; junk output is retried once, then reported.
- Ingestion is idempotent, so a failed or repeated run leaves the graph consistent.
- Nothing fails silently.

## Testing

- The `Extractor` interface lets a `FakeExtractor` drive the ingest -> graph -> query path with no network and no subscription usage; these tests are the fast default.
- Unit tests per module against its interface.
- A small number of live smoke tests exercise the real Claude extraction and are run deliberately, not on every run.

## Authentication

- Claude runs via the Claude Agent SDK, which uses the same login as Claude Code.
- The owner is already logged into Claude Code with a Claude subscription, so no API key is required for Slice 1.
- Subscription usage counts against Claude Code usage limits; at a handful of URLs per week this is a non-issue.

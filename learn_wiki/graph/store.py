import sqlite3
from learn_wiki.models import SourceDocument, Extraction
from learn_wiki import ontology
from learn_wiki.errors import ExtractionError

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
    quote TEXT NOT NULL CHECK(length(trim(quote)) > 0)
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
        # Track both node IDs and node types to detect collisions
        ids: dict[str, int] = {}
        types: dict[str, str] = {}

        # Check for same-name different-type collision in extraction.nodes
        for n in extraction.nodes:
            if n.name in types and types[n.name] != n.type:
                raise ExtractionError(
                    f"Node name collision: '{n.name}' appears with type '{types[n.name]}' "
                    f"and type '{n.type}' in the same extraction"
                )
            types[n.name] = n.type
            ids[n.name] = self._node_id(n.type, n.name, n.description)

        for e in extraction.edges:
            src_id = ids.get(e.source_name)
            if src_id is None:
                src_id = self._node_id("Concept", e.source_name, "")

            tgt_id = ids.get(e.target_name)
            if tgt_id is None:
                tgt_id = self._node_id("Concept", e.target_name, "")

            self._conn.execute(
                "INSERT INTO edges(source_node, target_node, type, source_id, quote) VALUES (?, ?, ?, ?, ?)",
                (src_id, tgt_id, e.type, source_id, e.quote),
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

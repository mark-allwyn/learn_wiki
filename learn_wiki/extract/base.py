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

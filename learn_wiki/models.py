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

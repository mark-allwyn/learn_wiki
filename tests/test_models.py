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

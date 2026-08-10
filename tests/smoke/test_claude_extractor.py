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

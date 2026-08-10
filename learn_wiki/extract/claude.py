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
    # Verified against the installed claude-agent-sdk (0.2.134): assistant
    # text is not exposed as `message.text`. `query()` yields Message
    # objects; only `AssistantMessage` carries a `.content` list of
    # `ContentBlock`s, and only `TextBlock` (one of several block variants)
    # has a `.text` attribute. Other message types (SystemMessage,
    # ResultMessage, ...) and other block types (ToolUseBlock, ...) are
    # skipped.
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

    chunks: list[str] = []
    async for message in query(prompt=prompt, options=ClaudeAgentOptions()):
        if not isinstance(message, AssistantMessage):
            continue
        for block in message.content:
            if isinstance(block, TextBlock):
                chunks.append(block.text)
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

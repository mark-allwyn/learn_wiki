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


# Minimal system prompt. Passing a plain string replaces Claude Code's large
# default coding-agent system prompt, which cuts input tokens and steers the
# model straight at the one-shot extraction task instead of agentic behavior.
_SYSTEM_PROMPT = (
    "You are a knowledge-graph extractor. Read the document in the user message "
    "and reply with only a single JSON object in the shape it requests. Do not "
    "use tools, do not plan or think out loud, do not explain - output the JSON "
    "object and nothing else."
)


async def _run_claude(prompt: str, *, model, effort) -> str:
    # Verified against the installed claude-agent-sdk (0.2.134): assistant text
    # is not exposed as `message.text`. `query()` yields Message objects; only
    # `AssistantMessage` carries a `.content` list of `ContentBlock`s, and only
    # `TextBlock` has a `.text` attribute. Other message/block types are skipped.
    #
    # Options are tuned for a fast one-shot extraction rather than an agent run:
    # a single turn, no tools, low effort, and a minimal system prompt.
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

    options = ClaudeAgentOptions(
        model=model,
        system_prompt=_SYSTEM_PROMPT,
        allowed_tools=[],
        max_turns=1,
        effort=effort,
    )
    chunks: list[str] = []
    async for message in query(prompt=prompt, options=options):
        if not isinstance(message, AssistantMessage):
            continue
        for block in message.content:
            if isinstance(block, TextBlock):
                chunks.append(block.text)
    return "".join(chunks)


class ClaudeExtractor:
    def __init__(self, model: str = "sonnet", effort: str = "low"):
        # Runs on the Claude subscription via the Agent SDK. `model` accepts a
        # Claude Code alias ("sonnet", "haiku", "opus") or a full model id;
        # `effort` is the thinking/effort level. Defaults favor speed: extraction
        # against a clear schema does not need Opus-at-high-effort.
        self._model = model
        self._effort = effort

    def extract(self, doc: SourceDocument) -> Extraction:
        prompt = build_prompt(doc)
        reply = asyncio.run(_run_claude(prompt, model=self._model, effort=self._effort))
        try:
            return parse_response(reply)
        except ExtractionError:
            reply = asyncio.run(_run_claude(
                prompt + "\n\nReturn ONLY the JSON object, nothing else.",
                model=self._model, effort=self._effort,
            ))
            return parse_response(reply)

"""
Prompt builder for grounded RAG prompts.

Responsible for constructing system + user prompts with:
- strict grounding instructions
- injected context documents
- agent‑specific behavior
"""

from typing import List, Dict


def _format_context(context_chunks: List[Dict]) -> str:
    parts: List[str] = []
    for chunk in context_chunks:
        prefix = ""
        if "doc_id" in chunk:
            prefix += f"[doc={chunk['doc_id']}] "
        if "page" in chunk:
            prefix += f"(page {chunk['page']}) "
        text = chunk.get("text") or ""
        parts.append(f"{prefix}{text}".strip())
    return "\n\n---\n\n".join(parts)


def build_prompt(
    query: str,
    context_chunks: List[Dict],
    *,
    agent_config: Dict,
) -> List[Dict]:
    """
    Build a grounded prompt with strict context usage.
    """
    system_prompt = agent_config.get("system_prompt") or (
        "You are a domain-specific assistant. "
        "Use only the provided context to answer the user's question. "
        "If the answer is not present, say: "
        "\"I cannot find the answer in the provided documents.\""
    )

    context_text = _format_context(context_chunks) if context_chunks else "No context available."

    messages: List[Dict] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "Context:\n"
                f"{context_text}\n\n"
                "Question:\n"
                f"{query}"
            ),
        },
    ]
    return messages



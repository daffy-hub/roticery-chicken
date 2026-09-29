from __future__ import annotations

from typing import Any


def extract_usage(payload: dict[str, Any]) -> int:
    usage = payload.get("usage") or {}
    total = usage.get("total_tokens")
    if total is not None:
        return int(total)

    # OpenAI Responses-style usage.
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    if input_tokens or output_tokens:
        return int(input_tokens) + int(output_tokens)

    # Chat Completions-style fallback.
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    return int(prompt_tokens) + int(completion_tokens)


def estimate_tokens(payload: dict[str, Any]) -> int:
    """Very rough safety estimate used only when a provider omits usage."""
    text = str(payload.get("messages", payload.get("input", "")))
    return max(1, len(text) // 4)

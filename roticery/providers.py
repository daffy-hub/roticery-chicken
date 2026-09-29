from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .config import AccountConfig

Protocol = Literal["openai", "anthropic", "both"]


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    default_protocol: Protocol
    display_name: str


PROVIDERS: dict[str, ProviderSpec] = {
    "openai": ProviderSpec("openai", "openai", "OpenAI"),
    "openrouter": ProviderSpec("openrouter", "both", "OpenRouter"),
    "anthropic": ProviderSpec("anthropic", "anthropic", "Anthropic"),
    "lmstudio": ProviderSpec("lmstudio", "both", "LM Studio"),
    "lm-studio": ProviderSpec("lmstudio", "both", "LM Studio"),
    "ollama": ProviderSpec("ollama", "openai", "Ollama"),
    "groq": ProviderSpec("groq", "openai", "Groq"),
    "mistral": ProviderSpec("mistral", "openai", "Mistral"),
    "together": ProviderSpec("together", "openai", "Together"),
    "fireworks": ProviderSpec("fireworks", "openai", "Fireworks"),
    "deepseek": ProviderSpec("deepseek", "openai", "DeepSeek"),
    "vllm": ProviderSpec("vllm", "openai", "vLLM"),
    "local": ProviderSpec("local", "openai", "Local OpenAI-compatible"),
    "google": ProviderSpec("google", "openai", "Google Gemini"),
    "gemini": ProviderSpec("google", "openai", "Google Gemini"),
    "xai": ProviderSpec("xai", "openai", "xAI"),
    "cerebras": ProviderSpec("cerebras", "openai", "Cerebras"),
    "perplexity": ProviderSpec("perplexity", "openai", "Perplexity"),
    "cohere": ProviderSpec("cohere", "openai", "Cohere"),
    "azure-openai": ProviderSpec("azure-openai", "openai", "Azure OpenAI"),
}


def protocol_for(account: AccountConfig) -> Protocol:
    configured = getattr(account, "protocol", None)
    if configured and configured != "auto":
        return configured
    spec = PROVIDERS.get(account.provider.lower())
    return spec.default_protocol if spec else "openai"


def supports_protocol(account: AccountConfig, protocol: str) -> bool:
    selected = protocol_for(account)
    return selected == protocol or selected == "both"

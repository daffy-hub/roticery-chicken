# Rotisserie Chicken 🐔

Rotisserie Chicken is a small, provider-agnostic AI API gateway. It exposes one OpenAI-compatible endpoint to an agent while routing requests across a configured pool of upstream credentials.

The first milestone is deliberately narrow:

- OpenAI-compatible `/v1/chat/completions`, `/v1/completions`, `/v1/responses`, `/v1/embeddings`, `/v1/moderations`, `/v1/images/generations`, `/v1/audio/speech`, and `/v1/audio/transcriptions` proxying.
- Any number of configured upstream accounts/providers.
- Persistent per-account token accounting in SQLite.
- Sequential or round-robin account rotation.
- Per-account token thresholds.
- Cooldown and retry on configured upstream status codes.
- Anthropic Messages compatibility at `/v1/messages`.
- Protocol-aware routing for OpenAI, Anthropic, OpenRouter, and LM Studio-style endpoints.
- Optional local client authentication.
- `/status` and `/healthz` endpoints.

## Design

```text
Agent (Hermes, OpenAI SDK, etc.)
            |
            v
     Rotisserie Chicken
            |
      Account Router
       /      |      \
      v       v       v
   Key A    Key B    Key N
      \       |       /
       \      |      /
        Provider APIs
```

The gateway records upstream-reported usage when available. OpenRouter documents an OpenAI-compatible API at `/api/v1` and supports usage information in API responses; this project consumes that usage field rather than trying to infer tokens from model text. See the OpenRouter developer documentation for the current API contract.

## Important operating rule

This project is intended for legitimate credential pooling, controlled failover, development, and multi-provider routing. Configure and use accounts in accordance with each provider's terms, quotas, and account rules. The gateway does not attempt to defeat identity checks, anti-abuse controls, or provider-enforced limits.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp config/roticery.example.yaml config/roticery.yaml
cp .env.example .env
```

Populate the environment variables referenced by `api_key_env`, then run:

```bash
set -a
source .env
set +a
ROTI_CONFIG=config/roticery.yaml roticery --config config/roticery.yaml
```

The gateway listens on `127.0.0.1:8080` by default.

## Point an OpenAI-compatible client at it

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
  -H 'Authorization: Bearer change-me' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

Set `server.client_api_key_env` to `null` in local-only setups if you do not want a client API key.

## Roadmap

1. MVP proxy and token-aware rotation.
2. Provider adapters and protocol-aware routing for OpenAI, Anthropic, OpenRouter, LM Studio, Ollama, Groq, Mistral, Together, Fireworks, DeepSeek, and vLLM.
3. Atomic usage reservation for concurrent requests.
4. Per-model routing policies.
5. Admin API/UI for account health and usage.
6. Pluggable token counters and external stores for multi-process deployments.
7. Metrics, structured logs, and OpenTelemetry.
8. Provider capability discovery and `/v1/models` aggregation.

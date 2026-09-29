# Rotisserie Chicken — Design

## Core contract

Rotisserie Chicken presents one stable OpenAI-compatible API to the client. Upstream credentials are implementation details managed by the gateway.

## Components

### HTTP layer
FastAPI receives client requests and preserves the request body/model/tool parameters. The gateway currently proxies:

- `POST /v1/chat/completions`
- `POST /v1/completions`
- `POST /v1/responses`
- `GET /v1/models`

### Account registry
Each account specifies:

- an identifier
- a provider name
- an upstream base URL
- the environment variable containing its secret
- a token threshold
- a cooldown period
- an enabled flag

This makes providers configuration-driven rather than hard-coded dependencies. The provider registry selects the default protocol, while an account can explicitly select `openai`, `anthropic`, or `both`.

### Router
Two policies exist:

**Sequential:** keep using the current eligible account until its token threshold or cooldown makes it unavailable, then move to the next eligible account.

**Round-robin:** advance to the next eligible account on every request.

### Usage ledger
SQLite stores cumulative token usage and temporary cooldown state. The ledger survives process restarts.

The preferred accounting source is the upstream `usage` object. Chat Completions usage uses `total_tokens`; Responses usage uses `input_tokens + output_tokens` when needed. A rough text-length estimate exists only as a fallback for providers that omit usage.

### Failure handling
Configured HTTP statuses such as 429 and 5xx can temporarily disable an account and trigger one retry through the next eligible account. Streaming requests cannot be transparently retried after the response has started, so a streaming upstream failure is surfaced as an SSE error.

## Security boundaries

- Secrets are referenced through environment variables rather than YAML values.
- Client authentication is optional and intended for non-public deployments.
- The gateway does not bypass provider authentication, anti-abuse controls, or account-level restrictions.
- For public deployments, add TLS, stronger authentication, rate limiting, audit logging, and secret management before exposing the service to the internet.

## Next architectural step: atomic reservations

The MVP records usage after a response completes. That is sufficient for a single-agent/local deployment but concurrent requests can temporarily push an account over its configured threshold because multiple requests may select the same account before their usage is recorded.

The next version should add an atomic SQLite transaction that reserves a request budget before dispatch, then reconciles the reservation with the actual upstream usage after completion.

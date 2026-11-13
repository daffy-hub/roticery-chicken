# Rotisserie Chicken

Rotisserie Chicken is a self-hosted API gateway for applications that use AI model APIs. It gives downstream clients one local OpenAI-compatible API while routing requests to a configurable pool of upstream accounts, including OpenRouter. It can rotate between accounts based on reported token usage, temporarily cool down accounts after configured provider errors, and fail over to another eligible account.

The project is a Python 3.11+ application built with FastAPI. It stores account usage and cooldown state in SQLite and includes a small browser dashboard for viewing and managing configured accounts.

> **Use provider accounts in accordance with their terms, quotas, and usage policies.** Rotisserie Chicken is for legitimate API routing and availability management; it does not bypass provider limits or account controls.

## What it does

- Presents a single local API base URL to downstream applications.
- Proxies supported OpenAI-compatible endpoints:
  - `POST /v1/chat/completions`
  - `POST /v1/completions`
  - `POST /v1/responses`
  - `POST /v1/embeddings`
  - `POST /v1/moderations`
  - `POST /v1/images/generations`
  - `POST /v1/audio/speech`
  - `POST /v1/audio/transcriptions`
- Supports Anthropic Messages requests at `POST /v1/messages` and `POST /v1/messages/count_tokens`. OpenRouter accounts configured for both protocols can serve these requests as well as OpenAI-compatible calls.
- Routes across multiple configured upstream accounts, filtered by whether they support the incoming protocol.
- Offers sequential and round-robin account selection:
  - **Sequential** keeps selecting an account until it reaches its token threshold or is otherwise unavailable, then moves to another eligible account.
  - **Round-robin** advances to another eligible account on each selection.
- Records upstream-reported token usage where available. When usage is unavailable, the gateway may use a rough estimate; estimates are not authoritative provider billing data.
- Cools down an account after an HTTP status listed in `rotation.retry_statuses`, then tries other eligible accounts for the request. Cooldowns apply to that account for all downstream callers.
- Stores usage, cooldowns, and rotation state in a local SQLite database.
- Provides a browser dashboard at `/` for account configuration and connection tests, plus `/status` and `/healthz` endpoints.
- Supports optional downstream client authentication and upstream provider keys supplied through environment variables. Direct upstream keys can also be saved in account configuration, but environment variables or a managed secret store are safer for production.

## How request routing works

```text
Downstream app
     |  OpenAI-compatible API request
     v
Rotisserie Chicken (localhost:8080)
     |  select protocol-compatible account
     |  account eligible? -- enabled, below threshold, not cooling down
     |  provider returns configured retry status? -- cool down and retry another
     v
OpenRouter / another compatible provider / local endpoint
```

Each account has its own token threshold and cooldown duration, with global defaults in the `rotation` section. A non-streaming request that encounters a retryable status can be retried on other eligible accounts until one succeeds or the pool is exhausted. For streaming requests, failover is possible only before response chunks have been sent; after streaming has begun the gateway cannot safely restart the response on another account.

Token limits are routing thresholds, not guarantees about provider quotas or costs. Upstream usage may only be available after a request completes, and concurrent requests can exceed a threshold because usage is not reserved in advance.

## Requirements

- Python 3.11 or newer
- Internet access to install the Python dependencies
- One or more valid upstream provider API keys
- A free local port (the default is `8080`)

## Get the project

If you already have this repository:

```text
cd roticery-chicken
```

Otherwise, clone the repository and enter its folder:

```bash
git clone <repository-url>
cd roticery-chicken
```

Replace `<repository-url>` with the URL for your Git repository.

## Configure upstream accounts

Create your local configuration and environment file from the examples. The runtime config file and `.env` are local files and must not contain credentials committed to Git.

**Windows PowerShell**

```powershell
Copy-Item config\roticery.example.yaml config\roticery.yaml
Copy-Item .env.example .env
```

**macOS / Linux**

```bash
cp config/roticery.example.yaml config/roticery.yaml
cp .env.example .env
```

Edit `.env` and replace the example values:

```dotenv
ROTI_API_KEY=choose-a-long-private-client-key
ROTI_OR_01=your-first-upstream-provider-key
ROTI_OR_02=your-second-upstream-provider-key
```

`ROTI_API_KEY` is the optional key downstream applications send to protect access to the gateway. `ROTI_OR_01` and `ROTI_OR_02` are upstream provider keys used by the configured OpenRouter accounts. These credentials have different purposes. Keep real keys private and do not commit `.env`.

The example `config/roticery.example.yaml` configures two OpenRouter accounts, each referring to one of the `ROTI_OR_*` environment variables. To use only one account, remove or disable the other account in `config/roticery.yaml`. To add more accounts, give each a unique `id` and `api_key_env`.

Important configuration fields:

| Setting | Meaning |
| --- | --- |
| `server.host` / `server.port` | Interface and port the gateway listens on. The default is `127.0.0.1:8080`, for local use. |
| `server.client_api_key_env` | Environment variable containing the downstream client key. Set to `null` only for a trusted local-only setup. |
| `database` | SQLite file used to persist account usage and rotation state. |
| `rotation.strategy` | `sequential` or `round_robin`. |
| `rotation.default_token_threshold` | Default token usage threshold for accounts without their own threshold. |
| `rotation.retry_statuses` | Upstream HTTP status codes that trigger account cooldown and failover. |
| `rotation.default_cooldown_seconds` | Default cooldown duration for an account after a retryable error. |
| `accounts[].provider` | Provider identifier, such as `openrouter`, `openai`, `anthropic`, `groq`, or `lmstudio`. |
| `accounts[].base_url` | Upstream API base URL. |
| `accounts[].api_key_env` | Environment variable name containing this account's key. |
| `accounts[].protocol` | `openai`, `anthropic`, `both`, or `auto`. |
| `accounts[].token_threshold` / `cooldown_seconds` | Optional per-account overrides. |
| `models` | Optional static model list returned by `GET /v1/models`. |

`protocol: both` is appropriate for OpenRouter when you intend to use both OpenAI-compatible endpoints and Anthropic Messages. The gateway uses bearer authentication for OpenRouter and preserves the Anthropic version header for Anthropic-protocol calls.

## Install and run

Create a virtual environment and install the application with its test dependencies:

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

To load the simple `KEY=value` entries from `.env` into the current PowerShell process and start the service:

```powershell
Get-Content .env | ForEach-Object {
  if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
    [Environment]::SetEnvironmentVariable(
      $matches[1].Trim(),
      $matches[2].Trim().Trim('"'),
      'Process'
    )
  }
}
$env:ROTI_CONFIG = "config/roticery.yaml"
.\.venv\Scripts\roticery.exe --config config\roticery.yaml
```

**macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
set -a
source .env
set +a
export ROTI_CONFIG=config/roticery.yaml
roticery --config config/roticery.yaml
```

**Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
set -a
source .env
set +a
export ROTI_CONFIG=config/roticery.yaml
roticery --config config/roticery.yaml
```

The command runs in the foreground. Leave that terminal open while using the gateway; press **Ctrl+C** to stop it. On Windows, if `roticery.exe` is not present, install with the virtual environment's Python as shown above, then retry. You can also start the application using `python -m uvicorn roticery.cli:build_app --factory --host 127.0.0.1 --port 8080`, provided `ROTI_CONFIG` is set in that shell.

## Connect a downstream application

Configure an OpenAI-compatible client with:

- **Base URL:** `http://127.0.0.1:8080/v1`
- **API key:** the value of `ROTI_API_KEY` in `.env`, if `server.client_api_key_env` is configured
- **Model:** a model identifier accepted by your upstream provider, for example `openai/gpt-4o-mini` on OpenRouter

Example request:

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
  -H "Authorization: Bearer YOUR_ROTI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

Replace `YOUR_ROTI_API_KEY` with your configured client key. If client authentication is disabled for a trusted local setup, omit the `Authorization` header. The API key must never be embedded in a public browser application.

## Dashboard and operational endpoints

- `http://127.0.0.1:8080/` — dashboard to view, add, edit, delete, or test accounts.
- `http://127.0.0.1:8080/healthz` — basic process health response.
- `http://127.0.0.1:8080/status` — account enablement, token usage, thresholds, and cooldown status; when configured, send the downstream client authorization header.
- `http://127.0.0.1:8080/v1/models` — the optional static list configured under `models`.

The dashboard and its account-management endpoints are intended for local/trusted administration. Do not expose them directly to the public internet. For a remote deployment, place the service behind TLS and an access-controlled reverse proxy, restrict network access, and use managed secret storage.

## Development and tests

Activate the virtual environment, then run:

```bash
python -m pytest -q
```

The tests cover provider protocol compatibility, account rotation, token usage, dashboard account management, cooldown, and failover behavior. They mock upstream APIs; passing tests do not validate real provider credentials, external service availability, or production deployment security.

## Security and deployment notes

- Keep `.env` and any config containing direct API keys out of Git. The repository ignores `.env`, virtual environments, and local SQLite data by default.
- Prefer environment variables or a deployment platform's secret manager over direct keys in YAML or the dashboard.
- Keep the service bound to localhost unless a trusted network and appropriate access controls are in place.
- The downstream client key is not an upstream provider key. Downstream apps should receive only the gateway key; provider keys stay on the gateway host.
- Add TLS, firewall rules, rate limiting, backups, logging/monitoring, and a process supervisor appropriate to your hosting environment before public production use.
- SQLite persistence is intended for a single gateway process. Multi-process coordination and atomic usage reservations are not implemented.

## Current limitations

- Token thresholds are based on returned or estimated usage; usage is not reserved atomically before concurrent requests.
- Failover applies to configured HTTP status codes, not interpretation of provider-specific error-message text.
- Streaming requests cannot fail over after response chunks have already been sent to the client.
- The `/v1/models` endpoint returns the static configured list; it does not aggregate model catalogs from providers.
- The service does not provide production TLS termination, distributed state, per-model routing policy, or public-facing dashboard authentication.

## License

See [LICENSE](LICENSE).

from __future__ import annotations

import json
from pathlib import Path

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse, Response
from pydantic import BaseModel, Field

from .config import AccountConfig, AppConfig, load_config
from .management import find_account, remove_account, save_config, upsert_account
from .router import AccountRouter
from .storage import StateStore
from .upstream import UpstreamError, request_json, request_raw, stream_response


SUPPORTED_PATHS = {
    "/v1/chat/completions": "chat/completions",
    "/v1/completions": "completions",
    "/v1/responses": "responses",
    "/v1/embeddings": "embeddings",
    "/v1/moderations": "moderations",
    "/v1/images/generations": "images/generations",
    "/v1/audio/speech": "audio/speech",
    "/v1/audio/transcriptions": "audio/transcriptions",
}


class AccountRequest(BaseModel):
    id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    api_key_env: str = Field(min_length=1)
    token_threshold: int | None = Field(default=None, ge=1)
    cooldown_seconds: int | None = Field(default=None, ge=0)
    enabled: bool = True
    headers: dict[str, str] = Field(default_factory=dict)


def create_app(config: AppConfig, config_path: str | Path | None = None) -> FastAPI:
    store = StateStore(config.database)
    router = AccountRouter(config, store)
    client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=20.0))

    app = FastAPI(title="Roticery Chicken", version="0.1.0")
    app.state.config = config
    app.state.store = store
    app.state.router = router
    app.state.http_client = client
    app.state.config_path = Path(config_path) if config_path else None

    async def authorize(incoming_key: str | None) -> None:
        env_name = config.server.client_api_key_env
        if not env_name:
            return
        expected = __import__("os").getenv(env_name)
        if expected and incoming_key != f"Bearer {expected}":
            raise HTTPException(status_code=401, detail="Invalid client API key")

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await client.aclose()

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        from .dashboard import dashboard_response
        return dashboard_response()

    def require_config_path() -> Path:
        path = app.state.config_path
        if path is None:
            raise HTTPException(status_code=503, detail="Dashboard configuration management is unavailable for in-memory app instances")
        return path

    @app.get("/dashboard/accounts")
    async def dashboard_accounts() -> dict:
        return {
            "accounts": [
                {
                    "id": account.id,
                    "provider": account.provider,
                    "base_url": account.base_url,
                    "api_key_env": account.api_key_env,
                    "token_threshold": config.account_threshold(account),
                    "cooldown_seconds": config.account_cooldown(account),
                    "enabled": account.enabled,
                    "has_api_key": bool(__import__("os").getenv(account.api_key_env)),
                }
                for account in config.accounts
            ]
        }

    @app.post("/dashboard/accounts")
    async def dashboard_add_account(payload: AccountRequest) -> dict:
        require_config_path()
        if any(account.id == payload.id for account in config.accounts):
            raise HTTPException(status_code=409, detail="Account ID already exists")
        account = AccountConfig(**payload.model_dump())
        upsert_account(config, account)
        store.ensure_accounts([account.id])
        save_config(app.state.config_path, config)
        return {"status": "created", "account": {"id": account.id, "provider": account.provider}}

    @app.put("/dashboard/accounts/{account_id}")
    async def dashboard_update_account(account_id: str, payload: AccountRequest) -> dict:
        require_config_path()
        if payload.id != account_id:
            raise HTTPException(status_code=400, detail="Account ID in path and body must match")
        try:
            find_account(config, account_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Account not found") from exc
        account = AccountConfig(**payload.model_dump())
        upsert_account(config, account)
        store.ensure_accounts([account.id])
        save_config(app.state.config_path, config)
        return {"status": "updated", "account": {"id": account.id, "provider": account.provider}}

    @app.delete("/dashboard/accounts/{account_id}")
    async def dashboard_delete_account(account_id: str) -> dict:
        require_config_path()
        try:
            remove_account(config, account_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Account not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        save_config(app.state.config_path, config)
        return {"status": "deleted", "id": account_id}

    @app.post("/dashboard/accounts/{account_id}/test")
    async def dashboard_test_account(account_id: str) -> dict:
        try:
            account = find_account(config, account_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Account not found") from exc
        try:
            api_key = config.api_key_for(account)
        except RuntimeError as exc:
            return {"ok": False, "status": "missing_key", "message": str(exc)}

        import time
        started = time.perf_counter()
        url = account.base_url.rstrip("/") + "/models"
        headers = {"Authorization": f"Bearer {api_key}", **account.headers}
        try:
            response = await client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            return {"ok": False, "status": "network_error", "message": str(exc)}
        latency_ms = round((time.perf_counter() - started) * 1000)
        if response.is_success:
            return {"ok": True, "status": "online", "http_status": response.status_code, "latency_ms": latency_ms}
        return {
            "ok": False,
            "status": "auth_error" if response.status_code in (401, 403) else "upstream_error",
            "http_status": response.status_code,
            "latency_ms": latency_ms,
            "message": response.text[:200],
        }

    @app.get("/dashboard/data")
    async def dashboard_data() -> dict:
        accounts = []
        for account in config.accounts:
            state = store.get_state(account.id)
            threshold = config.account_threshold(account)
            accounts.append({
                "id": account.id,
                "provider": account.provider,
                "enabled": account.enabled,
                "tokens_used": state.tokens_used,
                "token_threshold": threshold,
                "remaining_tokens": max(0, threshold - state.tokens_used),
                "disabled_until": state.disabled_until,
            })
        return {"strategy": config.rotation.strategy, "accounts": accounts}

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/status")
    async def status(authorization: str | None = Header(default=None)) -> dict:
        await authorize(authorization)
        accounts = []
        for account in config.accounts:
            state = store.get_state(account.id)
            threshold = config.account_threshold(account)
            accounts.append(
                {
                    "id": account.id,
                    "provider": account.provider,
                    "enabled": account.enabled,
                    "tokens_used": state.tokens_used,
                    "token_threshold": threshold,
                    "remaining_tokens": max(0, threshold - state.tokens_used),
                    "disabled_until": state.disabled_until,
                }
            )
        return {"strategy": config.rotation.strategy, "accounts": accounts}

    @app.get("/v1/models")
    async def models(authorization: str | None = Header(default=None)) -> dict:
        await authorize(authorization)
        return {
            "object": "list",
            "data": [
                {"id": model.id, "object": "model", "owned_by": model.owned_by}
                for model in config.models
            ],
        }

    @app.post("/v1/{endpoint:path}")
    async def proxy(
        endpoint: str,
        request: Request,
        authorization: str | None = Header(default=None),
    ):
        path = f"/v1/{endpoint}"
        if path not in SUPPORTED_PATHS:
            raise HTTPException(status_code=404, detail=f"Unsupported endpoint: {path}")

        await authorize(authorization)
        content_type = request.headers.get("content-type", "")
        is_multipart = content_type.lower().startswith("multipart/")
        raw_body = await request.body() if is_multipart else None
        body = {} if is_multipart else await request.json()
        selected = router.select()
        account = selected.config

        try:
            api_key = config.api_key_for(account)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        stream = bool(body.get("stream"))

        if stream:
            def usage_callback(tokens: int) -> None:
                store.record_tokens(account.id, tokens)

            async def generator():
                try:
                    async for chunk in stream_response(
                        client,
                        account,
                        api_key,
                        SUPPORTED_PATHS[path],
                        body,
                        request.headers,
                        usage_callback,
                    ):
                        yield chunk
                except UpstreamError as exc:
                    store.disable(account.id, config.account_cooldown(account))
                    yield b"data: {\"error\":\"upstream request failed\"}\n\n"

            return StreamingResponse(generator(), media_type="text/event-stream")

        try:
            if is_multipart:
                response, tokens = await request_raw(client, account, api_key, SUPPORTED_PATHS[path], raw_body or b"", content_type, request.headers)
            else:
                response, tokens = await request_json(client, account, api_key, SUPPORTED_PATHS[path], body, request.headers)
        except UpstreamError as exc:
            if exc.status_code in config.rotation.retry_statuses:
                store.disable(account.id, config.account_cooldown(account))
                try:
                    retry = router.select()
                    retry_key = config.api_key_for(retry.config)
                    if is_multipart:
                        response, tokens = await request_raw(client, retry.config, retry_key, SUPPORTED_PATHS[path], raw_body or b"", content_type, request.headers)
                    else:
                        response, tokens = await request_json(client, retry.config, retry_key, SUPPORTED_PATHS[path], body, request.headers)
                    account = retry.config
                except (UpstreamError, RuntimeError):
                    return JSONResponse(
                        status_code=exc.status_code,
                        content=json.loads(exc.body.decode("utf-8"))
                        if exc.body
                        else {"error": "upstream request failed"},
                    )
            else:
                return JSONResponse(
                    status_code=exc.status_code,
                    content=json.loads(exc.body.decode("utf-8"))
                    if exc.body
                    else {"error": "upstream request failed"},
                )

        store.record_tokens(account.id, tokens)
        if "application/json" in response.headers.get("content-type", "").lower():
            return JSONResponse(content=response.json(), status_code=response.status_code)
        return Response(content=response.content, status_code=response.status_code, media_type=response.headers.get("content-type"))

    return app


def create_app_from_file(path: str | Path) -> FastAPI:
    return create_app(load_config(path), config_path=path)

from __future__ import annotations

import json
from pathlib import Path

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .config import AppConfig, load_config
from .router import AccountRouter
from .storage import StateStore
from .upstream import UpstreamError, request_json, stream_response


SUPPORTED_PATHS = {
    "/v1/chat/completions": "chat/completions",
    "/v1/completions": "completions",
    "/v1/responses": "responses",
}


def create_app(config: AppConfig) -> FastAPI:
    store = StateStore(config.database)
    router = AccountRouter(config, store)
    client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=20.0))

    app = FastAPI(title="Roticery Chicken", version="0.1.0")
    app.state.config = config
    app.state.store = store
    app.state.router = router
    app.state.http_client = client

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
        body = await request.json()
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
            response, tokens = await request_json(
                client,
                account,
                api_key,
                SUPPORTED_PATHS[path],
                body,
                request.headers,
            )
        except UpstreamError as exc:
            if exc.status_code in config.rotation.retry_statuses:
                store.disable(account.id, config.account_cooldown(account))
                try:
                    retry = router.select()
                    retry_key = config.api_key_for(retry.config)
                    response, tokens = await request_json(
                        client,
                        retry.config,
                        retry_key,
                        SUPPORTED_PATHS[path],
                        body,
                        request.headers,
                    )
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
        return JSONResponse(content=response.json(), status_code=response.status_code)

    return app


def create_app_from_file(path: str | Path) -> FastAPI:
    return create_app(load_config(path))

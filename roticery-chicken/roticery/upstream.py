from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .config import AccountConfig
from .usage import estimate_tokens, extract_usage


HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "host",
    "authorization",
}


class UpstreamError(Exception):
    def __init__(self, status_code: int, body: bytes):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Upstream returned HTTP {status_code}")


def build_headers(account: AccountConfig, api_key: str, incoming: httpx.Headers) -> dict[str, str]:
    headers = {
        k: v for k, v in incoming.items() if k.lower() not in HOP_BY_HOP
    }
    headers.update(account.headers)
    headers["Authorization"] = f"Bearer {api_key}"
    return headers


async def request_json(
    client: httpx.AsyncClient,
    account: AccountConfig,
    api_key: str,
    path: str,
    body: dict[str, Any],
    incoming_headers: httpx.Headers,
) -> tuple[httpx.Response, int]:
    url = f"{account.base_url.rstrip('/')}/{path.lstrip('/')}"
    response = await client.post(
        url,
        headers=build_headers(account, api_key, incoming_headers),
        json=body,
    )
    if response.status_code >= 400:
        raise UpstreamError(response.status_code, response.content)

    try:
        data = response.json()
    except json.JSONDecodeError:
        return response, estimate_tokens(body)
    return response, extract_usage(data)


async def stream_response(
    client: httpx.AsyncClient,
    account: AccountConfig,
    api_key: str,
    path: str,
    body: dict[str, Any],
    incoming_headers: httpx.Headers,
    on_usage,
) -> AsyncIterator[bytes]:
    url = f"{account.base_url.rstrip('/')}/{path.lstrip('/')}"
    async with client.stream(
        "POST",
        url,
        headers=build_headers(account, api_key, incoming_headers),
        json=body,
    ) as response:
        if response.status_code >= 400:
            raise UpstreamError(response.status_code, await response.aread())

        observed_usage = 0
        async for line in response.aiter_lines():
            raw = (line + "\n").encode()
            yield raw
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload and payload != "[DONE]":
                    try:
                        chunk = json.loads(payload)
                        observed_usage = max(observed_usage, extract_usage(chunk))
                    except json.JSONDecodeError:
                        pass

        on_usage(observed_usage or estimate_tokens(body))

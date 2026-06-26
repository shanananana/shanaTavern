from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from config import settings


class LLMError(Exception):
    pass


def _llm_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=settings.llm_connect_timeout,
        read=settings.llm_read_timeout,
        write=settings.llm_connect_timeout,
        pool=settings.llm_connect_timeout,
    )


async def list_models() -> list[str]:
    url = f"{settings.llm_base_url.rstrip('/')}/models"
    headers = {}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    async with httpx.AsyncClient(timeout=_llm_timeout()) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return [m["id"] for m in data.get("data", [])]


async def check_connection() -> tuple[bool, list[str]]:
    try:
        models = await list_models()
        return True, models
    except (httpx.HTTPError, json.JSONDecodeError, KeyError):
        return False, []


async def chat_completion_stream(
    messages: list[dict[str, str]],
) -> AsyncIterator[str]:
    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": settings.llm_temperature,
        "top_p": settings.llm_top_p,
        "max_tokens": settings.llm_max_tokens,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=_llm_timeout()) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise LLMError(
                    f"LLM 请求失败 ({resp.status_code}): {body.decode(errors='replace')[:500]}"
                )
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = line[6:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    data = json.loads(chunk)
                    delta = data["choices"][0].get("delta", {})
                    text = delta.get("content", "")
                    if text:
                        yield text
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue


async def chat_completion(messages: list[dict[str, str]]) -> str:
    parts: list[str] = []
    async for token in chat_completion_stream(messages):
        parts.append(token)
    return "".join(parts)

"""Model provider abstraction with OpenRouter as the first provider."""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator

import aiosqlite
import httpx

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
APP_TITLE = "OpenClaw Mission Control"
APP_REFERER = "https://github.com/adamwahla1/openclaw-mission-control"


@dataclass
class ProviderResponse:
    content: str
    provider: str
    requested_model: str
    actual_model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    raw: dict[str, Any] | None = None


class ModelProvider:
    provider = "base"

    async def list_models(self, db: aiosqlite.Connection) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def chat(
        self,
        db: aiosqlite.Connection,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.4,
        max_tokens: int = 2048,
        routing_policy: str = "pinned",
    ) -> ProviderResponse:
        raise NotImplementedError

    async def stream_chat(
        self,
        db: aiosqlite.Connection,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.4,
        max_tokens: int = 2048,
        routing_policy: str = "pinned",
    ) -> AsyncIterator[dict[str, Any]]:
        response = await self.chat(db, messages, model, temperature, max_tokens, routing_policy)
        yield {"type": "message.delta", "content": response.content}
        yield {"type": "message.completed", "response": response}

    async def test(self, db: aiosqlite.Connection, api_key: str | None = None) -> dict[str, Any]:
        raise NotImplementedError


async def get_provider_config(db: aiosqlite.Connection, provider: str) -> dict[str, Any]:
    async with db.execute(
        "SELECT * FROM provider_configs WHERE provider = ?",
        (provider,),
    ) as cursor:
        row = await cursor.fetchone()
    if not row:
        return {}
    data = dict(row)
    try:
        data["config"] = json.loads(data.get("config") or "{}")
    except (json.JSONDecodeError, TypeError):
        data["config"] = {}
    return data


async def upsert_provider_config(
    db: aiosqlite.Connection,
    provider: str,
    display_name: str,
    enabled: bool,
    config: dict[str, Any],
) -> dict[str, Any]:
    existing = await get_provider_config(db, provider)
    provider_id = existing.get("id") or f"provider-{provider}"
    merged_config = dict(existing.get("config") or {})
    merged_config.update({k: v for k, v in config.items() if v is not None})

    await db.execute(
        """
        INSERT INTO provider_configs (id, provider, display_name, enabled, config, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(provider) DO UPDATE SET
            display_name = excluded.display_name,
            enabled = excluded.enabled,
            config = excluded.config,
            updated_at = datetime('now')
        """,
        (provider_id, provider, display_name, 1 if enabled else 0, json.dumps(merged_config)),
    )
    await db.commit()
    return await get_provider_config(db, provider)


def redact_provider_config(row: dict[str, Any]) -> dict[str, Any]:
    config = dict(row.get("config") or {})
    api_key = config.pop("api_key", "")
    return {
        "id": row.get("id"),
        "provider": row.get("provider"),
        "display_name": row.get("display_name"),
        "enabled": bool(row.get("enabled", 0)),
        "configured": bool(api_key),
        "api_key_preview": f"{api_key[:8]}..." if len(api_key) > 8 else "",
        "config": config,
        "last_test_status": row.get("last_test_status"),
        "last_test_message": row.get("last_test_message"),
        "last_tested_at": row.get("last_tested_at"),
        "updated_at": row.get("updated_at"),
    }


class OpenRouterProvider(ModelProvider):
    provider = "openrouter"

    async def _headers(self, db: aiosqlite.Connection, api_key: str | None = None) -> dict[str, str]:
        config = await get_provider_config(db, self.provider)
        cfg = config.get("config") or {}
        key = api_key or cfg.get("api_key") or ""
        if not key:
            raise RuntimeError("OpenRouter API key is not configured")
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": cfg.get("referer") or APP_REFERER,
            "X-OpenRouter-Title": cfg.get("app_title") or APP_TITLE,
        }

    async def _base_url(self, db: aiosqlite.Connection) -> str:
        config = await get_provider_config(db, self.provider)
        cfg = config.get("config") or {}
        return (cfg.get("base_url") or OPENROUTER_BASE_URL).rstrip("/")

    async def list_models(self, db: aiosqlite.Connection) -> list[dict[str, Any]]:
        headers = await self._headers(db)
        base_url = await self._base_url(db)
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(f"{base_url}/models", headers=headers)
            resp.raise_for_status()
            data = resp.json()
        models = data.get("data", []) if isinstance(data, dict) else []
        return [
            {
                "id": item.get("id"),
                "name": item.get("name") or item.get("id"),
                "context_length": item.get("context_length"),
                "pricing": item.get("pricing", {}),
                "supported_parameters": item.get("supported_parameters", []),
            }
            for item in models
            if item.get("id")
        ]

    async def test(self, db: aiosqlite.Connection, api_key: str | None = None) -> dict[str, Any]:
        try:
            headers = await self._headers(db, api_key=api_key)
            base_url = await self._base_url(db)
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{base_url}/models", headers=headers)
                resp.raise_for_status()
                data = resp.json()
            count = len(data.get("data", [])) if isinstance(data, dict) else 0
            await self._record_test(db, "ok", f"Connected. {count} models available.")
            return {"ok": True, "model_count": count, "message": f"Connected. {count} models available."}
        except Exception as exc:
            message = str(exc)
            await self._record_test(db, "error", message)
            return {"ok": False, "error": message}

    async def _record_test(self, db: aiosqlite.Connection, status: str, message: str) -> None:
        await db.execute(
            """
            UPDATE provider_configs
            SET last_test_status = ?, last_test_message = ?, last_tested_at = datetime('now')
            WHERE provider = 'openrouter'
            """,
            (status, message[:500]),
        )
        await db.commit()

    def _request_model(self, model: str, routing_policy: str) -> tuple[str, dict[str, Any]]:
        provider: dict[str, Any] = {}
        if routing_policy == "auto":
            return "openrouter/auto", provider
        if routing_policy == "cheap":
            provider["sort"] = "price"
        elif routing_policy == "fast":
            provider["sort"] = "latency"
        elif routing_policy == "strong":
            provider["allow_fallbacks"] = True
        return model or "openrouter/auto", provider

    async def chat(
        self,
        db: aiosqlite.Connection,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.4,
        max_tokens: int = 2048,
        routing_policy: str = "pinned",
    ) -> ProviderResponse:
        headers = await self._headers(db)
        base_url = await self._base_url(db)
        request_model, provider_preferences = self._request_model(model, routing_policy)
        payload: dict[str, Any] = {
            "model": request_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if provider_preferences:
            payload["provider"] = provider_preferences

        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        latency_ms = int((time.perf_counter() - started) * 1000)

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        usage = data.get("usage") or {}
        input_tokens = int(usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
        actual_model = data.get("model") or request_model

        return ProviderResponse(
            content=message.get("content") or "",
            provider=self.provider,
            requested_model=request_model,
            actual_model=actual_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            raw=data,
        )


PROVIDERS: dict[str, ModelProvider] = {"openrouter": OpenRouterProvider()}


async def get_model_config(db: aiosqlite.Connection, purpose: str) -> dict[str, Any]:
    async with db.execute("SELECT * FROM model_configs WHERE purpose = ?", (purpose,)) as cursor:
        row = await cursor.fetchone()
    if row:
        return dict(row)
    async with db.execute("SELECT * FROM model_configs WHERE purpose = 'cheap_fast'") as cursor:
        row = await cursor.fetchone()
    return dict(row) if row else {
        "provider": "openrouter",
        "model": "openrouter/auto",
        "routing_policy": "auto",
        "temperature": 0.4,
        "max_tokens": 2048,
    }


async def record_provider_cost(
    db: aiosqlite.Connection,
    response: ProviderResponse,
    operation: str,
    agent_id: str | None = None,
    task_id: str | None = None,
    run_id: str | None = None,
) -> None:
    from services.cost_tracker import estimate_cost

    cost = estimate_cost(response.actual_model, response.input_tokens, response.output_tokens)
    response.cost_usd = cost
    await db.execute(
        """
        INSERT INTO cost_records
            (id, agent_id, task_id, run_id, model, operation, input_tokens, output_tokens,
             total_tokens, cost, currency, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'USD', datetime('now'))
        """,
        (
            f"cost-{uuid.uuid4().hex[:8]}",
            agent_id,
            task_id,
            run_id,
            response.actual_model,
            operation,
            response.input_tokens,
            response.output_tokens,
            response.total_tokens,
            cost,
        ),
    )
    await db.commit()

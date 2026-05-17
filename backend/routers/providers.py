"""Provider and model configuration endpoints."""
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import get_db
from services.providers import PROVIDERS, get_provider_config, redact_provider_config, upsert_provider_config

router = APIRouter(tags=["providers"])


class ProviderConfigRequest(BaseModel):
    provider: str = "openrouter"
    display_name: str = "OpenRouter"
    enabled: bool = True
    api_key: str | None = None
    base_url: str | None = None
    referer: str | None = None
    app_title: str | None = None


class OpenRouterTestRequest(BaseModel):
    api_key: str | None = None


class ModelConfigRequest(BaseModel):
    purpose: str
    provider: str = "openrouter"
    model: str
    routing_policy: str = "pinned"
    temperature: float = 0.4
    max_tokens: int = 2048
    enabled: bool = True


@router.get("/api/providers")
async def list_providers():
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM provider_configs ORDER BY provider")
    return [redact_provider_config(_parse_provider_row(row)) for row in rows]


@router.post("/api/providers")
async def save_provider(body: ProviderConfigRequest):
    if body.provider not in PROVIDERS:
        raise HTTPException(400, f"Unsupported provider: {body.provider}")
    db = await get_db()
    existing = await get_provider_config(db, body.provider)
    existing_config = existing.get("config") or {}
    config: dict[str, Any] = {
        "api_key": body.api_key if body.api_key else existing_config.get("api_key", ""),
        "base_url": body.base_url,
        "referer": body.referer,
        "app_title": body.app_title,
    }
    row = await upsert_provider_config(db, body.provider, body.display_name, body.enabled, config)
    return redact_provider_config(row)


@router.post("/api/providers/openrouter/test")
async def test_openrouter(body: OpenRouterTestRequest):
    db = await get_db()
    provider = PROVIDERS["openrouter"]
    return await provider.test(db, api_key=body.api_key)


@router.get("/api/providers/openrouter/models")
async def list_openrouter_models():
    db = await get_db()
    try:
        models = await PROVIDERS["openrouter"].list_models(db)
        return {"ok": True, "models": models}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "models": []}


@router.get("/api/model-configs")
async def list_model_configs():
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM model_configs ORDER BY purpose")
    return [dict(row) for row in rows]


@router.post("/api/model-configs")
async def save_model_config(body: ModelConfigRequest):
    db = await get_db()
    if body.routing_policy not in {"pinned", "cheap", "fast", "strong", "auto"}:
        raise HTTPException(400, "Invalid routing_policy")
    config_id = f"model-{body.purpose}"
    await db.execute(
        """
        INSERT INTO model_configs
            (id, purpose, provider, model, routing_policy, temperature, max_tokens, enabled, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(purpose) DO UPDATE SET
            provider = excluded.provider,
            model = excluded.model,
            routing_policy = excluded.routing_policy,
            temperature = excluded.temperature,
            max_tokens = excluded.max_tokens,
            enabled = excluded.enabled,
            updated_at = datetime('now')
        """,
        (
            config_id,
            body.purpose,
            body.provider,
            body.model,
            body.routing_policy,
            body.temperature,
            body.max_tokens,
            1 if body.enabled else 0,
        ),
    )
    await db.commit()
    async with db.execute("SELECT * FROM model_configs WHERE purpose = ?", (body.purpose,)) as cursor:
        return dict(await cursor.fetchone())


def _parse_provider_row(row) -> dict[str, Any]:
    data = dict(row)
    try:
        data["config"] = json.loads(data.get("config") or "{}")
    except (json.JSONDecodeError, TypeError):
        data["config"] = {}
    return data

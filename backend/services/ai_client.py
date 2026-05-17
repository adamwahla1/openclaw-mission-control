"""Provider-backed AI client used by debates, autopilot, and legacy callers."""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

from database import get_db
from services.providers import PROVIDERS, get_model_config, get_provider_config, record_provider_cost

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = os.environ.get("GEMINI_WORKSHOP_BASE_URL", "")
GEMINI_API_KEY = os.environ.get("GEMINI_WORKSHOP_API_KEY", "")
GEMINI_DEFAULT_MODEL = "gemini-2.0-flash-lite"
DEFAULT_MODEL = "openrouter/auto"

_client: Optional[httpx.AsyncClient] = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=60.0)
    return _client


async def generate(
    prompt: str,
    system: str = "",
    history: list[dict] | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1024,
    temperature: float = 0.8,
) -> str:
    """Generate text through the configured Mission Control provider layer."""
    provider_text = await _generate_with_provider(
        prompt=prompt,
        system=system,
        history=history,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if provider_text is not None:
        return provider_text

    if GEMINI_BASE_URL and GEMINI_API_KEY:
        return await _generate_with_gemini(
            prompt=prompt,
            system=system,
            history=history,
            model=model if model and model.startswith("gemini") else GEMINI_DEFAULT_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    return _offline_response(prompt)


async def generate_json(
    prompt: str,
    system: str = "",
    history: list[dict] | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2048,
    temperature: float = 0.6,
) -> str:
    """Generate a response expected to contain structured output."""
    return await generate(
        prompt=prompt,
        system=system,
        history=history,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )


async def _generate_with_provider(
    prompt: str,
    system: str,
    history: list[dict] | None,
    model: str,
    max_tokens: int,
    temperature: float,
) -> str | None:
    try:
        db = await get_db()
        cfg = await get_model_config(db, "cheap_fast")
        provider_name = cfg.get("provider") or "openrouter"
        provider = PROVIDERS.get(provider_name)
        provider_config = await get_provider_config(db, provider_name)
        provider_settings = provider_config.get("config") or {}
        if not provider or not provider_config.get("enabled") or not provider_settings.get("api_key"):
            return None

        requested_model = model if model and model != DEFAULT_MODEL else cfg.get("model", DEFAULT_MODEL)
        messages = _build_openai_messages(prompt, system, history)
        response = await provider.chat(
            db,
            messages=messages,
            model=requested_model,
            temperature=temperature if temperature is not None else float(cfg.get("temperature", 0.4)),
            max_tokens=max_tokens or int(cfg.get("max_tokens", 2048)),
            routing_policy=cfg.get("routing_policy", "auto"),
        )
        await record_provider_cost(db, response, operation="ai_client.generate")
        return response.content
    except Exception as exc:
        logger.warning("Provider AI client call failed; falling back: %s", exc)
        return None


def _build_openai_messages(prompt: str, system: str, history: list[dict] | None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    for turn in history or []:
        role = turn.get("role", "user")
        if role == "model":
            role = "assistant"
        if role not in {"user", "assistant", "system"}:
            role = "user"
        content = turn.get("content") or turn.get("text") or ""
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt})
    return messages


async def _generate_with_gemini(
    prompt: str,
    system: str = "",
    history: list[dict] | None = None,
    model: str = GEMINI_DEFAULT_MODEL,
    max_tokens: int = 1024,
    temperature: float = 0.8,
) -> str:
    contents: list[dict] = []
    system_instruction = {"parts": [{"text": system}]} if system else None

    if history:
        for turn in history:
            role = turn.get("role", "user")
            text = turn.get("text") or turn.get("content") or ""
            if role == "assistant":
                role = "model"
            if role in ("user", "model") and text:
                contents.append({"role": role, "parts": [{"text": text}]})

    contents.append({"role": "user", "parts": [{"text": prompt}]})
    payload: dict = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    if system_instruction:
        payload["systemInstruction"] = system_instruction

    url = f"{GEMINI_BASE_URL}/v1beta/models/{model}:generateContent"
    headers = {
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json",
    }

    client = await _get_client()
    resp = await client.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()

    candidates = data.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        if parts:
            return parts[0].get("text", "")

    feedback = data.get("promptFeedback", {})
    block_reason = feedback.get("blockReason", "")
    if block_reason:
        logger.warning("Gemini response blocked: %s", block_reason)
        return f"[Response blocked: {block_reason}]"
    return ""


def _offline_response(prompt: str) -> str:
    title = prompt.strip().splitlines()[0][:140] if prompt.strip() else "this request"
    return (
        "## Native Runtime Draft\n\n"
        "Mission Control is running locally, but no model provider is configured yet. "
        f"Configure OpenRouter in Settings to generate a live response for: {title}\n\n"
        "This placeholder keeps existing debate, autopilot, and task surfaces usable while provider setup is pending."
    )

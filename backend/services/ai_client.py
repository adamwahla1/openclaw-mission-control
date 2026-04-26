"""Lightweight Gemini API client for AI-powered features."""

import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL = os.environ.get("GEMINI_WORKSHOP_BASE_URL", "")
API_KEY = os.environ.get("GEMINI_WORKSHOP_API_KEY", "")
DEFAULT_MODEL = "gemini-2.0-flash-lite"

# ── Client singleton ─────────────────────────────────────────────────────────

_client: Optional[httpx.AsyncClient] = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=60.0)
    return _client


# ── Public API ────────────────────────────────────────────────────────────────

async def generate(
    prompt: str,
    system: str = "",
    history: list[dict] | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1024,
    temperature: float = 0.8,
) -> str:
    """
    Generate a response using the Gemini API.

    Args:
        prompt: User message
        system: System instruction (appended as first 'user' turn with context prefix)
        history: List of {'role': 'user'|'model', 'text': str} turns
        model: Model name
        max_tokens: Max output tokens
        temperature: Sampling temperature

    Returns:
        Generated text string
    """
    if not BASE_URL or not API_KEY:
        raise RuntimeError("Gemini API not configured (missing GEMINI_WORKSHOP_BASE_URL or GEMINI_WORKSHOP_API_KEY)")

    # Build contents array for Gemini format
    contents: list[dict] = []

    # System instruction via systemInstruction field
    system_instruction = None
    if system:
        system_instruction = {"parts": [{"text": system}]}

    # Add history turns
    if history:
        for turn in history:
            role = turn.get("role", "user")
            text = turn.get("text", "")
            if role in ("user", "model") and text:
                contents.append({"role": role, "parts": [{"text": text}]})

    # Add current prompt
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

    url = f"{BASE_URL}/v1beta/models/{model}:generateContent"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    client = await _get_client()
    try:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "")

        # Fallback: check promptFeedback for block reason
        feedback = data.get("promptFeedback", {})
        block_reason = feedback.get("blockReason", "")
        if block_reason:
            logger.warning(f"Gemini response blocked: {block_reason}")
            return f"[Response blocked: {block_reason}]"

        return ""

    except httpx.HTTPStatusError as e:
        logger.error(f"Gemini API error {e.response.status_code}: {e.response.text[:300]}")
        raise
    except Exception as e:
        logger.error(f"Gemini request failed: {e}")
        raise


async def generate_json(
    prompt: str,
    system: str = "",
    history: list[dict] | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2048,
    temperature: float = 0.6,
) -> str:
    """Generate a response expected to contain structured output (markdown, JSON, etc.)."""
    return await generate(
        prompt=prompt,
        system=system,
        history=history,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )

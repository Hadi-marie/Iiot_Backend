from __future__ import annotations

import logging

import httpx

from .config import settings

logger = logging.getLogger(__name__)


def llm_available() -> bool:
    if settings.llm_provider == "openai":
        return bool(settings.openai_api_key)
    if settings.llm_provider == "ollama":
        return True
    return False


def generate(system_prompt: str, user_prompt: str) -> str | None:
    """Single-turn helper (kept for convenience)."""
    return generate_chat(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    )


def generate_chat(messages: list[dict]) -> str | None:
    """Generate from a full message list (system + prior turns + current). Returns None if
    the LLM is disabled or unreachable."""
    if not settings.llm_enabled:
        return None
    try:
        if settings.llm_provider == "openai":
            return _openai_chat(messages)
        if settings.llm_provider == "ollama":
            return _ollama_chat(messages)
    except Exception as exc:  # pragma: no cover - network dependent
        logger.warning("LLM generation failed (%s); falling back to retrieval.", exc)
        return None
    return None


def _openai_chat(messages: list[dict]) -> str:
    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    payload: dict = {"model": settings.openai_chat_model, "messages": messages}
    # The GPT-5 family only supports the default temperature; older models accept a custom one.
    if not settings.openai_chat_model.lower().startswith("gpt-5"):
        payload["temperature"] = 0.2
    with httpx.Client(timeout=90.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def _ollama_chat(messages: list[dict]) -> str:
    url = f"{settings.ollama_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "options": {"temperature": 0.2},
        "messages": messages,
    }
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["message"]["content"].strip()

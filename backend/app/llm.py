"""Client for a lightweight local LLM over the OpenAI-compatible chat API.

Default target is Ollama running qwen2.5:3b-instruct (bilingual Arabic/English, ~2 GB,
runs on CPU or a single small GPU). Any OpenAI-compatible server can be swapped in.
Every caller has a deterministic fallback, so Precast keeps working if the model is down.
"""
from __future__ import annotations

import json
import re
import time

import httpx

from . import config

_status = {"ok": None, "checked": 0.0, "detail": ""}


def status(force: bool = False) -> dict:
    if not config.LLM_ENABLED:
        return {"available": False, "engine": "template", "model": None, "detail": "LLM disabled by configuration"}
    if force or time.time() - _status["checked"] > 30:
        try:
            r = httpx.get(f"{config.LLM_BASE_URL}/models", timeout=3,
                          headers={"Authorization": f"Bearer {config.LLM_API_KEY}"})
            r.raise_for_status()
            models = [m.get("id") for m in r.json().get("data", [])]
            ok = not models or any(config.LLM_MODEL.split(":")[0] in (m or "") for m in models)
            _status.update(ok=ok, detail="" if ok else f"Model {config.LLM_MODEL} not pulled; available: {', '.join(models)[:200]}")
        except Exception as e:  # noqa: BLE001
            _status.update(ok=False, detail=f"Cannot reach {config.LLM_BASE_URL}: {type(e).__name__}")
        _status["checked"] = time.time()
    return {"available": bool(_status["ok"]), "engine": "llm" if _status["ok"] else "template",
            "model": config.LLM_MODEL, "endpoint": config.LLM_BASE_URL, "detail": _status["detail"]}


def chat(messages: list[dict], *, json_mode: bool = False, temperature: float = 0.2, max_tokens: int = 900) -> str | None:
    """Return the model's reply, or None if the model is unavailable (caller falls back)."""
    if not status()["available"]:
        return None
    body = {"model": config.LLM_MODEL, "messages": messages, "temperature": temperature, "max_tokens": max_tokens,
            "stream": False}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        r = httpx.post(f"{config.LLM_BASE_URL}/chat/completions", json=body, timeout=config.LLM_TIMEOUT,
                       headers={"Authorization": f"Bearer {config.LLM_API_KEY}"})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:  # noqa: BLE001
        _status.update(ok=False, checked=time.time(), detail="Last request failed")
        return None


def chat_json(messages: list[dict], **kw) -> dict | None:
    out = chat(messages, json_mode=True, **kw)
    if not out:
        return None
    m = re.search(r"\{.*\}", out, re.S)
    try:
        return json.loads(m.group(0) if m else out)
    except (json.JSONDecodeError, AttributeError):
        return None


def is_arabic(text: str) -> bool:
    return bool(re.search(r"[؀-ۿ]", text or ""))

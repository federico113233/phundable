# -*- coding: utf-8 -*-
"""
Groq Cloud client for Phundable.

Deliberately small and dependency-free (stdlib urllib) so the app keeps its
"no install needed" property beyond python-docx.

Design notes:
  * Groq sits behind Cloudflare, which rejects urllib's default User-Agent with
    HTTP 403 / error 1010. We always send an explicit client User-Agent.
  * The model catalogue differs per account, so we query /models once and pick
    the best available from a preference list instead of hardcoding an id.
  * Every failure path raises LLMUnavailable so callers can fall back to
    template prose. A live demo must never hard-fail because an API is down.
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

BASE_URL = "https://api.groq.com/openai/v1"
USER_AGENT = "phundable/1.0 (python-urllib)"
TIMEOUT = 60

# Best first. Chosen for instruction-following and French/English quality.
MODEL_PREFERENCE = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-20b",
    "groq/compound",
]

# Substrings marking models that cannot do chat completion (speech, TTS,
# safety classifiers) or are language-specialised away from EN/FR.
_NON_CHAT = ("whisper", "orpheus", "prompt-guard", "allam", "safeguard")

_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
_model_cache = None


class LLMUnavailable(Exception):
    """Raised whenever we cannot get a completion, for any reason."""


class RateLimited(LLMUnavailable):
    """429 from the provider. Carries how long the provider asked us to wait."""

    def __init__(self, message, retry_after=None):
        LLMUnavailable.__init__(self, message)
        self.retry_after = retry_after


def load_env(path=_ENV_PATH):
    """Read a simple KEY=VALUE .env file. Real env vars win over the file."""
    values = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    for key in list(values):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def api_key():
    key = load_env().get("GROQ_API_KEY", "")
    if not key:
        raise LLMUnavailable("GROQ_API_KEY is not set in server/.env")
    return key


def _request(path, payload=None, timeout=TIMEOUT):
    headers = {
        "Authorization": "Bearer " + api_key(),
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        if exc.code == 429:
            wait = None
            header = exc.headers.get("retry-after") if exc.headers else None
            if header:
                try:
                    wait = float(header)
                except ValueError:
                    wait = None
            if wait is None:
                # Groq states the wait inside the message, e.g. "try again in 7.29s"
                found = re.search(r"try again in ([\d.]+)\s*s", body, re.I)
                if found:
                    wait = float(found.group(1))
                else:
                    found = re.search(r"try again in ([\d.]+)m([\d.]+)s", body, re.I)
                    if found:
                        wait = float(found.group(1)) * 60 + float(found.group(2))
            raise RateLimited("rate limited by Groq: %s" % body, retry_after=wait)
        raise LLMUnavailable("HTTP %s from Groq: %s" % (exc.code, body))
    except Exception as exc:
        raise LLMUnavailable("could not reach Groq: %r" % (exc,))


def available_models():
    data = _request("/models", timeout=20)
    return sorted(m["id"] for m in data.get("data", []))


def pick_model(force_refresh=False):
    """Best chat model this account can actually use. Cached after first call."""
    global _model_cache
    if _model_cache and not force_refresh:
        return _model_cache
    ids = available_models()
    chat_models = [m for m in ids if not any(bad in m.lower() for bad in _NON_CHAT)]
    for preferred in MODEL_PREFERENCE:
        if preferred in chat_models:
            _model_cache = preferred
            return preferred
    if chat_models:
        _model_cache = chat_models[0]
        return _model_cache
    raise LLMUnavailable("no chat-capable model available on this account")


def chat(system, user, temperature=0.4, max_tokens=1600, retries=2):
    """Single-turn completion. Raises LLMUnavailable rather than returning junk."""
    model = pick_model()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    last_error = None
    for attempt in range(retries + 1):
        try:
            data = _request("/chat/completions", payload)
            text = data["choices"][0]["message"]["content"].strip()
            if not text:
                raise LLMUnavailable("empty completion")
            return text
        except RateLimited as exc:
            last_error = exc
            delay = exc.retry_after if exc.retry_after else 20.0
            delay = min(delay + 1.0, 65.0)
            if attempt < retries:
                time.sleep(delay)
        except LLMUnavailable as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise last_error


def chat_json(system, user, temperature=0.1, max_tokens=2500, retries=2):
    """Completion constrained to a JSON object. Returns a parsed dict.

    Used by the offline enrichment pass, never on a request path that scores.
    """
    model = pick_model()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    last_error = None
    for attempt in range(retries + 1):
        try:
            data = _request("/chat/completions", payload)
            text = data["choices"][0]["message"]["content"].strip()
            try:
                return json.loads(text)
            except ValueError:
                # Some models wrap JSON in prose or fences; salvage the object.
                match = re.search(r"\{.*\}", text, re.S)
                if not match:
                    raise LLMUnavailable("no JSON object in completion")
                return json.loads(match.group(0))
        except RateLimited as exc:
            last_error = exc
            delay = exc.retry_after if exc.retry_after else 20.0
            delay = min(delay + 1.0, 65.0)
            if attempt < retries:
                time.sleep(delay)
        except (LLMUnavailable, ValueError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(2.0 * (attempt + 1))
    raise LLMUnavailable("could not obtain JSON: %r" % (last_error,))


def health():
    """Diagnostic summary used by the server's /api/health endpoint."""
    try:
        return {"ok": True, "model": pick_model(), "models": available_models()}
    except LLMUnavailable as exc:
        return {"ok": False, "error": str(exc)}

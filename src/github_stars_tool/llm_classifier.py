from __future__ import annotations

import json
from urllib import error, request

from .config import ProjectConfig


SYSTEM_PROMPT = """You classify GitHub repositories into one category from a fixed list.
Return strict JSON with keys: category, reason, confidence.
confidence must be a number from 0 to 1.
Do not return markdown."""


def _post_json(url: str, api_key: str, payload: dict) -> dict:
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if "<html" in detail.lower() or "cloudflare" in detail.lower() or "attention required" in detail.lower():
            raise RuntimeError(
                "LLM classify request was blocked by an HTML challenge page "
                f"(HTTP {exc.code}). The configured provider may be behind Cloudflare or another anti-bot layer. "
                "Try a direct API origin, a provider-specific allowlist, or a different endpoint."
            ) from exc
        raise RuntimeError(f"LLM classify request failed: HTTP {exc.code} {detail}") from exc


def _extract_json_block(text: str) -> dict:
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start:end + 1])
    raise RuntimeError(f"Could not parse JSON from LLM response: {text[:300]}")


def _call_chat_completions(config: ProjectConfig, api_key: str, prompt: dict) -> dict:
    payload = {
        "model": config.llm_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        "temperature": config.llm_temperature,
    }
    if config.llm_structured_output == "json_object":
        payload["response_format"] = {"type": "json_object"}
    body = _post_json(f"{config.llm_base_url.rstrip('/')}/chat/completions", api_key, payload)
    content = body["choices"][0]["message"]["content"]
    return _extract_json_block(content)


def _call_responses(config: ProjectConfig, api_key: str, prompt: dict) -> dict:
    payload = {
        "model": config.llm_model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": SYSTEM_PROMPT}]},
            {"role": "user", "content": [{"type": "input_text", "text": json.dumps(prompt, ensure_ascii=False)}]},
        ],
        "temperature": config.llm_temperature,
    }
    if config.llm_structured_output == "json_object":
        payload["text"] = {"format": {"type": "json_object"}}
    body = _post_json(f"{config.llm_base_url.rstrip('/')}/responses", api_key, payload)
    text = body.get("output_text")
    if not text:
        chunks = []
        for item in body.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    chunks.append(content["text"])
        text = "\n".join(chunks)
    return _extract_json_block(text or "")


def classify_repo_with_llm(config: ProjectConfig, categories: list[str], repo: dict) -> dict:
    api_key = config.llm_api_key
    if not api_key:
        raise RuntimeError(f"Environment variable {config.llm_api_key_env} is not set.")

    prompt = {
        "categories": categories,
        "repo": {
            "full_name": repo.get("full_name"),
            "description": repo.get("description"),
            "language": repo.get("language"),
            "topics": repo.get("topics", []),
            "stars": repo.get("stars"),
        },
        "instruction": "Choose the single best category.",
    }
    if config.llm_provider != "openai_compatible":
        raise RuntimeError(f"Unsupported llm provider: {config.llm_provider}")
    if config.llm_endpoint == "chat_completions":
        result = _call_chat_completions(config, api_key, prompt)
    elif config.llm_endpoint == "responses":
        result = _call_responses(config, api_key, prompt)
    else:
        raise RuntimeError(f"Unsupported llm endpoint: {config.llm_endpoint}")
    return {
        "category": result["category"],
        "reason": result.get("reason", "ai"),
        "confidence": result.get("confidence", 0),
        "source": "ai",
    }

import json
import time
import urllib.request
import urllib.error
from typing import Optional

from .config import Config


def call_llm(messages: list[dict], config: Config) -> Optional[str]:
    """Call an OpenAI-compatible LLM API. Returns raw response string or None."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.llm_api_key}",
    }
    payload = {
        "model": config.llm_model,
        "messages": messages,
        "temperature": config.llm_temperature,
        "max_tokens": config.llm_max_tokens,
    }

    url = config.llm_base_url.rstrip("/") + "/chat/completions"
    data = json.dumps(payload).encode()

    last_error = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=config.llm_timeout) as resp:
                result = json.loads(resp.read().decode())
            return result["choices"][0]["message"]["content"]
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            last_error = str(e)
            if attempt == 0:
                time.sleep(1)
                continue
    return None


def count_tokens(messages: list[dict], config: Config) -> tuple[int, int]:
    """Heuristic token count. Returns (prompt_tokens, output_budget)."""
    prompt = ""
    for m in messages:
        prompt += m.get("content", "")
    prompt_tokens = len(prompt) // 4
    return prompt_tokens, config.llm_max_tokens

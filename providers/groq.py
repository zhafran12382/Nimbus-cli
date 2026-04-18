"""
NimbusCLI - Groq Provider
Handles communication with Groq API (OpenAI-compatible format).
"""

import json
import requests
from providers.base import BaseProvider, with_retry


class GroqProvider(BaseProvider):
    """Groq API provider using OpenAI-compatible format."""

    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model, base_url="https://api.groq.com/openai/v1")

    def _build_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @with_retry(max_retries=3, delay=2)
    def chat(self, messages: list[dict], tools: list[dict] = None, stream: bool = False, **kwargs) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        payload.update(kwargs)
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._build_headers(),
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        message = choice["message"]

        result = {
            "content": message.get("content"),
            "tool_calls": None,
            "usage": data.get("usage", {}),
        }

        if message.get("tool_calls"):
            result["tool_calls"] = []
            for tc in message["tool_calls"]:
                func = tc["function"]
                try:
                    args = json.loads(func["arguments"]) if isinstance(func["arguments"], str) else func["arguments"]
                except json.JSONDecodeError:
                    args = {"raw": func["arguments"]}
                result["tool_calls"].append({
                    "id": tc.get("id", ""),
                    "name": func["name"],
                    "arguments": args,
                })

        return result

    def stream_chat(self, messages: list[dict], tools: list[dict] = None):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._build_headers(),
            json=payload,
            stream=True,
            timeout=60,
        )
        resp.raise_for_status()

        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str.strip() == "[DONE]":
                break
            try:
                data = json.loads(data_str)
                delta = data["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

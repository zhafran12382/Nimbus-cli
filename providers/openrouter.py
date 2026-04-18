"""
NimbusCLI - OpenRouter Provider
Handles communication with OpenRouter API (OpenAI-compatible format).
"""

import json
import requests
from providers.base import BaseProvider, with_retry


class OpenRouterProvider(BaseProvider):
    """OpenRouter API provider using OpenAI-compatible format."""

    def __init__(self, api_key: str, model: str, routing: str = ""):
        super().__init__(api_key, model, base_url="https://openrouter.ai/api/v1")
        self.routing = routing

    @staticmethod
    def validate_routing(api_key: str, model: str, routing: str) -> tuple[bool, str]:
        """
        Validate routing by sending a strict test request with provider.only + allow_fallbacks=false.
        Returns (is_valid, error_message).
        """
        providers_list = [r.strip() for r in routing.split(",")]
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Say ok"}],
            "max_tokens": 5,
            "provider": {
                "only": providers_list,
                "allow_fallbacks": False,
            },
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/nimbus-cli",
            "X-Title": "NimbusCLI",
        }
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            if resp.status_code != 200:
                try:
                    err_body = resp.json()
                    err_msg = err_body.get("error", {}).get("message", resp.text[:300])
                except Exception:
                    err_msg = resp.text[:300]
                return False, err_msg
            return True, ""
        except Exception as e:
            return False, str(e)

    def _build_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/nimbus-cli",
            "X-Title": "NimbusCLI",
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

        if self.routing and self.routing.lower() != "auto":
            payload["provider"] = {"order": [r.strip() for r in self.routing.split(",")]}

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._build_headers(),
            json=payload,
            timeout=120,
        )
        if resp.status_code != 200:
            try:
                err_body = resp.json()
                err_msg = err_body.get("error", {}).get("message", resp.text[:300])
            except Exception:
                err_msg = resp.text[:300]
            raise RuntimeError(f"OpenRouter API {resp.status_code}: {err_msg}")
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
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        if self.routing and self.routing.lower() != "auto":
            payload["provider"] = {"order": [r.strip() for r in self.routing.split(",")]}

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._build_headers(),
            json=payload,
            stream=True,
            timeout=120,
        )
        if resp.status_code != 200:
            try:
                err_body = resp.json()
                err_msg = err_body.get("error", {}).get("message", resp.text[:300])
            except Exception:
                err_msg = resp.text[:300]
            raise RuntimeError(f"OpenRouter API {resp.status_code}: {err_msg}")

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

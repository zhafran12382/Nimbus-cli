"""
NimbusCLI - Anthropic Provider
Handles communication with Anthropic's Claude API (Messages API format).
"""

import json
import requests
from providers.base import BaseProvider, with_retry


class AnthropicProvider(BaseProvider):
    """Anthropic Claude API provider using Messages API format."""

    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model, base_url="https://api.anthropic.com/v1")

    def _build_headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

    def _convert_messages(self, messages: list[dict]) -> tuple[str, list[dict]]:
        """Separate system prompt and convert messages to Anthropic format."""
        system_text = ""
        converted = []

        for msg in messages:
            role = msg["role"]
            content = msg.get("content", "")

            if role == "system":
                system_text = content
            elif role == "user":
                converted.append({"role": "user", "content": content or ""})
            elif role == "assistant":
                if msg.get("tool_calls"):
                    # Convert tool calls to Anthropic tool_use blocks
                    tool_blocks = []
                    for tc in msg["tool_calls"]:
                        tool_blocks.append({
                            "type": "tool_use",
                            "id": tc.get("id", tc["name"]),
                            "name": tc["name"],
                            "input": tc["arguments"],
                        })
                    converted.append({"role": "assistant", "content": tool_blocks})
                else:
                    converted.append({"role": "assistant", "content": content or ""})
            elif role == "tool":
                converted.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("name", "tool"),
                        "content": content or "",
                    }],
                })

        return system_text, converted

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """Convert OpenAI tool format to Anthropic format."""
        if not tools:
            return []

        converted = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                converted.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                })
        return converted

    @with_retry(max_retries=3, delay=2)
    def chat(self, messages: list[dict], tools: list[dict] = None, stream: bool = False, **kwargs) -> dict:
        system_text, converted_messages = self._convert_messages(messages)

        payload = {
            "model": self.model,
            "messages": converted_messages,
            "max_tokens": 4096,
        }
        payload.update(kwargs)

        if system_text:
            payload["system"] = system_text

        anthropic_tools = self._convert_tools(tools)
        if anthropic_tools:
            payload["tools"] = anthropic_tools

        resp = requests.post(
            f"{self.base_url}/messages",
            headers=self._build_headers(),
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        result = {"content": None, "tool_calls": None, "usage": {}}

        text_parts = []
        tool_calls = []

        for block in data.get("content", []):
            if block["type"] == "text":
                text_parts.append(block["text"])
            elif block["type"] == "tool_use":
                tool_calls.append({
                    "id": block["id"],
                    "name": block["name"],
                    "arguments": block.get("input", {}),
                })

        if text_parts:
            result["content"] = "\n".join(text_parts)
        if tool_calls:
            result["tool_calls"] = tool_calls

        usage = data.get("usage", {})
        result["usage"] = {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
        }

        return result

    def stream_chat(self, messages: list[dict], tools: list[dict] = None):
        system_text, converted_messages = self._convert_messages(messages)

        payload = {
            "model": self.model,
            "messages": converted_messages,
            "max_tokens": 4096,
            "stream": True,
        }

        if system_text:
            payload["system"] = system_text

        resp = requests.post(
            f"{self.base_url}/messages",
            headers=self._build_headers(),
            json=payload,
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()

        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:]
            try:
                data = json.loads(data_str)
                event_type = data.get("type", "")
                if event_type == "content_block_delta":
                    delta = data.get("delta", {})
                    if delta.get("type") == "text_delta":
                        yield delta.get("text", "")
            except (json.JSONDecodeError, KeyError):
                continue

"""
NimbusCLI - Google Gemini Provider
Handles communication with Google's Gemini API (native format).
"""

import json
import requests
from providers.base import BaseProvider, with_retry


class GeminiProvider(BaseProvider):
    """Google Gemini API provider using native REST format."""

    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model, base_url="https://generativelanguage.googleapis.com/v1beta")

    def _convert_messages(self, messages: list[dict]) -> tuple[str, list[dict]]:
        """Convert OpenAI-style messages to Gemini format. Returns (system_instruction, contents)."""
        system_text = ""
        contents = []
        
        for msg in messages:
            role = msg["role"]
            content = msg.get("content", "")
            
            if role == "system":
                system_text = content
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content or ""}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content or ""}]})
            elif role == "tool":
                contents.append({
                    "role": "function",
                    "parts": [{"functionResponse": {"name": msg.get("name", "tool"), "response": {"result": content}}}],
                })
        
        return system_text, contents

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """Convert OpenAI tool format to Gemini function declarations."""
        if not tools:
            return []
        
        declarations = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                declarations.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {}),
                })
        
        return [{"functionDeclarations": declarations}] if declarations else []

    @with_retry(max_retries=3, delay=2)
    def chat(self, messages: list[dict], tools: list[dict] = None, stream: bool = False, **kwargs) -> dict:
        system_text, contents = self._convert_messages(messages)
        
        payload = {"contents": contents}
        payload.update(kwargs)
        
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        
        gemini_tools = self._convert_tools(tools)
        if gemini_tools:
            payload["tools"] = gemini_tools

        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        candidate = data["candidates"][0]
        parts = candidate["content"]["parts"]

        result = {"content": None, "tool_calls": None, "usage": {}}

        text_parts = []
        tool_calls = []

        for part in parts:
            if "text" in part:
                text_parts.append(part["text"])
            elif "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append({
                    "id": fc["name"],
                    "name": fc["name"],
                    "arguments": fc.get("args", {}),
                })

        if text_parts:
            result["content"] = "\n".join(text_parts)
        if tool_calls:
            result["tool_calls"] = tool_calls

        # Usage metadata
        usage_meta = data.get("usageMetadata", {})
        result["usage"] = {
            "prompt_tokens": usage_meta.get("promptTokenCount", 0),
            "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
        }

        return result

    def stream_chat(self, messages: list[dict], tools: list[dict] = None):
        system_text, contents = self._convert_messages(messages)
        
        payload = {"contents": contents}
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        
        gemini_tools = self._convert_tools(tools)
        if gemini_tools:
            payload["tools"] = gemini_tools

        url = f"{self.base_url}/models/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"

        resp = requests.post(url, json=payload, stream=True, timeout=120)
        resp.raise_for_status()

        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:]
            try:
                data = json.loads(data_str)
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                for part in parts:
                    if "text" in part:
                        yield part["text"]
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

"""
NimbusCLI - Session Manager
Manages conversation history and context.
"""

import json
import time
from pathlib import Path
from core.config import CONFIG_DIR


SESSIONS_DIR = CONFIG_DIR / "sessions"


class Session:
    """Manages a single chat session with message history."""

    def __init__(self, session_id: str = None):
        self.session_id = session_id or f"session_{int(time.time())}"
        self.messages: list[dict] = []
        self.created_at = time.time()
        self.provider = ""
        self.model = ""
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def add_usage(self, input_tok: int, output_tok: int):
        self.total_input_tokens += input_tok
        self.total_output_tokens += output_tok

    def add_message(self, role: str, content: str):
        """Add a message to the conversation history."""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })

    def add_tool_call(self, tool_name: str, arguments: dict, result: str):
        """Record a tool call and its result."""
        self.messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{"name": tool_name, "arguments": arguments}],
            "timestamp": time.time(),
        })
        self.messages.append({
            "role": "tool",
            "name": tool_name,
            "content": result,
            "timestamp": time.time(),
        })

    def get_messages_for_api(self) -> list[dict]:
        """Get messages formatted for OpenAI-compatible API calls."""
        api_messages = []
        for msg in self.messages:
            role = msg["role"]

            if role == "assistant" and msg.get("tool_calls"):
                # Format tool_calls in OpenAI spec: {id, type, function:{name, arguments}}
                formatted_tc = []
                for tc in msg["tool_calls"]:
                    formatted_tc.append({
                        "id": tc.get("id", tc.get("name", "call_0")),
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]) if isinstance(tc["arguments"], dict) else str(tc["arguments"]),
                        },
                    })
                entry = {
                    "role": "assistant",
                    "content": msg.get("content") or None,
                    "tool_calls": formatted_tc,
                }
                api_messages.append(entry)

            elif role == "tool":
                entry = {
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id", msg.get("name", "call_0")),
                    "content": msg.get("content") or "",
                }
                api_messages.append(entry)

            else:
                api_messages.append({
                    "role": role,
                    "content": msg.get("content") or "",
                })

        return api_messages

    def save(self):
        """Save session to disk."""
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        filepath = SESSIONS_DIR / f"{self.session_id}.json"
        data = {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "provider": self.provider,
            "model": self.model,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "messages": self.messages,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, session_id: str) -> "Session":
        """Load a session from disk."""
        filepath = SESSIONS_DIR / f"{session_id}.json"
        if not filepath.exists():
            raise FileNotFoundError(f"Session '{session_id}' not found.")
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        session = cls(data["session_id"])
        session.created_at = data["created_at"]
        session.provider = data.get("provider", "")
        session.model = data.get("model", "")
        session.total_input_tokens = data.get("total_input_tokens", 0)
        session.total_output_tokens = data.get("total_output_tokens", 0)
        session.messages = data["messages"]
        return session

    @classmethod
    def list_sessions(cls) -> list[dict]:
        """List all saved sessions."""
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        sessions = []
        for f in sorted(SESSIONS_DIR.glob("*.json"), reverse=True):
            try:
                with open(f, "r") as fh:
                    data = json.load(fh)
                sessions.append({
                    "id": data["session_id"],
                    "created_at": data["created_at"],
                    "provider": data.get("provider", ""),
                    "model": data.get("model", ""),
                    "message_count": len(data["messages"]),
                })
            except Exception:
                continue
        return sessions

    def compact_memory(self):
        """Compact the conversation history using an LLM summary."""
        # Instead of self-referencing an Agent directly here, we do it in main.py or agent.py
        # to avoid circular imports. This method just sets up the structure.
        pass

    def clear(self):
        """Clear conversation history."""
        self.messages = []


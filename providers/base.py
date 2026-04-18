"""
NimbusCLI - Base Provider
Abstract base class for all LLM providers.
"""

import time
import requests
from abc import ABC, abstractmethod
from functools import wraps

def with_retry(max_retries=3, delay=2, backoff=2):
    """Decorator to retry network requests gracefully."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            while True:
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.RequestException, ConnectionError, ConnectionResetError) as e:
                    retries += 1
                    if retries >= max_retries:
                        raise RuntimeError(f"Network error after {max_retries} retries: {str(e)}")
                    print(f"  [Network Issue] '{e}'. Retrying in {current_delay}s... ({retries}/{max_retries})")
                    time.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator


class BaseProvider(ABC):
    """Abstract base for LLM API providers."""

    def __init__(self, api_key: str, model: str, base_url: str = ""):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    @abstractmethod
    def chat(self, messages: list[dict], tools: list[dict] = None, stream: bool = False, **kwargs) -> dict:
        """
        Send a chat completion request.
        
        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool/function definitions.
            stream: Whether to stream the response.
        
        Returns:
            dict with keys:
                - 'content': str or None (the text response)
                - 'tool_calls': list of dicts or None
                    Each tool_call: {'name': str, 'arguments': dict}
                - 'usage': dict with 'prompt_tokens', 'completion_tokens'
        """
        pass

    @abstractmethod
    def stream_chat(self, messages: list[dict], tools: list[dict] = None):
        """
        Stream a chat completion response.
        
        Yields:
            str chunks of the response text.
        """
        pass

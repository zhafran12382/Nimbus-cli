"""
NimbusCLI - LLM Abstraction Layer
Factory to create the correct provider instance based on configuration.
"""

from core.config import get_api_key, get_provider_config, PROVIDERS
from providers.base import BaseProvider
from providers.openrouter import OpenRouterProvider
from providers.google_gemini import GeminiProvider
from providers.groq import GroqProvider
from providers.openai_provider import OpenAIProvider
from providers.anthropic import AnthropicProvider


PROVIDER_CLASSES = {
    "openrouter": OpenRouterProvider,
    "google": GeminiProvider,
    "groq": GroqProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}


def create_provider(provider_id: str, model: str, **kwargs) -> BaseProvider:
    """
    Create a provider instance.
    
    Args:
        provider_id: The provider key (e.g., 'openrouter', 'google', 'groq')
        model: The model ID to use.
    
    Returns:
        An initialized BaseProvider subclass instance.
    
    Raises:
        ValueError: If provider is unknown or API key is missing.
    """
    if provider_id not in PROVIDER_CLASSES:
        available = ", ".join(PROVIDER_CLASSES.keys())
        raise ValueError(f"Unknown provider '{provider_id}'. Available: {available}")

    api_key = get_api_key(provider_id)
    if not api_key:
        config = get_provider_config(provider_id)
        env_var = config["api_key_env"] if config else "UNKNOWN"
        raise ValueError(
            f"API key for '{provider_id}' not found. "
            f"Set {env_var} in your environment or run: python main.py setup"
        )

    return PROVIDER_CLASSES[provider_id](api_key=api_key, model=model, **kwargs)


def list_providers() -> list[dict]:
    """List all available providers and their models."""
    result = []
    for pid, pconfig in PROVIDERS.items():
        has_key = bool(get_api_key(pid))
        result.append({
            "id": pid,
            "name": pconfig["name"],
            "has_key": has_key,
            "models": pconfig["models"],
        })
    return result

"""
NimbusCLI - Configuration Manager
Handles loading/saving config, API keys, and user preferences.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Default config directory
CONFIG_DIR = Path.home() / ".nimbus"
CONFIG_FILE = CONFIG_DIR / "config.json"
ENV_FILE = CONFIG_DIR / ".env"

# Provider definitions with model lists
PROVIDERS = {
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "format": "openai",
        "models": [
            {"id": "google/gemma-4-31b-it:free", "name": "Gemma 4 31B", "free": True},
            {"id": "meta-llama/llama-3.3-70b-instruct:free", "name": "Llama 3.3 70B", "free": True},
            {"id": "qwen/qwen3-coder:free", "name": "Qwen 3 Coder", "free": True},
            {"id": "minimax/minimax-m2.7", "name": "MiniMax M2.7", "free": False},
            {"id": "xiaomi/mimo-v2-pro", "name": "Xiaomi MiMo V2 Pro", "free": False},
            {"id": "deepseek/deepseek-v3.2", "name": "DeepSeek V3.2", "free": False},
            {"id": "openai/gpt-oss-120b", "name": "GPT-OSS 120B", "free": False},
            {"id": "meta-llama/llama-3.3-70b-instruct", "name": "Llama 3.3 70B (Paid)", "free": False},
            {"id": "anthropic/claude-haiku-4-5", "name": "Claude Haiku 4.5", "free": False},
            {"id": "openai/gpt-5.4-mini", "name": "GPT-5.4 Mini", "free": False},
            {"id": "google/gemini-2.5-flash", "name": "Gemini 2.5 Flash", "free": False},
            {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "free": False},
            {"id": "openai/gpt-5.4", "name": "GPT-5.4", "free": False},
        ],
    },
    "google": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key_env": "GOOGLE_GEMINI_API_KEY",
        "format": "gemini",
        "models": [
            {"id": "gemini-3.1-flash", "name": "Gemini 3.1 Flash"},
            {"id": "gemini-3.1-flash-8b", "name": "Gemini 3.1 Flash 8B"},
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"},
            {"id": "gemini-2.5-flash-lite", "name": "Gemini 2.5 Flash Lite"},
            {"id": "gemini-2.5-flash-8b", "name": "Gemini 2.5 Flash 8B"},
        ],
    },
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "format": "openai",
        "models": [
            {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B"},
            {"id": "meta-llama/llama-4-scout-17b-16e-instruct", "name": "Llama 4 Scout 17B"},
            {"id": "qwen3-32b", "name": "Qwen 3 32B"},
            {"id": "gemma-4-27b-it", "name": "Gemma 4 27B"},
            {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B"},
        ],
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "format": "openai",
        "models": [
            {"id": "gpt-5.4-mini", "name": "GPT-5.4 Mini"},
            {"id": "gpt-5.4-nano", "name": "GPT-5.4 Nano"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini"},
            {"id": "o4-mini", "name": "o4 Mini"},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo"},
        ],
    },
    "anthropic": {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "api_key_env": "ANTHROPIC_API_KEY",
        "format": "anthropic",
        "models": [
            {"id": "claude-haiku-4-5", "name": "Claude Haiku 4.5"},
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku"},
            {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku"},
            {"id": "claude-haiku-latest", "name": "Claude Haiku Latest"},
            {"id": "claude-haiku-fast", "name": "Claude Haiku Fast"},
        ],
    },
}


def ensure_config_dir():
    """Create config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Load configuration from file."""
    ensure_config_dir()
    
    # Load .env if exists
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
    
    # Also load from project-local .env
    local_env = Path.cwd() / ".env"
    if local_env.exists():
        load_dotenv(local_env)
    
    # Load config.json
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    
    return {
        "provider": "openrouter",
        "model": "google/gemma-4-31b-it:free",
        "search_engine": "duckduckgo",
    }


def save_config(config: dict):
    """Save configuration to file."""
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def save_api_key(key_name: str, key_value: str):
    """Save an API key to the .env file."""
    ensure_config_dir()
    
    env_data = {}
    if ENV_FILE.exists():
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env_data[k.strip()] = v.strip()
    
    env_data[key_name] = key_value
    
    with open(ENV_FILE, "w") as f:
        for k, v in env_data.items():
            f.write(f"{k}={v}\n")
    
    # Reload into environment
    os.environ[key_name] = key_value


def get_api_key(provider_id: str) -> str | None:
    """Get the API key for a provider."""
    provider = PROVIDERS.get(provider_id)
    if not provider:
        return None
    return os.environ.get(provider["api_key_env"], "")


def get_provider_config(provider_id: str) -> dict | None:
    """Get full provider configuration."""
    return PROVIDERS.get(provider_id)


def get_tavily_key() -> str | None:
    """Get the Tavily API key."""
    return os.environ.get("TAVILY_API_KEY", "")

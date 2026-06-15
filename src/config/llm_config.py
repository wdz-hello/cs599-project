"""LLM client configuration — DeepSeek API (OpenAI-compatible)."""

from openai import OpenAI
from src.config.settings import settings


def create_llm_client() -> OpenAI:
    """Create OpenAI-compatible client for DeepSeek API."""
    settings.validate()
    return OpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
    )


def get_model_name() -> str:
    return settings.DEEPSEEK_MODEL


def get_default_kwargs() -> dict:
    return {
        "model": settings.DEEPSEEK_MODEL,
        "temperature": settings.TEMPERATURE,
        "max_tokens": settings.MAX_TOKENS,
    }

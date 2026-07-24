"""Unified model configuration. To switch providers (OpenAI / z.ai GLM / any other OpenAI-compatible endpoint),
just change three values in .env: OPENAI_API_KEY, OPENAI_BASE_URL, GROUNDING_MODEL.
"""
import os
from langchain_openai import ChatOpenAI


def get_model_name() -> str:
    return os.environ.get("GROUNDING_MODEL", "gpt-4o")


def struct_method() -> str:
    """Which structured-output method to use; it varies by backend:
    - local Ollama vision models → json_schema (they don't support tools)
    - z.ai GLM / OpenAI → function_calling (native tool use, most reliable)
    Change STRUCT_METHOD in .env."""
    return os.environ.get("STRUCT_METHOD", "json_schema")


def make_chat(temperature: float = 0.5, model: str = None,
              disable_thinking: bool = None) -> ChatOpenAI:
    """Build a chat model from the .env config.
    - OPENAI_API_KEY: your key (OpenAI's or z.ai's, either goes here)
    - OPENAI_BASE_URL: leave empty = official OpenAI; z.ai's address = GLM
    - GROUNDING_MODEL: model name (gpt-4o / glm-4.6 …)
    - model: one-off override of the model name (e.g. vision model for bank-building, big text model for conversation)
    - disable_thinking: whether to switch off "deep thinking" mode (GLM-4.6 has it on by default,
      taking 20-35s for a single sentence; off it's ~2s). None = follow DISABLE_THINKING in .env;
      True/False = explicit choice.
      The vision bank-building step passes False, so a vision model that doesn't recognize this parameter won't error.
    """
    kwargs = {"model": model or get_model_name(), "temperature": temperature}
    base = os.environ.get("OPENAI_BASE_URL", "").strip()
    if base:
        kwargs["base_url"] = base
    if disable_thinking is None:
        disable_thinking = os.environ.get("DISABLE_THINKING", "").strip() in ("1", "true", "True", "yes")
    if disable_thinking:
        # z.ai GLM's thinking-off switch rides in via extra_body into the request body (the OpenAI client rejects it as a top-level param)
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    # api_key is picked up automatically from the OPENAI_API_KEY env var
    return ChatOpenAI(**kwargs)

"""get_llm(task): the only place that builds chat models. Shared by agent/ and
ingestion/ (vision escalation), so it lives at the app root.

Env (OpenAI-compatible; OpenRouter by default, Google AI Studio for dev):
  LLM_BASE_URL, LLM_API_KEY, AGENT_MODEL (task "agent"), EXTRACT_LLM_MODEL
  (task "extract"). Optional per task: AGENT_TEMPERATURE (default 0).
  Output cap per call (spend control): AGENT_MAX_TOKENS (default 4096: reasoning models spend part of
  the cap thinking, and 1024 left 17 of 71 eval turns empty),
  EXTRACT_MAX_TOKENS (default 4096); positive integers, else LLMConfigError.
  Retries are limited to 1 so a failing call cannot silently triple the cost.
Missing key or model -> LLMConfigError with the variable name; never a
network call at construction time beyond what ChatOpenAI does lazily.
"""

from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

Task = Literal["agent", "extract"]
MODEL_ENV: dict[str, str] = {"agent": "AGENT_MODEL", "extract": "EXTRACT_LLM_MODEL"}
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
AGENT_TEMPERATURE_ENV = "AGENT_TEMPERATURE"
MAX_TOKENS: dict[str, tuple[str, int]] = {
    "agent": ("AGENT_MAX_TOKENS", 4096),
    "extract": ("EXTRACT_MAX_TOKENS", 4096),
}


class LLMConfigError(RuntimeError):
    """A required environment variable is missing; message names it."""


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise LLMConfigError(f"Missing required environment variable {name}")
    return value


def _max_tokens(task: str) -> int:
    name, default = MAX_TOKENS[task]
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value <= 0:
        raise LLMConfigError(f"{name} must be a positive integer, got {raw!r}")
    return value


def get_llm(task: Task = "agent") -> BaseChatModel:
    if task not in MODEL_ENV:
        raise LLMConfigError(f"Unknown LLM task {task!r}; expected one of {sorted(MODEL_ENV)}")
    load_dotenv(override=False)
    api_key = _require("LLM_API_KEY")
    model = _require(MODEL_ENV[task])
    base_url = os.environ.get("LLM_BASE_URL", "").strip() or DEFAULT_BASE_URL
    temperature = 0.0
    if task == "agent":
        raw = os.environ.get(AGENT_TEMPERATURE_ENV, "").strip()
        if raw:
            try:
                temperature = float(raw)
            except ValueError as exc:
                raise LLMConfigError(
                    f"{AGENT_TEMPERATURE_ENV} must be a number, got {raw!r}"
                ) from exc
    return ChatOpenAI(
        base_url=base_url,
        api_key=SecretStr(api_key),
        model=model,
        temperature=temperature,
        timeout=60,
        max_retries=1,
        max_completion_tokens=_max_tokens(task),
    )

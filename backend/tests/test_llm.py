"""get_llm builds ChatOpenAI from env only; no network is touched."""

import pytest
from langchain_openai import ChatOpenAI

import app.llm as llm_mod
from app.llm import DEFAULT_BASE_URL, LLMConfigError, get_llm

VARS = ("LLM_BASE_URL", "LLM_API_KEY", "AGENT_MODEL", "EXTRACT_LLM_MODEL", "AGENT_TEMPERATURE")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    # Never read a real .env during tests.
    monkeypatch.setattr(llm_mod, "load_dotenv", lambda *a, **k: False)
    for v in VARS:
        monkeypatch.delenv(v, raising=False)


def test_agent_and_extract_models(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_MODEL", "agent/model")
    monkeypatch.setenv("EXTRACT_LLM_MODEL", "extract/model")
    a, e = get_llm("agent"), get_llm("extract")
    assert isinstance(a, ChatOpenAI) and isinstance(e, ChatOpenAI)
    assert a.model_name == "agent/model"
    assert e.model_name == "extract/model"
    assert a.openai_api_base == DEFAULT_BASE_URL
    assert a.temperature == 0
    assert a.max_retries == 2


def test_custom_base_url_and_temperature(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("AGENT_MODEL", "m")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:9999/v1")
    monkeypatch.setenv("AGENT_TEMPERATURE", "0.3")
    a = get_llm("agent")
    assert isinstance(a, ChatOpenAI)
    assert a.openai_api_base == "http://localhost:9999/v1"
    assert a.temperature == 0.3


def test_missing_key(monkeypatch):
    monkeypatch.setenv("AGENT_MODEL", "m")
    with pytest.raises(LLMConfigError, match="LLM_API_KEY"):
        get_llm("agent")


@pytest.mark.parametrize(
    ("task", "var"), [("agent", "AGENT_MODEL"), ("extract", "EXTRACT_LLM_MODEL")]
)
def test_missing_model(monkeypatch, task, var):
    monkeypatch.setenv("LLM_API_KEY", "k")
    with pytest.raises(LLMConfigError, match=var):
        get_llm(task)  # type: ignore[arg-type]


def test_bad_temperature(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("AGENT_MODEL", "m")
    monkeypatch.setenv("AGENT_TEMPERATURE", "hot")
    with pytest.raises(LLMConfigError, match="AGENT_TEMPERATURE"):
        get_llm("agent")

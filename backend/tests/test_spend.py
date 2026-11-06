"""Spend control tests: injected readers/HTTP, tmp log, no network."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import app.spend as sp
from app.spend import BudgetExceeded, KeyStatus, SpendError, budgeted, estimate_usd

SECRET = "sk-test-SECRET"


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sp, "load_dotenv", lambda *a, **k: False)
    monkeypatch.setenv("LLM_API_KEY", SECRET)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)


class Reader:
    def __init__(self, *usages: float | Exception, remaining: float | None = None):
        self.usages = list(usages)
        self.remaining = remaining

    def __call__(self) -> KeyStatus:
        u = self.usages.pop(0) if len(self.usages) > 1 else self.usages[0]
        if isinstance(u, Exception):
            raise u
        return KeyStatus(usage_usd=u, limit_remaining_usd=self.remaining)


def test_read_key_status_parses_and_uses_url_and_header() -> None:
    seen: dict[str, Any] = {}

    def get(url: str, headers: dict[str, str]) -> dict[str, Any]:
        seen.update(url=url, headers=headers)
        return {"data": {"usage": 1.5, "limit_remaining": 8.5, "expires_at": None}}

    st = sp.read_key_status(http_get=get)
    assert (st.usage_usd, st.limit_remaining_usd) == (1.5, 8.5)
    assert seen["url"] == "https://openrouter.ai/api/v1/key"
    assert seen["headers"]["Authorization"] == f"Bearer {SECRET}"


def test_read_key_status_errors_hide_key(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(url: str, headers: dict[str, str]) -> dict[str, Any]:
        raise RuntimeError(f"bad {headers['Authorization']}")

    with pytest.raises(SpendError) as e1:
        sp.read_key_status(http_get=boom)
    with pytest.raises(SpendError) as e2:
        sp.read_key_status(http_get=lambda u, h: {"nope": 1})
    monkeypatch.delenv("LLM_API_KEY")
    with pytest.raises(SpendError, match="LLM_API_KEY") as e3:
        sp.read_key_status()
    for e in (e1, e2, e3):
        assert SECRET not in str(e.value)


def test_fail_closed(tmp_path: Path) -> None:
    ran = False
    reader = Reader(SpendError("no"))
    with pytest.raises(SpendError), budgeted("x", 1.0, log_path=tmp_path / "l.md", reader=reader):
        ran = True
    assert not ran


def test_refuses_when_remaining_below_cap(tmp_path: Path) -> None:
    reader = Reader(5.0, remaining=0.5)
    with (
        pytest.raises(SpendError, match="left on the key"),
        budgeted("x", 1.0, log_path=tmp_path / "l.md", reader=reader),
    ):
        pass


def test_logs_success(tmp_path: Path) -> None:
    log = tmp_path / "sub" / "l.md"
    with budgeted("eval", 1.0, model="m/x", log_path=log, reader=Reader(5.0, 5.25)) as b:
        b.calls = 3
    text = log.read_text()
    assert text.startswith("# OpenRouter spend log")
    assert "| eval | m/x | 3 | 0.250000 | 1.00 | ok |" in text


def test_logs_on_exception_and_does_not_mask(tmp_path: Path) -> None:
    log = tmp_path / "l.md"
    reader = Reader(1.0, SpendError("down"))
    with pytest.raises(ValueError, match="boom"), budgeted("s", 1.0, log_path=log, reader=reader):
        raise ValueError("boom")
    assert "| unknown | 1.00 | failed |" in log.read_text()


def test_check_raises_and_logs_aborted(tmp_path: Path) -> None:
    log = tmp_path / "l.md"
    with (
        pytest.raises(BudgetExceeded),
        budgeted("s", 0.5, log_path=log, reader=Reader(1.0, 2.0)) as b,
    ):
        b.check()
    assert "aborted" in log.read_text()
    assert issubclass(BudgetExceeded, SpendError)


def test_check_within_cap_returns_spend(tmp_path: Path) -> None:
    with budgeted("s", 0.5, log_path=tmp_path / "l.md", reader=Reader(1.0, 1.2, 1.2)) as b:
        assert b.check() == pytest.approx(0.2)


def test_secret_never_in_log(tmp_path: Path) -> None:
    log = tmp_path / "l.md"
    with budgeted("s", 1.0, log_path=log, reader=Reader(1.0, 1.1)):
        pass
    assert SECRET not in log.read_text()


def test_estimate_usd() -> None:
    assert estimate_usd(1000, 500, 1e-6, 2e-6) == pytest.approx(0.002)


def test_polls_the_whole_window_for_late_costs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OpenRouter books costs late and in parts: keep polling for settle_s, log the last read."""
    from app import spend

    slept: list[float] = []
    monkeypatch.setattr(spend.time, "sleep", slept.append)
    monkeypatch.setattr(spend, "POLL_S", 10.0)
    values = iter([5.0, 5.1, 5.1, 5.4, 5.4])  # before, first after-read, then three polls
    reader = lambda: spend.KeyStatus(
        usage_usd=next(values), limit_remaining_usd=9.0, expires_at=None
    )
    log = tmp_path / "l.md"
    with budgeted("v", 1.0, log_path=log, reader=reader, settle_s=30.0) as b:
        b.calls = 1
    assert slept == [10.0, 10.0, 10.0]
    assert "| 0.400000 |" in log.read_text()


def test_no_wait_without_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import spend

    slept: list[float] = []
    monkeypatch.setattr(spend.time, "sleep", slept.append)
    reader = lambda: spend.KeyStatus(usage_usd=5.0, limit_remaining_usd=9.0, expires_at=None)
    with budgeted("v", 1.0, log_path=tmp_path / "l.md", reader=reader, settle_s=30.0):
        pass
    assert slept == []

"""Spend control for paid LLM steps (OpenRouter budget is tiny and hard-capped).

Contract:
- read_key_status(*, http_get=None) -> KeyStatus: GET {LLM_BASE_URL}/key with the
  env LLM_API_KEY. http_get(url, headers) -> dict is injectable. Any problem
  raises SpendError; messages never contain the key.
- budgeted(step, max_usd, *, model="", log_path=SPEND_LOG, reader=read_key_status, settle_s=SETTLE_S)
  (all resolved at call time). If calls were made but usage has not moved, it waits settle_s
  once and re-reads (OpenRouter reports usage with a delay):
  context manager. Fails closed: if usage cannot be read, or the key's remaining
  limit is below max_usd, the step does not run (SpendError). Yields a Budget
  with a settable `.calls` and `.check()` (raises BudgetExceeded when the spend
  so far is above max_usd). On exit, even on error, appends one row to the
  markdown log; if the final read fails the spend is logged as "unknown" and
  the original exception is never masked.
- estimate_usd(prompt_tokens, completion_tokens, price_prompt, price_completion)
  -> float: pure arithmetic, per-token prices.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
SPEND_LOG = Path(__file__).resolve().parents[2] / "docs" / "spend-log.md"
_HEADER = (
    "# OpenRouter spend log\n\n"
    "Rows are appended automatically by `backend/app/spend.py` after every paid step.\n\n"
    "| date (UTC) | step | model | calls | spent USD | cap USD | outcome |\n"
    "|---|---|---|---|---|---|---|\n"
)

HttpGet = Callable[[str, dict[str, str]], dict[str, Any]]


class SpendError(RuntimeError):
    """Spend could not be verified or the budget is too small; the step must not run."""


class BudgetExceeded(SpendError):
    """The step already spent more than its cap."""


class KeyStatus(BaseModel):
    usage_usd: float
    limit_remaining_usd: float | None = None
    expires_at: str | None = None


def _urllib_get(url: str, headers: dict[str, str]) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise TypeError("response is not a JSON object")
    return data


def read_key_status(*, http_get: HttpGet | None = None) -> KeyStatus:
    load_dotenv(override=False)
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not key:
        raise SpendError("Cannot verify spend: LLM_API_KEY is not set")
    base = os.environ.get("LLM_BASE_URL", "").strip() or DEFAULT_BASE_URL
    get = http_get or _urllib_get
    try:
        payload = get(f"{base.rstrip('/')}/key", {"Authorization": f"Bearer {key}"})
        data = payload["data"]
        remaining = data.get("limit_remaining")
        return KeyStatus(
            usage_usd=float(data["usage"]),
            limit_remaining_usd=None if remaining is None else float(remaining),
            expires_at=data.get("expires_at"),
        )
    except Exception as exc:  # noqa: BLE001 - never leak details that could hold the key
        raise SpendError(
            f"Cannot verify spend: key status call failed ({type(exc).__name__})"
        ) from None


def estimate_usd(
    prompt_tokens: int,
    completion_tokens: int,
    price_prompt_per_token: float,
    price_completion_per_token: float,
) -> float:
    return prompt_tokens * price_prompt_per_token + completion_tokens * price_completion_per_token


class Budget:
    def __init__(self, max_usd: float, start_usage: float, reader: Callable[[], KeyStatus]):
        self.max_usd = max_usd
        self.start_usage = start_usage
        self.calls = 0
        self._reader = reader

    def check(self) -> float:
        """Re-read usage; raise BudgetExceeded when this step spent more than its cap."""
        spent = self._reader().usage_usd - self.start_usage
        if spent > self.max_usd:
            raise BudgetExceeded(f"spent ${spent:.6f}, above the ${self.max_usd:.2f} cap")
        return spent


def _append_row(log_path: Path, row: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not log_path.exists():
        log_path.write_text(_HEADER)
    with log_path.open("a") as fh:
        fh.write(row + "\n")


SETTLE_S = 20.0  # OpenRouter reports usage a few seconds after a call


def _settled_usage(
    reader: Callable[[], KeyStatus], start: float, calls: int, settle_s: float
) -> float:
    """Final usage. If calls were made but usage has not moved yet, wait once and re-read."""
    usage = reader().usage_usd
    if calls and usage <= start and settle_s > 0:
        time.sleep(settle_s)
        usage = reader().usage_usd
    return usage


@contextmanager
def budgeted(
    step: str,
    max_usd: float,
    *,
    model: str = "",
    log_path: Path | None = None,
    reader: Callable[[], KeyStatus] | None = None,
    settle_s: float | None = None,
) -> Iterator[Budget]:
    log_path = log_path or SPEND_LOG
    settle = SETTLE_S if settle_s is None else settle_s
    reader = reader or read_key_status  # resolved at call time (patchable)
    before = reader()  # fail closed: SpendError propagates, step never runs
    remaining = before.limit_remaining_usd
    if remaining is not None and remaining < max_usd:
        raise SpendError(
            f"Refusing {step}: ${remaining:.2f} left on the key, cap is ${max_usd:.2f}"
        )
    budget = Budget(max_usd, before.usage_usd, reader)
    outcome = "ok"
    try:
        yield budget
    except BudgetExceeded:
        outcome = "aborted"
        raise
    except BaseException:
        outcome = "failed"
        raise
    finally:
        try:
            spent = f"{_settled_usage(reader, before.usage_usd, budget.calls, settle) - before.usage_usd:.6f}"
        except Exception:  # noqa: BLE001 - logging must not mask the original error
            spent = "unknown"
        row = (
            f"| {datetime.now(UTC).isoformat(timespec='seconds')} | {step} | {model} | "
            f"{budget.calls} | {spent} | {max_usd:.2f} | {outcome} |"
        )
        try:
            _append_row(log_path, row)
        except OSError:
            pass

"""ingest.py against a real Postgres (regressions found by the Gate 2 demo).

The unit tests in test_ingest.py fake the connection, so they could not see
that `--reset` on a brand-new database failed (DELETE before the schema
existed). These run main() end to end on the test database.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import psycopg
import pytest

import ingest
from app.domain.models import Catalog
from app.ingestion.pipeline import ExtractionReport
from tests.conftest import DEFAULT_TEST_URL

BACKEND = Path(__file__).resolve().parents[1]
REAL_JSON = BACKEND / "data" / "processed" / "actuators.json"
pytestmark = pytest.mark.integration


@pytest.fixture
def db_url(pg: psycopg.Connection) -> str:
    """Test DB URL, with every table dropped: what a first run on a new machine sees."""
    pg.execute("DROP TABLE IF EXISTS messages, sessions, actuators, catalog_tables CASCADE")
    return os.environ.get("TEST_DATABASE_URL") or DEFAULT_TEST_URL  # info.dsn hides the password


@pytest.fixture
def json_copy(tmp_path: Path) -> Path:
    dst = tmp_path / "actuators.json"
    shutil.copy(REAL_JSON, dst)
    return dst


def _count(url: str) -> int:
    with psycopg.connect(url) as c:
        row = c.execute("SELECT count(*) FROM actuators").fetchone()
        assert row is not None
        return int(row[0])


def test_reset_on_brand_new_database(db_url: str, json_copy: Path, capsys) -> None:
    code = ingest.main(["--reset", "--no-escalation", "--json", str(json_copy),
                        "--database-url", db_url])
    assert code == 0, capsys.readouterr().err
    assert "rows=68" in capsys.readouterr().out
    assert _count(db_url) == 68


def test_default_then_reset_is_idempotent(db_url: str, json_copy: Path) -> None:
    args = ["--no-escalation", "--json", str(json_copy), "--database-url", db_url]
    assert ingest.main(args) == 0
    assert ingest.main(["--reset", *args]) == 0
    assert _count(db_url) == 68


def test_from_pdf_replaces_stale_rows(
    db_url: str, json_copy: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = ["--no-escalation", "--json", str(json_copy), "--database-url", db_url]
    assert ingest.main(args) == 0
    catalog = Catalog.model_validate_json(REAL_JSON.read_text())
    smaller = catalog.model_copy(update={"rows": catalog.rows[1:]})  # one PN dropped
    monkeypatch.setattr(ingest, "extract_with_report",
                        lambda pdf, esc: (smaller, ExtractionReport()))
    assert ingest.main(["--from-pdf", "--force", *args]) == 0
    assert _count(db_url) == 67  # the dropped PN does not linger


def test_database_down_is_a_clean_error(json_copy: Path, capsys) -> None:
    code = ingest.main(["--no-escalation", "--json", str(json_copy),
                        "--database-url", "postgresql://series76:series76@localhost:1/none"])
    assert code == 1
    assert "docker compose up -d db" in capsys.readouterr().err


def test_missing_llm_config_is_a_clean_error(
    json_copy: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from app.llm import LLMConfigError

    def boom(pdf, esc):
        raise LLMConfigError("Missing required environment variable LLM_API_KEY")

    monkeypatch.setattr(ingest, "extract_with_report", boom)
    code = ingest.main(["--from-pdf", "--force", "--json", str(json_copy)])
    assert code == 1
    assert "LLM_API_KEY" in capsys.readouterr().err

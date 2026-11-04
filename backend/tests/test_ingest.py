"""CLI tests for backend/ingest.py. No database, no LLM: every dependency is faked."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

import ingest
from app.bootstrap import DataStatus
from app.domain.models import Catalog
from app.ingestion.pipeline import ExtractionError, ExtractionReport

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def no_real_escalator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never build the real vision escalator (it is a stub until escalate.py lands)."""
    monkeypatch.setattr(ingest, "make_vision_escalator", lambda: "VISION")


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Records the order of side-effecting calls. Each fake is installed on `ingest`."""
    order: list[str] = []
    conn = MagicMock(name="conn")

    def fake_connect(url: str | None = None) -> Any:
        order.append("connect")
        return conn

    def fake_delete_all(_conn: Any) -> None:
        order.append("delete_all")

    def fake_ensure(_conn: Any, **kwargs: Any) -> DataStatus:
        order.append("ensure_data")
        return DataStatus(source="json", rows=68)

    monkeypatch.setattr(ingest, "connect", fake_connect)
    monkeypatch.setattr(ingest, "delete_all", fake_delete_all)
    monkeypatch.setattr(ingest, "ensure_data", fake_ensure)
    return order


def test_default_runs_ensure_data_and_prints_summary(
    calls: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert ingest.main([]) == 0
    assert calls == ["connect", "ensure_data"]
    assert "source=json rows=68" in capsys.readouterr().out


def test_reset_deletes_before_ensure_data(calls: list[str]) -> None:
    assert ingest.main(["--reset"]) == 0
    assert calls == ["connect", "delete_all", "ensure_data"]


def test_default_passes_vision_escalator_and_paths(
    monkeypatch: pytest.MonkeyPatch, calls: list[str], tmp_path: Path
) -> None:
    seen: dict[str, Any] = {}

    def fake_ensure(_conn: Any, **kwargs: Any) -> DataStatus:
        seen.update(kwargs)
        return DataStatus(source="db", rows=68)

    monkeypatch.setattr(ingest, "ensure_data", fake_ensure)
    json_path = tmp_path / "a.json"
    pdf_path = tmp_path / "a.pdf"
    assert ingest.main(["--json", str(json_path), "--pdf", str(pdf_path)]) == 0
    assert seen["escalator"] == "VISION"
    assert seen["json_path"] == json_path
    assert seen["pdf_path"] == pdf_path


def test_from_pdf_without_force_refuses_when_json_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    json_path = tmp_path / "actuators.json"
    json_path.write_text("{}")
    extract = MagicMock(name="extract_with_report")
    monkeypatch.setattr(ingest, "extract_with_report", extract)

    code = ingest.main(["--from-pdf", "--json", str(json_path)])

    assert code == 2
    extract.assert_not_called()
    assert "actuators.json exists; pass --force to overwrite" in capsys.readouterr().err


def test_from_pdf_with_force_extracts_and_writes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    json_path = tmp_path / "actuators.json"
    json_path.write_text("{}")
    pdf_path = tmp_path / "series.pdf"
    catalog = Catalog(tables=[], rows=[])
    extract = MagicMock(return_value=(catalog, ExtractionReport()))
    write = MagicMock(name="write_catalog")
    upsert = MagicMock(name="upsert_catalog", return_value=0)
    monkeypatch.setattr(ingest, "extract_with_report", extract)
    monkeypatch.setattr(ingest, "write_catalog", write)
    monkeypatch.setattr(ingest, "upsert_catalog", upsert)
    monkeypatch.setattr(ingest, "connect", lambda url=None: MagicMock(name="conn"))

    code = ingest.main(["--from-pdf", "--force", "--json", str(json_path), "--pdf", str(pdf_path)])

    assert code == 0
    extract.assert_called_once_with(pdf_path, "VISION")
    write.assert_called_once_with(catalog, json_path, force=True)
    upsert.assert_called_once()
    assert "source=pdf rows=0" in capsys.readouterr().out


def test_no_escalation_passes_none(
    monkeypatch: pytest.MonkeyPatch, calls: list[str], tmp_path: Path
) -> None:
    seen: dict[str, Any] = {}

    def fake_ensure(_conn: Any, **kwargs: Any) -> DataStatus:
        seen.update(kwargs)
        return DataStatus(source="json", rows=68)

    monkeypatch.setattr(ingest, "ensure_data", fake_ensure)
    make = MagicMock(name="make_vision_escalator")
    monkeypatch.setattr(ingest, "make_vision_escalator", make)

    assert ingest.main(["--no-escalation"]) == 0
    assert seen["escalator"] is None
    make.assert_not_called()


def test_no_escalation_from_pdf_passes_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    extract = MagicMock(return_value=(Catalog(tables=[], rows=[]), ExtractionReport()))
    monkeypatch.setattr(ingest, "extract_with_report", extract)
    monkeypatch.setattr(ingest, "write_catalog", MagicMock())
    monkeypatch.setattr(ingest, "upsert_catalog", MagicMock(return_value=0))
    monkeypatch.setattr(ingest, "connect", lambda url=None: MagicMock())

    code = ingest.main(
        ["--from-pdf", "--no-escalation", "--json", str(tmp_path / "x.json"), "--pdf", "p.pdf"]
    )

    assert code == 0
    assert extract.call_args.args[1] is None


def test_extraction_error_exits_1_with_message(
    monkeypatch: pytest.MonkeyPatch, calls: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(_conn: Any, **kwargs: Any) -> DataStatus:
        raise ExtractionError("table 3 row 764A00: FLA unreadable")

    monkeypatch.setattr(ingest, "ensure_data", boom)

    assert ingest.main([]) == 1
    err = capsys.readouterr().err
    assert "table 3 row 764A00: FLA unreadable" in err


def test_help_exits_0() -> None:
    result = subprocess.run(
        ["uv", "run", "python", "ingest.py", "--help"],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        check=False,
        env={k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"},
    )
    assert result.returncode == 0, result.stderr
    assert "--reset" in result.stdout

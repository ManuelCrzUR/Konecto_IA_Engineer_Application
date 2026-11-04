"""Read/write data/processed/actuators.json (format: domain.models.Catalog).

Never overwrites silently (CLAUDE.md §9): write_catalog refuses an existing
file unless force=True. Writes are atomic (temp file + rename) so a crash
never leaves a half-written JSON.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.domain.models import Catalog


class CatalogFileError(RuntimeError):
    """The file exists but is not valid JSON or does not validate as Catalog."""


def read_catalog(path: Path) -> Catalog | None:
    """None if the file does not exist; CatalogFileError if corrupt or invalid."""
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogFileError(f"{path}: not valid JSON: {exc}") from exc
    try:
        return Catalog.model_validate(data)
    except ValidationError as exc:
        raise CatalogFileError(f"{path}: does not match Catalog schema: {exc}") from exc


def _catalog_to_json_data(catalog: Catalog) -> dict[str, Any]:
    """Plain dict in the on-disk shape. `has_data` is computed, so it is not stored."""
    return catalog.model_dump(mode="json", exclude={"rows": {"__all__": {"has_data"}}})


def write_catalog(catalog: Catalog, path: Path, force: bool = False) -> None:
    """FileExistsError if path exists and not force. Pretty JSON (indent=2),
    same shape build_seed.py produces: {"tables": [...], "rows": [...]}."""
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists; pass force=True to overwrite")

    data = _catalog_to_json_data(catalog)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Temp file in the same directory so os.replace is an atomic rename on one filesystem.
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise

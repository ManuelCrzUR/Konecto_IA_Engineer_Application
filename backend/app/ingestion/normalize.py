"""Raw cell text -> typed values. Applies the extraction rules from CLAUDE.md §4.

Rules: values exactly as printed (no conversion, no arithmetic, no "fixes");
thousands commas removed; 'N/A' -> None; trailing '*' on the part number ->
csa_certified=False and the PN is stored without it. Enclosure, voltage,
phase and service come from the table (section title), never from the PN;
the PN suffix is only a cross-check.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from app.domain.models import NUMERIC_FIELDS, Actuator


class NormalizationError(ValueError):
    """A cell or part number cannot be normalized; message names table/PN/field."""


# Section/table title metadata per table_id (source of enclosure/voltage/phase/service).
SECTION_META: dict[str, dict[str, Any]] = {
    "T1_wp_110v_1ph": {"enclosure": "weatherproof", "certifications": "CSA, CE, & UKCA",
                       "voltage": "110V", "current_type": "AC", "phase": 1,
                       "service": "on_off_and_modulating"},
    "T2_wp_220v_1ph": {"enclosure": "weatherproof", "certifications": "CSA, CE, & UKCA",
                       "voltage": "220V", "current_type": "AC", "phase": 1,
                       "service": "on_off_and_modulating"},
    "T3_wp_220v_3ph": {"enclosure": "weatherproof", "certifications": "CSA, CE, & UKCA",
                       "voltage": "220V", "current_type": "AC", "phase": 3,
                       "service": "unspecified"},
    "T4_xp_24v_onoff": {"enclosure": "explosionproof", "certifications": "CSA",
                        "voltage": "24V AC/DC", "current_type": "AC/DC", "phase": None,
                        "service": "on_off"},
    "T5_xp_24vdc_mod": {"enclosure": "explosionproof", "certifications": "CSA",
                        "voltage": "24V DC", "current_type": "DC", "phase": None,
                        "service": "modulating"},
    "T6_xp_110v_1ph": {"enclosure": "explosionproof", "certifications": "CSA",
                       "voltage": "110V", "current_type": "AC", "phase": 1,
                       "service": "on_off_and_modulating"},
    "T7_xp_220v_1ph": {"enclosure": "explosionproof", "certifications": "CSA",
                       "voltage": "220V", "current_type": "AC", "phase": 1,
                       "service": "on_off_and_modulating"},
}

# Expected PN voltage suffix per table (cross-check only).
SUFFIX_BY_TABLE: dict[str, str] = {
    "T1_wp_110v_1ph": "11300000",
    "T2_wp_220v_1ph": "11320000",
    "T3_wp_220v_3ph": "11330C00",
    "T4_xp_24v_onoff": "11380000",
    "T5_xp_24vdc_mod": "11370000",
    "T6_xp_110v_1ph": "11300000",
    "T7_xp_220v_1ph": "11320000",
}


_THOUSANDS_RE = re.compile(r"^\d{1,3}(,\d{3})+(\.\d+)?$")
_PLAIN_RE = re.compile(r"^\d+(\.\d+)?$")
_NA_RE = re.compile(r"^N\s*/\s*A$", re.IGNORECASE)
_NUMERIC = frozenset(NUMERIC_FIELDS)


def parse_number(raw: str | None) -> float | None:
    """'26,500' -> 26500.0; '1.2' -> 1.2; 'N/A', '', None -> None.
    Anything else that is not a plain number -> NormalizationError.

    No OCR repair: the text is taken exactly as printed.
    """
    if raw is None:
        return None
    text = raw.strip()
    if not text or _NA_RE.match(text):
        return None
    if "," in text:
        if not _THOUSANDS_RE.match(text):
            raise NormalizationError(f"invalid number (bad thousands separator): {raw!r}")
        text = text.replace(",", "")
    if not _PLAIN_RE.match(text):
        raise NormalizationError(f"not a plain number: {raw!r}")
    return float(text)


def split_part_number(raw: str) -> tuple[str, bool]:
    """Strip spaces; trailing '*' -> (pn_without_star, False), else (pn, True).
    '766A00-11320000/A*' -> ('766A00-11320000/A', False)."""
    pn = "".join(raw.split())
    if pn.endswith("*"):
        return pn.rstrip("*"), False
    return pn, True


def check_suffix(table_id: str, part_number: str) -> None:
    """Raise NormalizationError if the PN suffix does not match SUFFIX_BY_TABLE."""
    expected = SUFFIX_BY_TABLE.get(table_id)
    if expected is None:
        raise NormalizationError(f"unknown table_id: {table_id!r}")
    m = re.match(r"^[^-]+-([^/]+)(/|$)", part_number)
    actual = m.group(1) if m else None
    if actual != expected:
        raise NormalizationError(
            f"{table_id}: part number {part_number!r} has suffix {actual!r}, expected {expected!r}"
        )


def normalize_row(
    table_id: str, raw_pn: str, raw_cells: dict[str, str | None], row_index: int | None = None
) -> Actuator:
    """Build an Actuator from raw strings: PN via split_part_number + check_suffix,
    meta from SECTION_META[table_id], each numeric field via parse_number.
    Unknown field names -> NormalizationError."""
    meta = SECTION_META.get(table_id)
    if meta is None:
        raise NormalizationError(f"unknown table_id: {table_id!r}")
    pn, csa = split_part_number(raw_pn)
    check_suffix(table_id, pn)
    values: dict[str, float | None] = {}
    for name, cell in raw_cells.items():
        if name not in _NUMERIC:
            raise NormalizationError(f"{table_id}/{pn}: unknown field {name!r}")
        try:
            values[name] = parse_number(cell)
        except NormalizationError as exc:
            raise NormalizationError(f"{table_id}/{pn}/{name}: {exc}") from exc
    try:
        return Actuator.model_validate(
            {
                **meta,
                **values,
                "table_id": table_id,
                "part_number": pn,
                "csa_certified": csa,
                "row_index": row_index,
            }
        )
    except ValidationError as exc:
        raise NormalizationError(f"{table_id}/{pn}: invalid row: {exc}") from exc

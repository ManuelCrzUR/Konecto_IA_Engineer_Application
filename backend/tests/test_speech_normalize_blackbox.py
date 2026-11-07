"""Black-box tests for normalize_transcript (D-53).

Written from the contract docstring in app/speech/normalize.py only.
"""

from __future__ import annotations

import pytest

from app.speech.normalize import normalize_transcript


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Spanish spoken separators "guion" and "barra", thousands commas removed.
        ("764 a 00 guion 11,300,000 barra a", "764A00-11300000/A"),
        # English spoken separators "dash" and "slash", spaces between groups removed.
        ("764 a 00 dash 11 300 000 slash a", "764A00-11300000/A"),
        # Accented "guión" and "barra oblicua".
        ("763 b 00 guión 11330 c 00 barra oblicua a", "763B00-11330C00/A"),
    ],
)
def test_spoken_separators_become_symbols(text: str, expected: str) -> None:
    assert normalize_transcript(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # "by" between the model number and two digits becomes X.
        ("764 by 30 guion 11320000 slash a", "764X30-11320000/A"),
        # "por" between the model number and two digits, base only.
        ("762 por 30", "762X30"),
        # "equis" between the model number and two digits.
        ("764 equis 30 guion 11320000 barra a", "764X30-11320000/A"),
    ],
)
def test_by_por_equis_become_x(text: str, expected: str) -> None:
    assert normalize_transcript(text) == expected


def test_thousands_commas_removed_inside_part_number() -> None:
    assert normalize_transcript("764A00-11,300,000/A") == "764A00-11300000/A"


def test_lowercase_letters_are_uppercased() -> None:
    assert normalize_transcript("764a00-11300000/a") == "764A00-11300000/A"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Trailing spoken "barra a" becomes "/A".
        ("764A00-11300000 barra a", "764A00-11300000/A"),
        # Spoken "slash A" with spaces between groups; canonical shape inserts the hyphen.
        ("764A00 11300000 slash A", "764A00-11300000/A"),
    ],
)
def test_trailing_barra_or_slash_a_becomes_slash_a(text: str, expected: str) -> None:
    assert normalize_transcript(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Base-only spans keep only the 6-char base.
        ("76 4a 00", "764A00"),
        ("764 a 00", "764A00"),
    ],
)
def test_base_only_spans_become_six_char_base(text: str, expected: str) -> None:
    assert normalize_transcript(text) == expected


def test_already_canonical_part_number_unchanged() -> None:
    assert normalize_transcript("764X30-11320000/A") == "764X30-11320000/A"


def test_text_without_model_number_only_stripped() -> None:
    assert (
        normalize_transcript("  cuál es el torque del actuador?  ")
        == "cuál es el torque del actuador?"
    )


def test_model_outside_761_to_767_left_unchanged() -> None:
    text = "768 a 00 guion 11300000 barra a"
    assert normalize_transcript(text) == text


@pytest.mark.parametrize(
    "text",
    [
        # Suffix with 9 digits: never padded, trimmed or guessed.
        "764A00-113000000/A",
        # Suffix with 7 digits: never padded.
        "764A00-1130000/A",
    ],
)
def test_shapes_that_do_not_fit_left_as_written(text: str) -> None:
    assert normalize_transcript(text) == text


def test_misheard_digit_is_not_snapped_to_catalog() -> None:
    assert normalize_transcript("764 a 09 guion 11300000 barra a") == "764A09-11300000/A"


def test_two_part_numbers_in_one_sentence() -> None:
    text = "compara 764 a 00 guion 11300000 barra a y 763 b 00 guion 11330 c 00 barra a"
    assert normalize_transcript(text) == "compara 764A00-11300000/A y 763B00-11330C00/A"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("(764 a 00 guion 11300000 barra a).", "(764A00-11300000/A)."),
        ("¿Qué es 764 a 00 guion 11300000 barra a?", "¿Qué es 764A00-11300000/A?"),
    ],
)
def test_punctuation_around_part_number_preserved(text: str, expected: str) -> None:
    assert normalize_transcript(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", ""),
        ("   ", ""),
        ("🔧 764 a 00 🙂", "🔧 764A00 🙂"),
        ("hola " * 20000, ("hola " * 20000).strip()),
    ],
)
def test_never_raises_on_odd_input(text: str, expected: str) -> None:
    assert normalize_transcript(text) == expected

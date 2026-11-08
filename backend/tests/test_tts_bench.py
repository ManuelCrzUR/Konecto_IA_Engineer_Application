import importlib.util
import sys
import wave
from pathlib import Path

_dir = Path(__file__).resolve().parents[1] / "scripts" / "tts_bench"
sys.path.insert(0, str(_dir))
import helpers as tts

_spec = importlib.util.spec_from_file_location("tts_run", _dir / "run.py")
run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run)


def test_pcm_to_wav_header_and_frames(tmp_path):
    pcm = b"\x00\x01" * 24000
    out = tmp_path / "a.wav"
    secs = tts.pcm_to_wav(pcm, out, 24000)
    with wave.open(str(out)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 24000)
        assert w.getnframes() == 24000
    assert secs == 1.0


def test_concatenated_pcm_frame_count(tmp_path):
    parts = [b"\x00\x01" * 1000, b"\x02\x03" * 500, b"\x04\x05" * 250]
    out = tmp_path / "c.wav"
    tts.pcm_to_wav(b"".join(parts), out, 24000)
    with wave.open(str(out)) as w:
        assert w.getnframes() == 1750


def test_estimate_cost():
    text = "x" * 100
    assert tts.estimate_cost("elevenlabs/eleven-flash-v2.5", text, 5) == 100 * 0.00004
    assert tts.estimate_cost("elevenlabs/eleven-multilingual-v2", text, 5) == 100 * 0.00008
    gem = tts.estimate_cost("google/gemini-3.8-flash-tts", text, 2)
    assert abs(gem - (25 * 0.0000005 + 2 * 25 * 0.000009)) < 1e-12


def test_parse_rate():
    assert tts.parse_rate("audio/pcm;rate=16000") == 16000
    assert tts.parse_rate("audio/pcm") == 24000
    assert tts.parse_rate(None) == 24000


def test_split_keeps_part_numbers_and_decimals():
    s = run.TEXTS["es2"]
    parts = tts.split_sentences(s)
    assert parts[0] == "Te recomiendo dos opciones."
    assert any("762B00-11320000/A" in p and "1.1 A" in p for p in parts)
    assert len(parts) == 4
    assert " ".join(parts) == s
    # Part number right before the sentence end is not broken, but the end still splits.
    assert tts.split_sentences("Es el 764A00-11300000/A. Listo.") == [
        "Es el 764A00-11300000/A.",
        "Listo.",
    ]
    assert tts.split_sentences("Valor 1.1 A y 2.0 A") == ["Valor 1.1 A y 2.0 A"]


def test_split_spanish_question_marks():
    assert tts.split_sentences("Hola. ¿Cuál quieres? ¡Dime! Gracias.") == [
        "Hola.",
        "¿Cuál quieres?",
        "¡Dime!",
        "Gracias.",
    ]


def test_build_body_provider_options():
    eleven = tts.build_body("elevenlabs/eleven-flash-v2.5", "laura", "hola", "es")
    assert eleven["provider"] == {"options": {"elevenlabs": {"language_code": "es"}}}
    assert eleven["response_format"] == "mp3"
    gem = tts.build_body("google/gemini-3.8-flash-tts", "Kore", "hola", "es")
    assert "provider" not in gem and gem["response_format"] == "pcm"
    assert "provider" not in tts.build_body("elevenlabs/eleven-flash-v2.5", "sarah", "hola")


def test_sum_costs():
    assert tts.sum_costs([0.1, 0.2]) == 0.1 + 0.2
    assert tts.sum_costs([0.1, None]) is None
    assert tts.sum_costs([]) is None

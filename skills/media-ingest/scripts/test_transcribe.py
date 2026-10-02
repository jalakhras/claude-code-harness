"""Unit + integration tests for the transcribe fix (run via uv/pytest):

  uv run --with pytest python -m pytest skills/media-ingest/scripts/test_transcribe.py -q

Covers the decision (TRANSCRIBE_OPTS, WHISPER_UV_DEPS) and that the call site
and the batch runner actually use it. No model or audio needed - faster_whisper
is faked.
"""
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import transcribe  # noqa: E402


def test_transcribe_opts_decision():
    # kill cross-segment conditioning (repetition loops) + set a VAD silence floor
    assert transcribe.TRANSCRIBE_OPTS["condition_on_previous_text"] is False
    assert transcribe.TRANSCRIBE_OPTS["vad_filter"] is True
    assert transcribe.TRANSCRIBE_OPTS["vad_parameters"] == {"min_silence_duration_ms": 500}


def test_whisper_uv_deps_pins_av():
    # av 19.0.0 breaks faster-whisper 1.2.1 (metadata_errors) -> must be pinned
    assert "faster-whisper" in transcribe.WHISPER_UV_DEPS
    assert "av<19" in transcribe.WHISPER_UV_DEPS


def test_transcribe_on_forwards_opts(monkeypatch):
    # integration: the real call site forwards the decision to faster-whisper
    captured = {}

    class FakeModel:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, media, **kwargs):
            captured.update(kwargs)
            info = types.SimpleNamespace(language="ar", language_probability=1.0, duration=1.0)
            return iter([]), info

    fake = types.ModuleType("faster_whisper")
    fake.WhisperModel = FakeModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake)

    transcribe.transcribe_on("large-v3", "cpu", "int8", "x.wav", "ar", "")
    assert captured.get("condition_on_previous_text") is False
    assert captured.get("vad_filter") is True
    assert captured.get("vad_parameters") == {"min_silence_duration_ms": 500}


def test_batch_runner_builds_uv_cmd_with_pin():
    # the batch runner's uv command is built from the pinned dep list
    import batch_ingest  # noqa: E402  (imports transcribe; must not error)
    cmd = batch_ingest.transcribe_cmd(Path("v.mp4"), Path("out.md"),
                                      model="large-v3", lang="ar", engine="local")
    assert "av<19" in cmd
    assert "faster-whisper" in cmd
    # av<19 must be introduced by its own --with flag
    assert cmd[cmd.index("av<19") - 1] == "--with"

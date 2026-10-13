#!/usr/bin/env python
"""Spec for pw-run.py keeping evidence: the HTML report and the traces.

pw-run passes its own --reporter, which replaces the config's reporters, so no
HTML report was ever written. With --html-report the html reporter is added and
pointed at that directory; --artifacts-dir copies test-results/ (traces,
screenshots) there BEFORE the failure re-run, which would otherwise wipe it.
"""
import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location("pw_run", pathlib.Path(__file__).with_name("pw-run.py"))
pw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pw)


def test_html_report_adds_the_reporter_and_its_directory(tmp_path):
    cmd, env = pw.playwright_invocation(["--project=desktop"], tmp_path / "r.json",
                                        progress=True, html_dir=tmp_path / "html")
    assert "--reporter=line,json,html" in cmd
    assert env["PLAYWRIGHT_HTML_OUTPUT_DIR"] == str(tmp_path / "html")
    assert env["PLAYWRIGHT_HTML_OPEN"] == "never"
    assert env["PLAYWRIGHT_JSON_OUTPUT_NAME"] == str(tmp_path / "r.json")


def test_without_html_report_nothing_changes(tmp_path):
    cmd, env = pw.playwright_invocation(["x"], tmp_path / "r.json", progress=False, html_dir=None)
    assert "--reporter=json" in cmd
    assert "PLAYWRIGHT_HTML_OUTPUT_DIR" not in env


def test_artifacts_are_copied_and_a_missing_folder_is_not_an_error(tmp_path):
    src = tmp_path / "angular" / "test-results" / "spec-a"
    src.mkdir(parents=True)
    (src / "trace.zip").write_bytes(b"zip")
    dest = tmp_path / "evidence"
    assert pw.copy_artifacts(tmp_path / "angular", dest) == 1
    assert (dest / "test-results" / "spec-a" / "trace.zip").read_bytes() == b"zip"
    assert pw.copy_artifacts(tmp_path / "nothing-here", tmp_path / "e2") == 0


def _run_pw(*argv):
    import subprocess
    import sys
    p = subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name("pw-run.py")), *argv],
                       capture_output=True, text=True)
    return p.stdout + p.stderr


def test_playwright_options_are_accepted_with_or_without_a_path_or_separator(tmp_path):
    """Playwright's own options must pass through in any order: option-only, path first, option
    first, or after `--` (argparse's REMAINDER used to reject "--project=…" unless a path came first)."""
    missing = str(tmp_path / "no-such-angular-dir")
    for tail in (["--project=desktop", "--project=mobile"],
                 ["exam-form", "--project=desktop"],
                 ["--project=desktop", "exam-form", "--grep", "opens"],
                 ["--", "--project=desktop"]):
        out = _run_pw("--cwd", missing, "--progress", *tail)
        assert "no such directory" in out, (tail, out)   # parsed; stopped later, at the cwd check
        assert "unrecognized arguments" not in out


def test_pass_through_keeps_order_and_drops_only_the_separator():
    ours, rest = pw.parse_cli(["--no-llm", "--project=desktop", "spec-a", "--grep", "x", "--", "--headed"])
    assert ours.no_llm and rest == ["--project=desktop", "spec-a", "--grep", "x", "--headed"]


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))

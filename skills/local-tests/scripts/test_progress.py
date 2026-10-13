#!/usr/bin/env python
"""Spec for the --progress feature of dotnet-run.py and pw-run.py.

The formatting and the Playwright counter parse are pure and asserted directly;
the dotnet polling mechanism is smoke-tested against a fake process that writes
.trx files over time (no real dotnet), so the throttled tick and the stderr
drain are exercised without a suite. Modules load via importlib (hyphen names).
"""
import importlib.util
import pathlib
import sys
import textwrap


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).with_name(filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dr = _load("dotnet_run", "dotnet-run.py")
pw = _load("pw_run", "pw-run.py")


def test_dotnet_progress_line_names_each_project_and_failures():
    counts = {
        "Co.Domain.Tests": {"passed": 445, "failed": 0, "skipped": 0, "done": True},
        "Co.Application.Tests": {"passed": 300, "failed": 2, "skipped": 0, "done": False},
    }
    line = dr.fmt_dotnet_progress(counts, dr.short_names(counts))
    assert "Domain.Tests 445 done" in line and "Application.Tests 302" in line
    assert "failed 2" in line


def test_pw_counter_parse():
    assert pw.parse_counter("[12/50] exam-form opens") == (12, 50)
    assert pw.parse_counter("Running 50 tests using 4 workers") is None
    assert pw.parse_counter("") is None


def test_run_projects_streams_live_counts_and_failures(tmp_path, capsys, monkeypatch):
    """Fake per-project 'dotnet test' prints console-logger lines over ~1s: the
    counter must tick while it runs, a failure must be named at once, and the
    worst exit code must survive."""
    fake = tmp_path / "fake_dotnet.py"
    fake.write_text(textwrap.dedent("""
        import sys, time
        name = sys.argv[1]
        for i in range(4):
            print(f"  Passed {name}.T{i} [1 ms]", flush=True); time.sleep(0.15)
        if name == "B":
            print("  Failed B.Breaks [2 ms]", flush=True)
        sys.exit(1 if name == "B" else 0)
    """), encoding="utf-8")
    monkeypatch.setattr(dr, "project_test_cmd",
                        lambda project, results_dir, test_filter="": [sys.executable, str(fake), project.stem])

    rc, tails = dr.run_projects([pathlib.Path("A.csproj"), pathlib.Path("B.csproj")],
                                cwd=str(tmp_path), results_dir=str(tmp_path), progress=True, interval=0.2)
    err = capsys.readouterr().err
    assert rc == 1                                        # B failed -> worst exit kept
    assert "[dotnet-run] progress:" in err                # ticked while running
    assert "[dotnet-run] FAIL B: B.Breaks" in err         # failure named immediately
    assert set(tails) == {"A", "B"}


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))

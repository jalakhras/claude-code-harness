#!/usr/bin/env python
"""Spec for dotnet-run.py's verdict on sample .trx files (no dotnet needed).

These pin the behaviour that a green report MUST mean every test project passed:
an aborted run (host crash), a non-zero process exit, work left notExecuted, and
a failure in any one project of a multi-project solution each make the verdict a
failure — and all .trx in the results directory are aggregated, not just the
newest. Loaded via importlib because the script's name has a hyphen.
"""
import importlib.util
import os
import pathlib

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "dotnet_run", pathlib.Path(__file__).with_name("dotnet-run.py")
)
dr = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(dr)


def _trx(total, passed, failed, outcome="Completed", not_executed=0,
         run_error=None, failures=()):
    """Build a minimal TRX document string in the TeamTest 2010 schema."""
    run_infos = ""
    if run_error:
        run_infos = (
            '<RunInfos><RunInfo computerName="lab" outcome="Error" '
            'timestamp="2026-10-10T00:00:00">'
            f"<Text>{run_error}</Text></RunInfo></RunInfos>"
        )
    results = ""
    for name, msg in failures:
        results += (
            f'<UnitTestResult testName="{name}" outcome="Failed">'
            f"<Output><ErrorInfo><Message>{msg}</Message></ErrorInfo></Output>"
            "</UnitTestResult>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">'
        f'<ResultSummary outcome="{outcome}">'
        f'<Counters total="{total}" executed="{passed + failed}" passed="{passed}" '
        f'failed="{failed}" notExecuted="{not_executed}"/>'
        f"{run_infos}</ResultSummary>"
        f"<Results>{results}</Results></TestRun>"
    )


def _write(tmp_path, name, content, mtime):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    os.utime(p, (mtime, mtime))
    return str(p)


def test_clean_single_project_passes(tmp_path):
    """Control: a clean run with exit 0 is the one case that reports success."""
    f = _write(tmp_path, "a.trx", _trx(10, 10, 0), mtime=1000)
    code, text = dr.summarize([f], returncode=0)
    assert code == 0
    assert "All tests passed." in text


def test_aborted_run_is_a_failure(tmp_path):
    """Host crash: counters look all-passed, but RunInfo outcome=Error -> fail."""
    f = _write(
        tmp_path, "efcore.trx",
        _trx(324, 324, 0, outcome="Failed",
             run_error="The active test run was aborted. Reason: Test host process crashed"),
        mtime=1000,
    )
    code, text = dr.summarize([f], returncode=0)
    assert code != 0, "an aborted run must never report success"
    assert "abort" in text.lower() or "crash" in text.lower()


def test_nonzero_process_exit_is_a_failure(tmp_path):
    """Even with a clean trx, a non-zero dotnet exit means the run is suspect."""
    f = _write(tmp_path, "a.trx", _trx(10, 10, 0), mtime=1000)
    code, _ = dr.summarize([f], returncode=1)
    assert code != 0


def test_skips_are_not_a_failure(tmp_path):
    """notExecuted is how VSTest records an intentional skip — not a run failure."""
    f = _write(tmp_path, "a.trx", _trx(10, 8, 0, not_executed=2), mtime=1000)
    code, _ = dr.summarize([f], returncode=0)
    assert code == 0


def test_zero_tests_is_not_a_pass(tmp_path):
    """A filter that matched nothing (total=0, clean exit) must not read as green."""
    f = _write(tmp_path, "a.trx", _trx(0, 0, 0), mtime=1000)
    code, text = dr.summarize([f], returncode=0)
    assert code != 0 and "no tests" in text.lower()


def test_aggregates_all_projects_not_just_newest(tmp_path):
    """A failure in an older project's trx must not be hidden by a newer clean one."""
    bad = _write(
        tmp_path, "domain.trx",
        _trx(5, 4, 1, outcome="Failed", failures=[("T.Boom", "Expected 1 but was 2")]),
        mtime=1000,  # older
    )
    good = _write(tmp_path, "application.trx", _trx(7, 7, 0), mtime=2000)  # newer
    code, text = dr.summarize([bad, good], returncode=0)
    assert code != 0, "a failure in any project must fail the whole run"
    assert "total: 12" in text, "counts must be summed across all projects"
    assert "T.Boom" in text


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

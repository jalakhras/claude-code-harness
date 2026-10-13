#!/usr/bin/env python
"""Spec for the pass/fail verdict of pytest-run.py and pw-run.py.

Both runners used to declare success from a parsed report alone, so a run that
never really ran (no tests collected, a dead webServer, a non-zero/interrupted
exit) reported green. These pin the hardened rule: a green verdict needs tests
that actually ran under a trustworthy exit. Modules are loaded via importlib
because their file names carry a hyphen.
"""
import importlib.util
import pathlib

import pytest


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).with_name(filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pr = _load("pytest_run", "pytest-run.py")
pw = _load("pw_run", "pw-run.py")


# --- pytest-run.verdict(counts, still_failures, returncode) ------------------
def test_pytest_clean_pass():
    assert pr.verdict({"tests": 5}, [], 0) == (0, None)


def test_pytest_real_failures():
    code, reason = pr.verdict({"tests": 5}, [("mod::t", "boom")], 1)
    assert code == 1 and "failed" in reason


def test_pytest_zero_tests_is_not_a_pass():
    code, reason = pr.verdict({"tests": 0}, [], 0)
    assert code == 1 and "collect" in reason


def test_pytest_bad_exit_code_overrides_clean_report():
    for rc in (2, 3, 4, 5):
        code, reason = pr.verdict({"tests": 10}, [], rc)
        assert code == 1 and str(rc) in reason


# --- pw-run.verdict(rows, errors, still_failures) ----------------------------
def test_pw_clean_pass():
    assert pw.verdict([{"status": "passed"}], [], []) == (0, None)


def test_pw_no_tests_is_not_a_pass():
    code, reason = pw.verdict([], [], [])
    assert code == 1 and "no tests" in reason


def test_pw_global_runner_error_fails():
    code, reason = pw.verdict([{"status": "passed"}], [{"message": "Error: webServer did not start"}], [])
    assert code == 1 and "runner error" in reason


def test_pw_real_failures():
    code, reason = pw.verdict([{"status": "failed"}], [], [{"title": "x"}])
    assert code == 1 and "failed" in reason


# --- pytest-run.classify_rerun(fails, ran, rerun_failed) ---------------------
def test_rerun_passed_is_flaky():
    fails = [("m::t", "boom")]
    flaky, still = pr.classify_rerun(fails, ran={"m::t"}, rerun_failed=set())
    assert flaky == ["m::t"] and still == []


def test_rerun_failed_again_stays_failed():
    fails = [("m::t", "boom")]
    flaky, still = pr.classify_rerun(fails, ran={"m::t"}, rerun_failed={"m::t"})
    assert flaky == [] and [n for n, _ in still] == ["m::t"]


def test_node_not_rerun_stays_failed_not_flaky():
    """The false-green hole: a node the rerun never re-collected must stay failed."""
    fails = [("m::t", "boom")]
    flaky, still = pr.classify_rerun(fails, ran=set(), rerun_failed=set())
    assert flaky == [] and [n for n, _ in still] == ["m::t"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

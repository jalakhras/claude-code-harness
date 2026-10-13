#!/usr/bin/env python
"""Spec for split_plan.py: how heavy suites are split across this machine and lab-worker1,
and how the two halves' results are merged into one verdict."""
import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location("split_plan", pathlib.Path(__file__).with_name("split_plan.py"))
sp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sp)

PROJECTS = ["test/A.Application.Tests/A.Application.Tests.csproj",
            "test/A.Domain.Tests/A.Domain.Tests.csproj",
            "test/A.EntityFrameworkCore.Tests/A.EntityFrameworkCore.Tests.csproj",
            "test/A.TestBase/A.TestBase.csproj"]


def test_by_type_puts_each_suite_whole_on_one_side():
    p = sp.plan("byType", PROJECTS, dotnet_on="local")
    assert p["local"]["dotnet"] == PROJECTS and p["local"]["playwright"] == []
    assert p["worker"]["dotnet"] == [] and p["worker"]["playwright"] == [None]   # None = unsharded
    q = sp.plan("byType", PROJECTS, dotnet_on="worker")
    assert q["worker"]["dotnet"] == PROJECTS and q["local"]["playwright"] == [None]


def test_by_project_splits_dotnet_by_weight_with_no_overlap_and_no_loss():
    p = sp.plan("byProject", PROJECTS)
    a, b = p["local"]["dotnet"], p["worker"]["dotnet"]
    assert sorted(a + b) == sorted(PROJECTS) and not set(a) & set(b)
    # the heavy EFCore project sits alone against everything else
    ef = [x for x in a + b if "EntityFrameworkCore" in x][0]
    side_with_ef = a if ef in a else b
    assert side_with_ef == [ef]


def test_by_project_shards_playwright_across_both_sides():
    p = sp.plan("byProject", PROJECTS, shards_total=3, local_shards=[1, 2])
    assert p["local"]["playwright"] == ["1/3", "2/3"] and p["worker"]["playwright"] == ["3/3"]
    every = p["local"]["playwright"] + p["worker"]["playwright"]
    assert sorted(every) == ["1/3", "2/3", "3/3"]


def test_bad_shard_assignment_is_refused():
    for bad in ([0], [4], [1, 1], [1, 2, 3]):      # out of range, duplicate, nothing left for the worker
        try:
            sp.plan("byProject", PROJECTS, shards_total=3, local_shards=bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted {bad}")


def test_parse_part_reads_both_runner_summaries():
    text = "\n".join([
        "- total: 2403 | passed: 2398 | **failed: 5**",
        "- per project: Application.Tests 726 | Domain.Tests 467 | EntityFrameworkCore.Tests 1210 | TestBase 0",
        "[pw-run] passed 1012 | failed 0 | flaky 1 | skipped 25 | 410s",
        "[22:10] suite=dotnet on lab-worker1 tree=x@1 fingerprint MATCH 1e4ccd4f046b finished in 293s, exit=1",
    ])
    r = sp.parse_part(text)
    assert r["dotnet_total"] == 2403 and r["dotnet_failed"] == 5
    assert r["projects"] == {"Application.Tests": 726, "Domain.Tests": 467, "EntityFrameworkCore.Tests": 1210, "TestBase": 0}
    assert r["pw_passed"] == 1012 and r["pw_failed"] == 0 and r["pw_skipped"] == 25
    assert r["gate"] == "fingerprint MATCH 1e4ccd4f046b"


def test_parse_part_reads_windows_line_endings():
    """The halves' logs come from Windows processes: every line ends in CRLF, and the last item on
    a per-project line used to arrive as "TestBase 0\\r" and be dropped."""
    text = "- total: 19 | passed: 19 | **failed: 0**\r\n- per project: Domain.Tests 19 | TestBase 0\r\n"
    assert sp.parse_part(text)["projects"] == {"Domain.Tests": 19, "TestBase": 0}


def _part(side, exit_code, projects=None, pw=None, gate="fingerprint MATCH abc", seconds=100):
    r = {"side": side, "exit": exit_code, "seconds": seconds, "gate": gate,
         "projects": projects or {}, "dotnet_total": sum((projects or {}).values()), "dotnet_failed": 0,
         "pw_passed": (pw or 0), "pw_failed": 0, "pw_skipped": 0}
    return r


def test_merge_green_only_when_every_part_is_green_and_a_gate():
    ok = sp.merge([_part("local", 0, {"Domain.Tests": 467}, gate="local tree"),
                   _part("worker", 0, {"EntityFrameworkCore.Tests": 1210})],
                  expected_projects=["Domain.Tests", "EntityFrameworkCore.Tests"])
    assert ok["exit"] == 0 and ok["dotnet_total"] == 1677
    bad = sp.merge([_part("local", 0, {"Domain.Tests": 467}, gate="local tree"), _part("worker", 1, {"EntityFrameworkCore.Tests": 1210})],
                   expected_projects=["Domain.Tests", "EntityFrameworkCore.Tests"])
    assert bad["exit"] == 1
    not_gate = sp.merge([_part("local", 0, gate="local tree"), _part("worker", 4, gate="NOT A GATE (-NoSync)")])
    assert not_gate["exit"] == 4


def test_merge_catches_a_project_counted_twice_or_missing():
    dup = sp.merge([_part("local", 0, {"Domain.Tests": 467}, gate="local tree"), _part("worker", 0, {"Domain.Tests": 467})],
                   expected_projects=["Domain.Tests"])
    assert dup["exit"] == 1 and any("twice" in r for r in dup["reasons"])
    lost = sp.merge([_part("local", 0, {"Domain.Tests": 467}, gate="local tree")],
                    expected_projects=["Domain.Tests", "EntityFrameworkCore.Tests"])
    assert lost["exit"] == 1 and any("missing" in r for r in lost["reasons"])


def test_a_local_part_whose_tree_changed_mid_run_is_not_a_gate():
    m = sp.merge([_part("local", 0, gate="NOT A GATE (the working tree changed during the run)"),
                  _part("worker", 0)])
    assert m["exit"] == 4 and m["not_gate"] == ["local"]


def test_merge_matches_short_and_full_project_names():
    """A side running one project prints its full name, a side running several prints them without
    the shared prefix; both must map to the same expected project."""
    full = ["Co.Domain.Tests", "Co.EntityFrameworkCore.Tests"]
    m = sp.merge([_part("local", 0, {"Co.EntityFrameworkCore.Tests": 1210}, gate="local tree"),
                  _part("worker", 0, {"Domain.Tests": 467})], expected_projects=full)
    assert m["exit"] == 0, m["reasons"]
    dup = sp.merge([_part("local", 0, {"Co.Domain.Tests": 467}, gate="local tree"),
                    _part("worker", 0, {"Domain.Tests": 467})], expected_projects=full)
    assert any("twice" in r for r in dup["reasons"])


def test_discover_uses_the_runners_project_finder(tmp_path):
    t = tmp_path / "test" / "X.Tests"; t.mkdir(parents=True)
    (t / "X.Tests.csproj").write_text('<Project><ItemGroup><PackageReference Include="Microsoft.NET.Test.Sdk"/></ItemGroup></Project>', encoding="utf-8")
    s = tmp_path / "src" / "App"; s.mkdir(parents=True)
    (s / "App.csproj").write_text("<Project/>", encoding="utf-8")
    runners = pathlib.Path(__file__).resolve().parents[2] / "skills" / "local-tests" / "scripts"
    assert sp.discover(str(tmp_path), str(runners)) == ["test/X.Tests/X.Tests.csproj"]


def test_merge_fails_when_no_dotnet_test_ran_on_either_side():
    """Each share may match nothing (--allow-empty); the merged run may not."""
    m = sp.merge([_part("local", 0, {"Co.Domain.Tests": 0}, gate="local tree"),
                  _part("worker", 0, {"Co.EntityFrameworkCore.Tests": 0})],
                 expected_projects=["Co.Domain.Tests", "Co.EntityFrameworkCore.Tests"])
    assert m["exit"] == 1 and any("no .NET test ran" in r for r in m["reasons"])


def test_a_side_that_was_given_playwright_must_have_run_some():
    """A step that exits 0 without running anything is not a pass: the side was planned Playwright
    steps, so it must report Playwright counts."""
    quiet = _part("worker", 0); quiet["pw_steps"] = 1
    m = sp.merge([_part("local", 0, gate="local tree"), quiet])
    assert m["exit"] == 1 and any("Playwright" in r and "worker" in r for r in m["reasons"])
    ran = _part("worker", 0, pw=2113); ran["pw_steps"] = 1
    assert sp.merge([_part("local", 0, gate="local tree"), ran])["exit"] == 0


def test_merge_wall_clock_is_the_longest_part_and_reports_the_sum():
    m = sp.merge([_part("local", 0, seconds=280, gate="local tree"), _part("worker", 0, seconds=930)])
    assert m["sum_seconds"] == 1210


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))

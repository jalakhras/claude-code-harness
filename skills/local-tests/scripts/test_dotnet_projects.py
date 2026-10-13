#!/usr/bin/env python
"""Spec for dotnet-run.py running each test project on its own.

A fixed `LogFileName=results.trx` on a .sln makes every project write the same
file, so only one project survives (a crashed EFCore run once reported a false
324/324). VSTest has no per-assembly token in LogFileName (`{assembly}` is taken
literally) and LogFilePrefix only adds a one-second timestamp, so dotnet-run runs
one `dotnet test` per test project, each with its own trx named after it.
"""
import importlib.util
import pathlib
import sys
import textwrap

spec = importlib.util.spec_from_file_location("dotnet_run", pathlib.Path(__file__).with_name("dotnet-run.py"))
dr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dr)


def _csproj(path, test_sdk=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    ref = '<PackageReference Include="Microsoft.NET.Test.Sdk" />' if test_sdk else ""
    path.write_text(f"<Project><ItemGroup>{ref}</ItemGroup></Project>", encoding="utf-8")


def test_finds_only_test_projects_and_skips_build_output(tmp_path):
    _csproj(tmp_path / "test" / "A.Tests" / "A.Tests.csproj")
    _csproj(tmp_path / "test" / "B.Tests" / "B.Tests.csproj")
    _csproj(tmp_path / "src" / "App" / "App.csproj", test_sdk=False)
    _csproj(tmp_path / "test" / "A.Tests" / "bin" / "Debug" / "Copy.csproj")
    found = [p.name for p in dr.find_test_projects(str(tmp_path), "")]
    assert found == ["A.Tests.csproj", "B.Tests.csproj"]


def test_finds_mstest_sdk_and_istestproject_projects(tmp_path):
    a = tmp_path / "A.Tests" / "A.Tests.csproj"; a.parent.mkdir()
    a.write_text('<Project Sdk="MSTest.Sdk/3.6.0"></Project>', encoding="utf-8")
    b = tmp_path / "B.Tests" / "B.Tests.csproj"; b.parent.mkdir()
    b.write_text("<Project><PropertyGroup><IsTestProject>true</IsTestProject></PropertyGroup></Project>", encoding="utf-8")
    assert [p.name for p in dr.find_test_projects(str(tmp_path), "")] == ["A.Tests.csproj", "B.Tests.csproj"]


def test_stale_trx_in_a_reused_results_dir_is_cleared(tmp_path):
    old = tmp_path / "Co.EntityFrameworkCore.Tests.trx"
    old.write_text("<old/>", encoding="utf-8")
    keep = tmp_path / "notes.txt"
    keep.write_text("x", encoding="utf-8")
    dr.clear_old_trx(str(tmp_path))
    assert not old.exists() and keep.exists()


def test_explicit_csproj_is_used_as_is(tmp_path):
    p = tmp_path / "X.Tests.csproj"
    _csproj(p)
    assert dr.find_test_projects(str(tmp_path), [str(p)]) == [p]


def test_several_explicit_projects_are_all_used_and_nothing_else(tmp_path):
    """run-split gives each machine its own share: --project a.csproj --project b.csproj."""
    a = tmp_path / "A.Tests" / "A.Tests.csproj"; _csproj(a)
    b = tmp_path / "B.Tests" / "B.Tests.csproj"; _csproj(b)
    _csproj(tmp_path / "C.Tests" / "C.Tests.csproj")
    assert dr.find_test_projects(str(tmp_path), [str(a), str(b)]) == [a, b]


def test_cli_accepts_project_more_than_once():
    ns = dr.build_parser().parse_args(["--project", "a.csproj", "--project", "b.csproj"])
    assert ns.project == ["a.csproj", "b.csproj"]
    assert dr.build_parser().parse_args([]).project == []


def test_each_project_gets_its_own_trx_name():
    cmd = dr.project_test_cmd(pathlib.Path("/r/test/A.Tests/A.Tests.csproj"), "/out", "Name~X")
    joined = " ".join(cmd)
    assert "trx;LogFileName=A.Tests.trx" in joined
    assert "--no-build" in cmd and "--filter" in cmd and "Name~X" in cmd
    assert "console;verbosity=normal" in joined          # live per-test lines


def test_console_line_parse():
    assert dr.parse_console_line("  Passed Ns.T.Works [3 ms]") == ("passed", "Ns.T.Works")
    assert dr.parse_console_line("  Failed Ns.T.Breaks [12 ms]") == ("failed", "Ns.T.Breaks")
    assert dr.parse_console_line("  Skipped Ns.T.Later") == ("skipped", "Ns.T.Later")
    assert dr.parse_console_line("Test run for /x/A.Tests.dll (.NETCoreApp,Version=v10.0)") is None
    assert dr.parse_console_line("") is None


_TRX = textwrap.dedent("""\
    <?xml version="1.0"?>
    <TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">
      <ResultSummary outcome="{outcome}">
        <Counters total="{n}" executed="{n}" passed="{n}" failed="0" notExecuted="0"/>
        {runinfo}
      </ResultSummary><Results></Results></TestRun>""")


def _trx(path, n, outcome="Completed", crashed=False):
    runinfo = ('<RunInfos><RunInfo outcome="Error"><Text>The active test run was aborted. '
               'Reason: Test host process crashed</Text></RunInfo></RunInfos>') if crashed else ""
    path.write_text(_TRX.format(n=n, outcome=outcome, runinfo=runinfo), encoding="utf-8")
    return str(path)


def test_summary_counts_every_project_and_names_them(tmp_path):
    paths = [_trx(tmp_path / "Co.Domain.Tests.trx", 445), _trx(tmp_path / "Co.Application.Tests.trx", 717)]
    code, text = dr.summarize(paths, 0)
    assert code == 0
    assert "total: 1162" in text
    assert "Domain.Tests 445" in text and "Application.Tests 717" in text


def test_crash_in_one_project_fails_the_run(tmp_path):
    paths = [_trx(tmp_path / "Co.Domain.Tests.trx", 445),
             _trx(tmp_path / "Co.EntityFrameworkCore.Tests.trx", 324, outcome="Failed", crashed=True)]
    code, text = dr.summarize(paths, 0)
    assert code == 1
    assert "FAILED" in text and "crashed" in text


def test_an_xunit_fail_echo_is_a_failure_not_a_crash(tmp_path):
    """xUnit also writes each failing test as a RunInfo outcome="Error" line ending in [FAIL]; that
    is the failure already counted, not a crashed host — the summary must not say CRASHED."""
    p = tmp_path / "Co.Domain.Tests.trx"
    p.write_text(_TRX.format(n=445, outcome="Failed", runinfo=(
        '<RunInfos><RunInfo outcome="Error"><Text>[xUnit.net 00:00:00.71]     Ns.T.Keys [FAIL]</Text>'
        '</RunInfo></RunInfos>')).replace('failed="0"', 'failed="1"'), encoding="utf-8")
    code, text = dr.summarize([str(p)], 1)
    assert code == 1 and "1 failed" in text
    assert "CRASHED" not in text and "test run error" not in text


def test_summary_is_ascii_for_the_windows_console(tmp_path):
    code, text = dr.summarize([_trx(tmp_path / "Co.Domain.Tests.trx", 445)], 0)
    assert text.isascii()
    line = dr.fmt_dotnet_progress({"Co.A.Tests": {"passed": 1, "failed": 0, "skipped": 0, "done": True}}, {})
    assert line.isascii()


def test_allow_empty_lets_a_share_match_nothing_but_still_fails_on_failures(tmp_path):
    """run-split gives each machine a share; a filter can legitimately match nothing in one share.
    --allow-empty drops only the "no tests ran" reason — a crash or a failure still fails."""
    empty = [_trx(tmp_path / "Co.EntityFrameworkCore.Tests.trx", 0)]
    assert dr.summarize(empty, 0)[0] == 1
    code, text = dr.summarize(empty, 0, allow_empty=True)
    assert code == 0 and "no tests ran" not in text
    crashed = [_trx(tmp_path / "Co.X.Tests.trx", 0, outcome="Failed", crashed=True)]
    assert dr.summarize(crashed, 0, allow_empty=True)[0] == 1


def test_a_project_without_a_trx_fails_the_run(tmp_path):
    paths = [_trx(tmp_path / "Co.Domain.Tests.trx", 445)]
    code, text = dr.summarize(paths, 0, expected=["Co.Domain.Tests", "Co.EntityFrameworkCore.Tests"])
    assert code == 1
    assert "no .trx for EntityFrameworkCore.Tests" in text


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))

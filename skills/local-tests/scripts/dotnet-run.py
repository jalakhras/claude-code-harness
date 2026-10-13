#!/usr/bin/env python
"""Run a .NET test suite on the machine and print only a fixed-size summary.

Same idea as pw-run.py for the other token-noisy suite: dotnet test output (and
its stack traces) never enters Claude's context — only counts and, per failure,
the test name and first error line. Zero-config: from a solution/project dir,
`python dotnet-run.py` just works; pass a --filter to scope (focused testing).

  python dotnet-run.py [--cwd <dir>] [--project <path>]... [--filter <expr>]
  python dotnet-run.py --cwd D:/Projects/x --filter "FullyQualifiedName~PaperShape"

Verdict (the whole point — a green report must mean every project passed):
a run is a FAILURE when any process exits non-zero, when any test project's
trx carries a RunInfo outcome="Error" (host crash / aborted run), when a
ResultSummary outcome is not Completed/Passed, when a test project produced no
trx, or when any test failed.

One `dotnet test` per test project, in parallel, after one build: VSTest has no
per-assembly token for LogFileName (`{assembly}` is taken literally) and a fixed
name on a .sln makes every project overwrite the same file — that is how a
crashed run once reported 324/324. Each project writes `<ProjectName>.trx`.
With --results-dir the trx files are kept there (evidence); otherwise a temp dir.
"""
import argparse
import glob
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
#: ResultSummary outcomes that mean "the run itself completed cleanly"
OK_OUTCOMES = {None, "Completed", "Passed"}
#: directories never searched for test projects
SKIP_DIRS = {"bin", "obj", "node_modules", ".git", ".vs", "TestResults"}
#: the console logger's per-test line: "  Passed Ns.Type.Method [3 ms]"
CONSOLE_RESULT = re.compile(r"^\s+(Passed|Failed|Skipped)\s+(.+?)(?:\s+\[[^\]]*\])?\s*$")
#: what marks a test project in its .csproj (a reference set only in Directory.Build.props is not
#: seen — pass --project for such a repo)
TEST_PROJECT = re.compile(r"Microsoft\.NET\.Test\.Sdk|Sdk=\"MSTest\.Sdk|<IsTestProject>\s*true", re.I)
#: xUnit also records each failing test as a RunInfo outcome="Error" line ending in [FAIL]
XUNIT_FAIL_ECHO = re.compile(r"\[FAIL\]\s*$")
#: failing tests named live before the progress counter alone carries the count
MAX_LIVE_FAILS = 20


def find_test_projects(cwd, projects):
    """The test projects to run: the explicit .csproj files given (run-split hands each machine its
    own share), otherwise every .csproj under cwd that references a test SDK (build output skipped).
    A .sln, or nothing, means "discover"."""
    explicit = [p for p in (projects or []) if p.lower().endswith(".csproj")]
    if explicit:
        return [Path(p) for p in explicit]
    found = []
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(".csproj"):
                p = Path(root) / f
                if TEST_PROJECT.search(p.read_text(encoding="utf-8", errors="replace")):
                    found.append(p)
    return sorted(found, key=lambda p: p.name)


def clear_old_trx(results_dir):
    """A reused --results-dir must not let last run's trx stand in for a project that crashed now."""
    for f in all_trx(results_dir):
        os.remove(f)


def project_test_cmd(project, results_dir, test_filter=""):
    cmd = ["dotnet", "test", str(project), "--no-build"]
    if test_filter:
        cmd += ["--filter", test_filter]
    return cmd + ["--logger", f"trx;LogFileName={project.stem}.trx",
                  "--logger", "console;verbosity=normal",
                  "--results-directory", results_dir, "--nologo"]


def parse_console_line(line):
    """('passed'|'failed'|'skipped', test name) from a console-logger line, else None."""
    m = CONSOLE_RESULT.match(line or "")
    return (m.group(1).lower(), m.group(2)) if m else None


def short_names(names):
    """Drop the dotted prefix every name shares: Co.Domain.Tests -> Domain.Tests."""
    names = list(names)
    if len(names) < 2:
        return {n: n for n in names}
    parts = [n.split(".") for n in names]
    common = 0
    while all(len(p) > common + 1 and p[common] == parts[0][common] for p in parts):
        common += 1
    return {n: ".".join(p[common:]) for n, p in zip(names, parts)}


def all_trx(d):
    return sorted(glob.glob(os.path.join(d, "**", "*.trx"), recursive=True))


def _int(counters, key):
    return int(counters.get(key, 0)) if counters is not None else 0


def parse_trx(path):
    """Parse one .trx into counts, run-level outcome, run errors, and failures."""
    root = ET.parse(path).getroot()
    rs = root.find(".//t:ResultSummary", NS)
    counters = root.find(".//t:ResultSummary/t:Counters", NS)
    run_errors = []
    for ri in root.findall(".//t:RunInfo", NS):
        if (ri.get("outcome") or "") == "Error":
            txt = ri.find("t:Text", NS)
            line = txt.text.strip().splitlines()[0][:200] if (txt is not None and txt.text) else ""
            if XUNIT_FAIL_ECHO.search(line):
                continue  # xUnit's echo of a failing test: already counted in `failed`, not a run error
            run_errors.append(line or "test run reported an error")
    fails = []
    for r in root.findall(".//t:Results/t:UnitTestResult", NS):
        if (r.get("outcome") or "") != "Failed":
            continue
        name = r.get("testName", "?")
        msg = r.find(".//t:Output/t:ErrorInfo/t:Message", NS)
        first = msg.text.strip().splitlines()[0][:200] if (msg is not None and msg.text) else ""
        fails.append((name, first))
    return {
        "outcome": rs.get("outcome") if rs is not None else None,
        "total": _int(counters, "total"),
        "passed": _int(counters, "passed"),
        "failed": _int(counters, "failed"),
        "not_executed": _int(counters, "notExecuted"),
        "run_errors": run_errors,
        "fails": fails,
    }


def fmt_dotnet_progress(counts, short):
    """One short line from the live per-project counters — never the raw output."""
    parts = []
    for name, c in counts.items():
        parts.append(f"{short.get(name, name)} {c['passed'] + c['failed'] + c['skipped']}"
                     + (" done" if c["done"] else ""))
    failed = sum(c["failed"] for c in counts.values())
    return f"[dotnet-run] progress: {' | '.join(parts)} | failed {failed}"


def run_projects(projects, cwd, results_dir, test_filter="", progress=False, interval=30):
    """Run one `dotnet test` per project in parallel. With progress, a throttled
    counter line goes to stderr and each failing test is named the moment it fails.
    Returns (worst returncode, {project stem: stdout tail})."""
    short = short_names(p.stem for p in projects)
    counts = {p.stem: {"passed": 0, "failed": 0, "skipped": 0, "done": False} for p in projects}
    tails, lock = {}, threading.Lock()

    def emit(text):
        with lock:
            sys.stderr.write(text + "\n")
            sys.stderr.flush()

    def drive(project):
        proc = subprocess.Popen(project_test_cmd(project, results_dir, test_filter), cwd=cwd,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace")
        tail = []
        for line in proc.stdout:
            tail = (tail + [line.rstrip()])[-8:]
            hit = parse_console_line(line)
            if hit:
                with lock:
                    counts[project.stem][hit[0]] += 1
                if hit[0] == "failed" and progress:
                    with lock:
                        shown = sum(c["failed"] for c in counts.values())
                    # name the first failures live; past the cap the counter line carries the rest
                    if shown <= MAX_LIVE_FAILS:
                        emit(f"[dotnet-run] FAIL {short[project.stem]}: {hit[1][:160]}")
        proc.wait()
        counts[project.stem]["done"] = True
        tails[project.stem] = (proc.returncode, tail)

    threads = [threading.Thread(target=drive, args=(p,), daemon=True) for p in projects]
    for t in threads:
        t.start()
    last = time.monotonic()
    while any(t.is_alive() for t in threads):
        time.sleep(0.2)
        if progress and time.monotonic() - last >= interval:
            with lock:
                line = fmt_dotnet_progress(counts, short)
            emit(line)
            last = time.monotonic()
    for t in threads:
        t.join()
    worst = max((rc for rc, _ in tails.values()), default=1, key=abs)
    return worst, tails


def summarize(trx_paths, returncode, max_failures=15, expected=None, allow_empty=False):
    """Return (exit_code, summary_text) aggregated over every .trx produced.

    A run is a failure when the process exited non-zero, when any project's trx
    carries a RunInfo outcome="Error" (host crash / aborted run) or a
    ResultSummary outcome outside OK_OUTCOMES, when anything was notExecuted, or
    when any test failed. Counting only the newest trx — or only the `failed`
    counter — is exactly how a crashed multi-project run reported a false green.
    """
    parsed = [parse_trx(p) for p in trx_paths]
    stems = [Path(p).stem for p in trx_paths]
    missing = [e for e in (expected or []) if e not in stems]
    short = short_names(stems + missing)
    total = sum(p["total"] for p in parsed)
    passed = sum(p["passed"] for p in parsed)
    failed = sum(p["failed"] for p in parsed)
    not_executed = sum(p["not_executed"] for p in parsed)
    fails = [f for p in parsed for f in p["fails"]]
    run_errors = [e for p in parsed for e in p["run_errors"]]
    bad_outcomes = sorted({p["outcome"] for p in parsed if p["outcome"] not in OK_OUTCOMES})

    reasons = []
    if not parsed:
        reasons.append("no .trx parsed")
    if returncode != 0:
        reasons.append(f"dotnet exited {returncode}")
    for m in missing:
        reasons.append(f"no .trx for {short[m]}")
    if run_errors:
        reasons.append(f"test run error: {run_errors[0]}")
    if bad_outcomes:
        reasons.append("run outcome " + "/".join(bad_outcomes))
    if parsed and total == 0 and not allow_empty:   # run-split: a share may match nothing; its merge checks the whole
        reasons.append("no tests ran (did the filter match nothing?)")
    if failed:
        reasons.append(f"{failed} failed")
    # NOTE: notExecuted is NOT a failure on its own — VSTest records an intentional
    # skip ([Fact(Skip=…)], [Ignore]) as notExecuted; a real abort already trips the
    # RunInfo outcome="Error" and non-zero-exit gates above. It is shown, not gated.

    out = ["# dotnet-run summary", "",
           f"- total: {total} | passed: {passed} | **failed: {failed}**"
           + (f" | notExecuted: {not_executed}" if not_executed else ""),
           "- per project: " + " | ".join(
               f"{short[s]} {p['total']}" + (" CRASHED" if p["run_errors"] else "")
               for s, p in sorted(zip(stems, parsed))), ""]
    if reasons:
        out.append(f"**FAILED - {'; '.join(reasons)}**")
        out.append("")
    if fails:
        out.append("## Failures")
        for name, first in fails[:max_failures]:
            out.append(f"- **{name}**")
            if first:
                out.append(f"  - {first}")
        if len(fails) > max_failures:
            out.append(f"- ... and {len(fails) - max_failures} more")
        out.append("")
        out.append(f"trx files: {len(trx_paths)}")
    elif not reasons:
        out.append("All tests passed.")
    return (1 if reasons else 0), "\n".join(out)


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cwd", default=".", help="solution or project directory")
    ap.add_argument("--project", action="append", default=[],
                    help="a .sln, or a test .csproj; repeat for several (run-split gives each machine its share)")
    ap.add_argument("--filter", default="", help="dotnet test --filter expression (focused testing)")
    ap.add_argument("--max-failures", type=int, default=15)
    ap.add_argument("--progress", action="store_true", help="emit a periodic progress line to stderr")
    ap.add_argument("--progress-interval", type=int, default=30, help="seconds between progress lines")
    ap.add_argument("--results-dir", default="", help="keep the per-project .trx files here (evidence)")
    ap.add_argument("--allow-empty", action="store_true", help="a filter matching nothing in THIS share is not a failure (run-split)")
    return ap


def main() -> int:
    args = build_parser().parse_args()

    cwd = os.path.abspath(args.cwd)
    results_dir = os.path.abspath(args.results_dir) if args.results_dir else tempfile.mkdtemp(prefix="harness-trx-")
    os.makedirs(results_dir, exist_ok=True)
    clear_old_trx(results_dir)
    projects = find_test_projects(cwd, args.project)
    if not projects:
        print("# dotnet-run summary\n\n**FAILED - no test project found** (nothing references Microsoft.NET.Test.Sdk)")
        return 1

    # Build once, then the parallel per-project runs share it (--no-build): the given .sln, or each
    # given .csproj (its references come with it), or whatever `dotnet build` finds in cwd.
    targets = [[p] for p in args.project] if args.project else [[]]
    for t in targets:
        build = ["dotnet", "build"] + t + ["--nologo", "-v", "quiet"]
        sys.stderr.write(f"[dotnet-run] {' '.join(build)}  (cwd={cwd})\n")
        b = subprocess.run(build, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if b.returncode != 0:
            tail = "\n".join(l for l in (b.stdout + b.stderr).strip().splitlines() if "error" in l.lower())
            print("# dotnet-run summary\n\n**FAILED - build failed**\n")
            print("First error lines:\n```\n" + "\n".join(tail.splitlines()[:8]) + "\n```")
            return 1

    sys.stderr.write(f"[dotnet-run] {len(projects)} test project(s) in parallel: "
                     + ", ".join(short_names(p.stem for p in projects).values()) + "\n")
    returncode, tails = run_projects(projects, cwd, results_dir, args.filter,
                                     args.progress, args.progress_interval)

    if not all_trx(results_dir):
        # every project died before writing a trx — surface a short reason
        rc, tail = next(iter(tails.values()), (1, []))
        print("# dotnet-run summary\n\nNo .trx produced - the test hosts did not start.\n")
        if tail:
            print("Last output lines:\n```\n" + "\n".join(tail) + "\n```")
        return 1

    code, text = summarize(all_trx(results_dir), returncode, args.max_failures,
                           expected=[p.stem for p in projects], allow_empty=args.allow_empty)
    print(text)
    print(f"trx dir: {results_dir}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""Run a pytest suite on the machine and print only a fixed-size summary.

The third token-noisy suite, after Playwright and .NET. A large project's raw
`-q` output is a wall of dots and its failures carry full assertion diffs; none of
that belongs in the agent's context. This prints counts and, per failure, the test
id and the first meaningful assertion line. A failure being fixed is then opened
deliberately, by name.

  python pytest-run.py [--cwd <dir>] [<pytest args...>]
  python pytest-run.py --cwd path/to/project tests/test_example.py
  python pytest-run.py --cwd path/to/project -k "unit or integration"

What it does:

1. Runs pytest with a JUnit XML report; nothing of the raw output is shown.
2. Re-runs the failures **once, by node id**, so a test that passes the second
   time is reported as **flaky** rather than as a defect. Python suites flake for
   their own reasons - a clock, a temp directory, a stale `__pycache__` - and
   telling a flake from a defect is the point of running twice.
3. Prints a summary that does not grow with the suite.
4. With Ollama up, appends a short triage; `--no-llm` skips it.

Exit code 1 when anything still fails after the re-run, else 0.
"""
import argparse
import json
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

LLM_TIMEOUT_S = 90
#: an assertion diff can run for pages; only the first lines say what happened
FIRST_LINES = 3


def run_pytest(cwd, args, report, only=None):
    cmd = [sys.executable, "-m", "pytest", "-q", "--no-header",
           "-p", "no:cacheprovider", "--junit-xml=" + str(report)]
    cmd += only if only else args
    sys.stderr.write("[pytest-run] " + " ".join(cmd[2:]) + "  (cwd=" + str(cwd) + ")\n")
    proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.DEVNULL,
                          stderr=subprocess.PIPE, text=True)
    if not report.exists() and proc.stderr:
        sys.stderr.write(proc.stderr[-800:])
    return proc.returncode


def parse(report):
    """Returns (counts, [(node id, first lines of the failure)])."""
    root = ET.parse(report).getroot()
    suite = root.find("testsuite") if root.tag == "testsuites" else root
    counts = {}
    for key in ("tests", "failures", "errors", "skipped"):
        counts[key] = int(suite.get(key, 0) or 0)
    fails = []
    for case in suite.iter("testcase"):
        bad = case.find("failure")
        if bad is None:
            bad = case.find("error")
        if bad is None:
            continue
        node = (case.get("classname") or "") + "::" + (case.get("name") or "")
        text = (bad.get("message") or "") + "\n" + (bad.text or "")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        keep = [ln for ln in lines if ln.startswith(("E ", "assert", "Assertion", ">"))]
        if not keep:
            keep = lines
        fails.append((node, " | ".join(keep[:FIRST_LINES])[:400]))
    return counts, fails


def node_ids(cwd, fails):
    """JUnit classnames are dotted module paths; pytest wants a file path."""
    out = []
    for node, _ in fails:
        cls, _, name = node.partition("::")
        candidate = Path(*cls.split(".")).with_suffix(".py")
        if (cwd / candidate).exists():
            out.append(candidate.as_posix() + "::" + name)
        else:
            out.append(name)
    return out


def ollama_triage(host, model, summary):
    try:
        with urllib.request.urlopen(host + "/api/version", timeout=3):
            pass
    except Exception:
        return None
    prompt = ("You are triaging a Python pytest run for an engineer. Below is the run "
              "summary. In at most 6 short lines, English, plain text: group the failures "
              "by likely single cause (same fixture, same module, same assertion), say "
              "which look like a test-side problem versus a code problem, and name the one "
              "to open first. Do not repeat the summary.\n\n" + summary)
    body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0.1}}).encode("utf-8")
    req = urllib.request.Request(host + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_S) as response:
            text = json.loads(response.read().decode("utf-8")).get("response", "").strip()
    except Exception as exc:    # the summary is the deliverable; triage is a bonus
        return "(triage unavailable: " + str(exc) + ")"
    return "\n## local triage\n\n" + text if text else None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cwd", default=".")
    ap.add_argument("--model", default="qwen2.5:7b")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--max-failures", type=int, default=15)
    ap.add_argument("args", nargs=argparse.REMAINDER, help="passed to pytest")
    a = ap.parse_args()

    cwd = Path(a.cwd).resolve()
    if not cwd.exists():
        print("[pytest-run] no such directory: " + str(cwd))
        return 2
    args = [x for x in a.args if x != "--"]
    for x in args:
        if x.startswith("--junit"):
            print("[pytest-run] do not pass --junit-xml; that report is what this reads")
            return 2

    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.xml"
        code = run_pytest(cwd, args, report)
        if not report.exists():
            print("# pytest-run summary\n\nNo report produced - collection likely failed.")
            return code or 1
        counts, fails = parse(report)

        flaky = []
        still = list(fails)
        if fails:
            again = Path(tmp) / "again.xml"
            run_pytest(cwd, args, again, only=node_ids(cwd, fails))
            if again.exists():
                _, second = parse(again)
                bad = set(n for n, _ in second)
                flaky = [n for n, _ in fails if n not in bad]
                still = [(n, m) for n, m in fails if n in bad]

        out = ["# pytest-run summary", "",
               "- tests: " + str(counts["tests"]) + " - **failed: " + str(len(still))
               + "** - flaky: " + str(len(flaky)) + " - skipped: " + str(counts["skipped"]),
               ""]
        if still:
            out.append("## Failures")
            for node, msg in still[:a.max_failures]:
                out.append("- **" + node + "**")
                if msg:
                    out.append("  - " + msg)
            if len(still) > a.max_failures:
                out.append("- ... and " + str(len(still) - a.max_failures) + " more")
        if flaky:
            out.append("\n## Flaky (passed on the re-run)")
            for n in flaky:
                out.append("- " + n)
        if not still and not flaky:
            out.append("All tests passed.")
        summary = "\n".join(out)
        print(summary)
        if still and not a.no_llm:
            triage = ollama_triage(a.host, a.model, summary)
            if triage:
                print(triage)
        return 1 if still else 0


if __name__ == "__main__":
    sys.exit(main())

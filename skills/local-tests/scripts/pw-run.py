"""
pw-run.py — run a Playwright suite locally and print a fixed-size summary.

Claude supervises; the machine runs. The suite runs with the JSON reporter, the
failures are re-run once (a test that passes the second time is reported as a
flake, not a defect), and what reaches the context is a summary that does not
grow with the suite: counts, and per failure the test, its line, the expected/
received pair and the first line of the error. With Ollama up, a short local
triage is appended; without it the summary stands on its own.

  python pw-run.py [--cwd <angular dir>] [--no-llm] [--no-rerun] [--model qwen2.5:7b]
                   [--max-failures 12] <playwright test args…>

  python pw-run.py return-to --project=desktop
  python pw-run.py --cwd <projects>/x/angular return-to preview exam-form
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")
NOISE = re.compile(r"^\[WebServer\]|^\s*$")
LLM_TIMEOUT_S = 120
MAX_ERROR_LINES = 3


def run_playwright(cwd: Path, args: list[str], report: Path) -> int:
    env = {**os.environ, "PLAYWRIGHT_JSON_OUTPUT_NAME": str(report), "FORCE_COLOR": "0"}
    cmd = ["npx", "playwright", "test", *args, "--reporter=json"]
    proc = subprocess.run(cmd, cwd=cwd, env=env, shell=(os.name == "nt"), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not report.exists():
        # The runner died before writing a report: a config error, a missing spec
        # name, a dev server that never came up. Show the tail, nothing else.
        tail = [ANSI.sub("", l) for l in (proc.stdout + proc.stderr).splitlines() if not NOISE.match(l)]
        print("[pw-run] no report written; runner output tail:")
        print("\n".join(tail[-15:]))
    return proc.returncode


def walk(suite: dict, prefix: str = ""):
    """Yields (title, file, line, spec, result) for every test result in a suite tree."""
    name = f"{prefix} > {suite['title']}" if prefix and suite.get("title") else (suite.get("title") or prefix)
    for spec in suite.get("specs", []):
        for test in spec.get("tests", []):
            for result in test.get("results", []):
                yield f"{name} > {spec['title']}", spec.get("file", ""), spec.get("line", 0), test, result
    for child in suite.get("suites", []):
        yield from walk(child, name)


def read_report(report: Path):
    data = json.loads(report.read_text(encoding="utf-8"))
    rows = []
    for title, file, line, test, result in walk({"suites": data.get("suites", []), "title": ""}):
        rows.append({
            "title": title.strip(" >"),
            "file": file,
            "line": line,
            "project": test.get("projectName", ""),
            "status": result.get("status"),
            "expected": test.get("expectedStatus", "passed"),
            "errors": [ANSI.sub("", e.get("message", "")) for e in result.get("errors", [])],
            "attachments": [a.get("path", "") for a in result.get("attachments", []) if a.get("path")],
        })
    return rows, data.get("stats", {})


def failed(rows):
    return [r for r in rows if r["status"] not in ("passed", "skipped") and r["status"] != r["expected"]]


def key(r):
    return (r["file"], r["line"], r["project"])


def first_lines(message: str, n: int = MAX_ERROR_LINES) -> list[str]:
    lines = [l.strip() for l in message.splitlines() if l.strip()]
    wanted = [l for l in lines if re.match(r"^(Error|Expected|Received|Timeout|Locator|Call log|TypeError|ReferenceError)", l)]
    return (wanted or lines)[:n]


def summarize(rows, stats, reran: dict | None, max_failures: int) -> str:
    fails = failed(rows)
    still = [r for r in fails if reran is None or reran.get(key(r)) not in ("passed",)]
    flakes = [r for r in fails if reran is not None and reran.get(key(r)) == "passed"]
    passed = sum(1 for r in rows if r["status"] == "passed")
    skipped = sum(1 for r in rows if r["status"] == "skipped")
    # ASCII only: the Windows console renders anything else as '?'.
    out = [f"[pw-run] passed {passed} | failed {len(still)} | flaky {len(flakes)} | skipped {skipped} | {round(stats.get('duration', 0) / 1000)}s"]
    for r in flakes:
        out.append(f"  FLAKY {r['file']}:{r['line']} [{r['project']}] {r['title']}")
    for r in still[:max_failures]:
        out.append(f"  FAIL  {r['file']}:{r['line']} [{r['project']}] {r['title']}")
        for e in r["errors"][:1]:
            for l in first_lines(e):
                out.append(f"      {l[:220]}")
        shots = [a for a in r["attachments"] if a.endswith(".png")]
        if shots:
            out.append(f"      screenshot: {shots[0]}")
    if len(still) > max_failures:
        out.append(f"  ... and {len(still) - max_failures} more failures")
    return "\n".join(out)


def ollama_triage(host: str, model: str, summary: str) -> str | None:
    try:
        with urllib.request.urlopen(f"{host}/api/version", timeout=3):
            pass
    except Exception:
        return None
    prompt = (
        "You are triaging a Playwright end-to-end run for an engineer. Below is the run summary. "
        "In at most 6 short lines, English, plain text: group the failures by likely single cause "
        "(same locator, same URL, same stub), say which look like a test-side problem (regex, locator, timing) "
        "versus an application problem, and name the one failure to open first. Do not repeat the summary.\n\n"
        + summary
    )
    body = json.dumps({"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}).encode("utf-8")
    req = urllib.request.Request(f"{host}/api/generate", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_S) as r:
            text = json.loads(r.read().decode("utf-8")).get("response", "").strip()
    except Exception as e:  # the summary is the deliverable; triage is a bonus
        return f"[pw-run] triage skipped ({e})"
    lines = [l for l in text.splitlines() if l.strip()][:6]
    return "[triage · " + model + "]\n" + "\n".join("  " + l.strip() for l in lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cwd", default=".", help="the Playwright project directory (where playwright.config lives)")
    ap.add_argument("--no-llm", action="store_true", help="skip the local-model triage")
    ap.add_argument("--no-rerun", action="store_true", help="do not re-run failures once")
    ap.add_argument("--model", default="qwen2.5:7b")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--max-failures", type=int, default=12)
    ap.add_argument("args", nargs=argparse.REMAINDER, help="passed to `npx playwright test`")
    a = ap.parse_args()
    cwd = Path(a.cwd).resolve()
    if not cwd.exists():
        print(f"[pw-run] no such directory: {cwd}")
        return 2
    # `--` from the caller separating our flags from Playwright's
    args = [x for x in a.args if x != "--"]
    if any(x.startswith("--reporter") for x in args):
        print("[pw-run] do not pass --reporter; the JSON reporter is what this script reads")
        return 2

    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        code = run_playwright(cwd, args, report)
        if not report.exists():
            return code or 1
        rows, stats = read_report(report)
        fails = failed(rows)

        reran = None
        if fails and not a.no_rerun:
            rerun_report = Path(tmp) / "rerun.json"
            run_playwright(cwd, [*args, "--last-failed"], rerun_report)
            if rerun_report.exists():
                again, _ = read_report(rerun_report)
                reran = {key(r): r["status"] for r in again}

        summary = summarize(rows, stats, reran, a.max_failures)
        print(summary)
        still = [r for r in fails if reran is None or reran.get(key(r)) != "passed"]
        if still and not a.no_llm:
            triage = ollama_triage(a.host, a.model, summary)
            if triage:
                print(triage)
        return 1 if still else 0


if __name__ == "__main__":
    sys.exit(main())

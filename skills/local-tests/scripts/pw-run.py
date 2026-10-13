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
  python pw-run.py --cwd D:/Projects/x/angular return-to preview exam-form
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")
NOISE = re.compile(r"^\[WebServer\]|^\s*$")
#: the `line` reporter prints a running "[k/n] <title>" counter we throttle on
LINE_COUNTER = re.compile(r"\[(\d+)/(\d+)\]")
LLM_TIMEOUT_S = 120
MAX_ERROR_LINES = 3


def parse_counter(line: str):
    """Pull (done, total) from a Playwright `line` reporter row, or None."""
    m = LINE_COUNTER.search(line)
    return (int(m.group(1)), int(m.group(2))) if m else None


def playwright_invocation(args: list[str], report: Path, progress: bool = False, html_dir: Path | None = None):
    """The `npx playwright test` command and environment for one run.

    Our --reporter replaces the config's reporters, so the HTML report exists only
    when html_dir asks for it. With progress, the `line` reporter feeds the "[k/n]"
    tick; the json reporter always writes the file the summary reads."""
    env = {**os.environ, "PLAYWRIGHT_JSON_OUTPUT_NAME": str(report), "FORCE_COLOR": "0"}
    reporters = (["line"] if progress else []) + ["json"]
    if html_dir is not None:
        reporters.append("html")
        env["PLAYWRIGHT_HTML_OUTPUT_DIR"] = str(html_dir)
        env["PLAYWRIGHT_HTML_OPEN"] = "never"
    return ["npx", "playwright", "test", *args, f"--reporter={','.join(reporters)}"], env


def copy_artifacts(cwd: Path, dest: Path) -> int:
    """Copy test-results/ (traces, screenshots, error context) to dest. Returns 1 if
    copied, 0 if the run left none. Called before the failure re-run, which wipes it."""
    src = Path(cwd) / "test-results"
    if not src.is_dir():
        return 0
    shutil.copytree(src, Path(dest) / "test-results", dirs_exist_ok=True)
    return 1


def run_playwright(cwd: Path, args: list[str], report: Path, progress: bool = False, interval: int = 30,
                   html_dir: Path | None = None) -> int:
    cmd, env = playwright_invocation(args, report, progress, html_dir)
    if not progress:
        proc = subprocess.run(cmd, cwd=cwd, env=env, shell=(os.name == "nt"), capture_output=True, text=True, encoding="utf-8", errors="replace")
        out, rc = proc.stdout + proc.stderr, proc.returncode
    else:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, shell=(os.name == "nt"), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        lines, last, latest = [], time.monotonic(), None
        for line in proc.stdout:
            lines.append(line)
            c = parse_counter(line)
            if c:
                latest = c
            if latest and time.monotonic() - last >= interval:
                sys.stderr.write(f"[pw-run] progress: {latest[0]}/{latest[1]} tests\n")
                sys.stderr.flush()
                last = time.monotonic()
        proc.wait()
        out, rc = "".join(lines), proc.returncode
    if not report.exists():
        # The runner died before writing a report: a config error, a missing spec
        # name, a dev server that never came up. Show the tail, nothing else.
        tail = [ANSI.sub("", l) for l in out.splitlines() if not NOISE.match(l)]
        print("[pw-run] no report written; runner output tail:")
        print("\n".join(tail[-15:]))
    return rc


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
    # Top-level errors are global failures (webServer never came up, config error)
    # that leave specs un-run — a report can parse to zero rows and still be a bust.
    return rows, data.get("stats", {}), data.get("errors", []) or []


def verdict(rows, errors, still_failures):
    """Return (exit_code, reason|None). A green verdict needs tests that actually ran."""
    if errors:
        e = errors[0]
        first = (e.get("message") or e.get("value") or "") if isinstance(e, dict) else str(e)
        line = ANSI.sub("", first).strip().splitlines()[0][:200] if first else "global runner error"
        return 1, "runner error: " + line
    if not rows:
        return 1, "no tests were run"
    if still_failures:
        return 1, f"{len(still_failures)} failed"
    return 0, None


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


def parse_cli(argv):
    """(our options, Playwright's args in their original order).

    parse_known_args, not REMAINDER: a REMAINDER positional rejected "--project=…" unless a spec
    path came first. Anything we do not know passes through untouched; a `--` separator is
    accepted and dropped. allow_abbrev=False so a Playwright option is never read as a prefix of
    ours. (`--max-failures` is ours — the summary cap — not Playwright's stop-after-N.)"""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 allow_abbrev=False)
    ap.add_argument("--cwd", default=".", help="the Playwright project directory (where playwright.config lives)")
    ap.add_argument("--no-llm", action="store_true", help="skip the local-model triage")
    ap.add_argument("--no-rerun", action="store_true", help="do not re-run failures once")
    ap.add_argument("--model", default="qwen2.5:7b")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--max-failures", type=int, default=12)
    ap.add_argument("--progress", action="store_true", help="emit a periodic progress line to stderr")
    ap.add_argument("--progress-interval", type=int, default=30, help="seconds between progress lines")
    ap.add_argument("--html-report", default="", help="also write the HTML report to this directory (evidence)")
    ap.add_argument("--artifacts-dir", default="", help="copy test-results/ (traces, screenshots) here before any re-run")
    a, rest = ap.parse_known_args(argv)
    return a, [x for x in rest if x != "--"]


def main() -> int:
    a, args = parse_cli(sys.argv[1:])
    cwd = Path(a.cwd).resolve()
    if not cwd.exists():
        print(f"[pw-run] no such directory: {cwd}")
        return 2
    if any(x.startswith("--reporter") for x in args):
        print("[pw-run] do not pass --reporter; the JSON reporter is what this script reads")
        return 2

    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        html_dir = Path(a.html_report).resolve() if a.html_report else None
        code = run_playwright(cwd, args, report, a.progress, a.progress_interval, html_dir)
        if a.artifacts_dir:
            copy_artifacts(cwd, Path(a.artifacts_dir))
        if not report.exists():
            return code or 1
        rows, stats, errors = read_report(report)
        fails = failed(rows)

        reran = None
        if fails and not a.no_rerun:
            rerun_report = Path(tmp) / "rerun.json"
            run_playwright(cwd, [*args, "--last-failed"], rerun_report)
            if rerun_report.exists():
                again, _, _ = read_report(rerun_report)
                reran = {key(r): r["status"] for r in again}

        summary = summarize(rows, stats, reran, a.max_failures)
        print(summary)
        still = [r for r in fails if reran is None or reran.get(key(r)) != "passed"]
        exit_code, reason = verdict(rows, errors, still)
        if reason and not still:  # infra/no-tests cases the counts line would hide
            print("[pw-run] FAILED - " + reason)
        if still and not a.no_llm:
            triage = ollama_triage(a.host, a.model, summary)
            if triage:
                print(triage)
        return exit_code


if __name__ == "__main__":
    sys.exit(main())

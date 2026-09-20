#!/usr/bin/env python
"""Run a .NET test suite on the machine and print only a fixed-size summary.

Same idea as pw-run.py for the other token-noisy suite: dotnet test output (and
its stack traces) never enters Claude's context — only counts and, per failure,
the test name and first error line. Zero-config: from a solution/project dir,
`python dotnet-run.py` just works; pass a --filter to scope (focused testing).

  python dotnet-run.py [--cwd <dir>] [--project <path>] [--filter <expr>]
  python dotnet-run.py --cwd <projects>/x --filter "FullyQualifiedName~MyFeature"
"""
import argparse
import glob
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


def find_trx(d):
    files = glob.glob(os.path.join(d, "**", "*.trx"), recursive=True)
    return max(files, key=os.path.getmtime) if files else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cwd", default=".", help="solution or project directory")
    ap.add_argument("--project", default="", help="a specific .csproj/.sln (optional)")
    ap.add_argument("--filter", default="", help="dotnet test --filter expression (focused testing)")
    ap.add_argument("--max-failures", type=int, default=15)
    args = ap.parse_args()

    cwd = os.path.abspath(args.cwd)
    results_dir = tempfile.mkdtemp(prefix="harness-trx-")
    cmd = ["dotnet", "test"]
    if args.project:
        cmd.append(args.project)
    if args.filter:
        cmd += ["--filter", args.filter]
    cmd += ["--logger", f"trx;LogFileName=results.trx", "--results-directory", results_dir,
            "--nologo", "-v", "quiet"]

    sys.stderr.write(f"[dotnet-run] {' '.join(cmd)}  (cwd={cwd})\n")
    # Run; discard stdout/stderr — the .trx is the source of truth.
    proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

    trx = find_trx(results_dir)
    if not trx:
        # build/restore failure before any test ran — surface a short reason
        tail = "\n".join((proc.stderr or "").strip().splitlines()[-8:])
        print("# dotnet-run summary\n\nNo .trx produced — build/restore likely failed.\n")
        if tail:
            print("First error lines:\n```\n" + tail + "\n```")
        return 1

    ns = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
    tree = ET.parse(trx); root = tree.getroot()
    counters = root.find(".//t:ResultSummary/t:Counters", ns)
    total = int(counters.get("total", 0)) if counters is not None else 0
    passed = int(counters.get("passed", 0)) if counters is not None else 0
    failed = int(counters.get("failed", 0)) if counters is not None else 0

    fails = []
    for r in root.findall(".//t:Results/t:UnitTestResult", ns):
        if (r.get("outcome") or "") != "Failed":
            continue
        name = r.get("testName", "?")
        msg = r.find(".//t:Output/t:ErrorInfo/t:Message", ns)
        first = ""
        if msg is not None and msg.text:
            first = msg.text.strip().splitlines()[0][:200]
        fails.append((name, first))

    out = ["# dotnet-run summary", "",
           f"- total: {total} · passed: {passed} · **failed: {failed}**", ""]
    if fails:
        out.append("## Failures")
        for name, first in fails[:args.max_failures]:
            out.append(f"- **{name}**")
            if first:
                out.append(f"  - {first}")
        if len(fails) > args.max_failures:
            out.append(f"- … and {len(fails) - args.max_failures} more")
        out.append("")
        out.append(f"Full .trx: {trx}")
    else:
        out.append("All tests passed.")
    print("\n".join(out))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

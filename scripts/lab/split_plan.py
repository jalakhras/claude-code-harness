#!/usr/bin/env python3
"""Split heavy suites across this machine ("local") and lab-worker1 ("worker"), and merge the two
halves' results into one verdict. Pure logic, called by run-split.ps1; the runners do the running.

  split_plan.py plan  --mode byType|byProject --projects p1,p2,... [--dotnet-on local|worker]
                      [--shards-total N] [--local-shards 1,2] [--heavy-on local|worker]
  split_plan.py merge <parts.json> [--expected-projects A.Tests,B.Tests]

Modes:
  byType     one suite per machine: .NET whole on --dotnet-on, Playwright whole on the other.
  byProject  .NET projects split into two bins by weight (largest first into the lighter bin), and
             Playwright sharded --shard=k/N: --local-shards here, the rest on the worker.
"""
import argparse
import json
import re
import sys
from pathlib import Path

#: rough seconds per project, from the 2026-10-11 worker run (EFCore 1197 tests ~4 min, the rest ~30 s);
#: only the ORDER matters for the greedy split
WEIGHTS = [("EntityFrameworkCore", 240), ("TestBase", 0)]
DEFAULT_WEIGHT = 30
SIDES = ("local", "worker")


def weight(project: str) -> int:
    for needle, w in WEIGHTS:
        if needle in project:
            return w
    return DEFAULT_WEIGHT


def split_by_weight(projects):
    """Two bins of roughly equal total weight: heaviest first, each into the lighter bin."""
    bins, totals = ([], []), [0, 0]
    for p in sorted(projects, key=lambda x: (-weight(x), x)):
        i = 0 if totals[0] <= totals[1] else 1
        bins[i].append(p)
        totals[i] += weight(p)
    heavy, light = (bins[0], bins[1]) if totals[0] >= totals[1] else (bins[1], bins[0])
    return sorted(heavy), sorted(light)


def plan(mode, projects, dotnet_on="local", shards_total=2, local_shards=(1,), heavy_on="worker"):
    projects = list(projects)
    if mode == "byType":
        other = "worker" if dotnet_on == "local" else "local"
        return {dotnet_on: {"dotnet": projects, "playwright": []},
                other: {"dotnet": [], "playwright": [None]}}
    if mode != "byProject":
        raise ValueError(f"unknown mode {mode!r}")
    local_shards = list(local_shards)
    if (len(set(local_shards)) != len(local_shards) or not local_shards
            or any(not 1 <= s <= shards_total for s in local_shards) or len(local_shards) >= shards_total):
        raise ValueError(f"local shards {local_shards} must be distinct, within 1..{shards_total}, "
                         "and leave at least one shard for the worker")
    heavy, light = split_by_weight(projects)
    light_on = "local" if heavy_on == "worker" else "worker"
    shard = lambda ks: [f"{k}/{shards_total}" for k in ks]
    worker_shards = [k for k in range(1, shards_total + 1) if k not in local_shards]
    out = {heavy_on: {"dotnet": heavy}, light_on: {"dotnet": light}}
    out["local"]["playwright"] = shard(sorted(local_shards))
    out["worker"]["playwright"] = shard(worker_shards)
    return out


TOTAL = re.compile(r"- total: (\d+) \| passed: (\d+) \| \*\*failed: (\d+)\*\*")
PER_PROJECT = re.compile(r"^- per project: (.+)$", re.M)
PW = re.compile(r"\[pw-run\] passed (\d+) \| failed (\d+) \| flaky (\d+) \| skipped (\d+)")
GATE = re.compile(r"(fingerprint MATCH \w+|FINGERPRINT MISMATCH[^,]*|NOT A GATE[^,]*?\))")


def parse_part(text: str) -> dict:
    """Counts and the gate verdict from one part's runner output (several runs may be concatenated)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")   # the halves' logs come from Windows processes
    r = {"dotnet_total": 0, "dotnet_failed": 0, "projects": {}, "pw_passed": 0, "pw_failed": 0,
         "pw_flaky": 0, "pw_skipped": 0, "gate": None}
    for m in TOTAL.finditer(text):
        r["dotnet_total"] += int(m.group(1)); r["dotnet_failed"] += int(m.group(3))
    for m in PER_PROJECT.finditer(text):
        for item in m.group(1).split(" | "):
            name, _, n = item.replace(" CRASHED", "").rpartition(" ")
            if n.isdigit():
                r["projects"][name] = r["projects"].get(name, 0) + int(n)
    for m in PW.finditer(text):
        r["pw_passed"] += int(m.group(1)); r["pw_failed"] += int(m.group(2))
        r["pw_flaky"] += int(m.group(3)); r["pw_skipped"] += int(m.group(4))
    gates = GATE.findall(text)
    if gates:
        r["gate"] = next((g for g in gates if not g.startswith("fingerprint MATCH")), gates[-1])
    return r


def discover(repo: str, runners: str):
    """Test projects under repo, relative and '/'-separated, found by dotnet-run.py's own finder
    (one definition of "a test project", not a second copy here)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("dotnet_run", Path(runners) / "dotnet-run.py")
    dr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dr)
    return sorted(Path(p).resolve().relative_to(Path(repo).resolve()).as_posix()
                  for p in dr.find_test_projects(repo, []))


def canonical(name: str, expected) -> str:
    """Map a printed project name to its expected stem: the runner prints full names when it ran
    one project and names without the shared prefix when it ran several."""
    for e in expected or []:
        if e == name or e.endswith("." + name):
            return e
    return name


def merge(parts, expected_projects=None):
    """One verdict over both halves. Exit 1 when any part failed, a project was counted on both
    sides or by none; exit 4 when everything passed but a worker part was not a gate; else 0."""
    reasons = []
    seen = {}
    for p in parts:
        for name in p.get("projects", {}):
            seen.setdefault(canonical(name, expected_projects), []).append(p["side"])
    for name, sides in seen.items():
        if len(sides) > 1:
            reasons.append(f"{name} counted twice ({' + '.join(sides)})")
    for name in expected_projects or []:
        if name not in seen:
            reasons.append(f"{name} missing (ran on neither side)")
    # each share may match nothing (dotnet-run --allow-empty); the merged run may not
    if expected_projects and seen and sum(p.get("dotnet_total", 0) for p in parts) == 0:
        reasons.append("no .NET test ran on either side (did the filter match nothing?)")
    # a side that was planned Playwright steps must have run some (a step can exit 0 having run nothing)
    for p in parts:
        if p.get("pw_steps") and not (p.get("pw_passed", 0) + p.get("pw_failed", 0) + p.get("pw_skipped", 0)):
            reasons.append(f"Playwright ran no test on the {p['side']} side")
    failed = [p for p in parts if p["exit"] not in (0, 4)]
    for p in failed:
        reasons.append(f"{p['side']} part failed (exit {p['exit']})")
    def is_gate(p):
        g = str(p.get("gate") or "")
        if p["exit"] == 4 or g.startswith(("NOT A GATE", "FINGERPRINT MISMATCH")):
            return False
        return g.startswith("fingerprint MATCH") if p["side"] == "worker" else True
    not_gate = [p for p in parts if not is_gate(p)]
    code = 1 if reasons else (4 if not_gate else 0)
    return {
        "exit": code, "reasons": reasons,
        "dotnet_total": sum(p.get("dotnet_total", 0) for p in parts),
        "dotnet_failed": sum(p.get("dotnet_failed", 0) for p in parts),
        "pw_passed": sum(p.get("pw_passed", 0) for p in parts),
        "pw_failed": sum(p.get("pw_failed", 0) for p in parts),
        "pw_skipped": sum(p.get("pw_skipped", 0) for p in parts),
        "wall_seconds": max((p.get("seconds", 0) for p in parts), default=0),
        "sum_seconds": sum(p.get("seconds", 0) for p in parts),
        "not_gate": [p["side"] for p in not_gate],
    }


def format_merged(m, parts) -> str:
    # ASCII only: the Windows console renders anything else as '?'.
    lines = ["# run-split summary", ""]
    for p in parts:
        lines.append(f"- {p['side']}: exit {p['exit']} in {p.get('seconds', 0)}s | {p.get('gate') or 'no gate line'}"
                     + (f" | evidence {p['evidence']}" if p.get("evidence") else ""))
    lines.append(f"- .NET: {m['dotnet_total']} tests, {m['dotnet_failed']} failed"
                 + (" | per project: " + " | ".join(f"{k} {v}" for p in parts for k, v in sorted(p.get('projects', {}).items()))
                    if any(p.get("projects") for p in parts) else ""))
    lines.append(f"- Playwright: passed {m['pw_passed']} | failed {m['pw_failed']} | skipped {m['pw_skipped']}")
    lines.append(f"- wall clock {m['wall_seconds']}s (longest part) vs {m['sum_seconds']}s if run one after another")
    if m["reasons"]:
        lines.append(f"**FAILED - {'; '.join(m['reasons'])}**")
    elif m["exit"] == 4:
        lines.append(f"**PASSED BUT NOT A GATE - {', '.join(m['not_gate'])}**")
    else:
        lines.append("All parts passed.")
    return "\n".join(lines)


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--mode", required=True, choices=["byType", "byProject"])
    p.add_argument("--projects", required=True)
    p.add_argument("--dotnet-on", default="local", choices=SIDES)
    p.add_argument("--shards-total", type=int, default=2)
    p.add_argument("--local-shards", default="1")
    p.add_argument("--heavy-on", default="worker", choices=SIDES)
    d = sub.add_parser("discover")
    d.add_argument("--repo", required=True)
    d.add_argument("--runners", required=True)
    m = sub.add_parser("merge")
    m.add_argument("parts")
    m.add_argument("--expected-projects", default="")
    a = ap.parse_args(argv)
    if a.cmd == "discover":
        print("\n".join(discover(a.repo, a.runners)))
        return 0
    if a.cmd == "plan":
        projects = [x for x in a.projects.split(",") if x]
        try:
            out = plan(a.mode, projects, a.dotnet_on, a.shards_total,
                       [int(x) for x in a.local_shards.split(",") if x], a.heavy_on)
        except ValueError as e:
            print(f"[split] {e}", file=sys.stderr)
            return 2
        print(json.dumps(out))
        return 0
    parts = json.loads(Path(a.parts).read_text(encoding="utf-8-sig"))
    for part in parts:
        part.update({k: v for k, v in parse_part(part.get("text", "")).items() if k != "gate" or not part.get("gate")})
    merged = merge(parts, [x for x in a.expected_projects.split(",") if x])
    print(format_merged(merged, parts))
    return merged["exit"]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

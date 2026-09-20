---
name: security-lab
description: Run authorized penetration testing against the owner's own assets — scope check, recon, tooling, controlled attack, findings, fix, retest — for defensive hardening and learning. Owned assets only, per security-lab/scope.md. Use when jalakhras asks to test the security or resilience of a site/app/repo he owns, write an analysis tool, or attack his own target to measure its defenses.
metadata:
  origin: claude-harness
  lane: "4 — authorized offensive security (owned assets only)"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch
---

# security-lab

Offensive testing to make the owner's own systems stronger. This is legitimate,
authorized security work — pentesting his assets, writing analysis tooling,
attacking his own targets to measure resilience. It is **not** a licence for
generic offensive technique.

## Gate — before anything else | السياج (لا يُتجاوز)

1. **Name the target and confirm it is in `security-lab/scope.md`.** If it is not
   listed, **stop** and ask the owner to add it (ownership/authorization). No row,
   no test — no exceptions, whatever the stated reason.
2. **Prefer an isolated environment** — localhost/staging, not live production
   with real users, unless that row explicitly authorizes production.
3. **Refuse, always:** targets the owner does not own or is not authorized to test;
   mass or denial-of-service attacks; supply-chain compromise; malware; phishing
   against real people; detection evasion for malicious use. Refuse plainly and
   offer the nearest legitimate action.

If the gate does not pass, produce nothing offensive — a defensive `security-review`
of the code is the fallback.

## Workflow (once the gate passes)

### 1. Scope & rules of engagement
Restate: the exact target (from its scope row), what is in and out of bounds, the
environment, and what "done" means (e.g. "prove/refute auth bypass on the review
queue"). Small, testable objective — not "hack it".

### 2. Recon
Map the surface with read-only steps first: endpoints, inputs, auth flows, tech
stack, exposed config. Record what you see; do not change state yet.

### 3. Tooling
Use standard tools against the owned target (nmap, ffuf, sqlmap, Burp/ZAP,
custom scripts). Custom analysis scripts live in `security-lab/tools/`. Keep every
command reproducible and logged.

### 4. Controlled attack
Execute the specific test. Stay within the objective; do not pivot to a new target
or a destructive action the objective did not call for. Capture the exact request/
response that proves or refutes the finding.

### 5. Findings
For each: severity, the reproducing steps/payload, the impact, and the fix. Rank
most-severe first. A "we tried X and it held" is a finding worth recording too.

### 6. Fix & retest
Hand real vulnerabilities to `security-reviewer` / the relevant stack, apply the
fix, then **re-run the exact test** to confirm it is closed (the falsify discipline:
the exploit must now fail where it succeeded).

## Storage
- Tools/scripts → `security-lab/tools/`.
- Raw findings (payloads, captures) → `security-lab/findings/` — **git-excluded**;
  do not commit exploit detail or anything sensitive.
- The report (what was tested, result, fixes) → `<vault>\wiki\security\<target>.md`.

## Note
This complements, not replaces, `security-review` (defensive, pre-commit) and
`production-audit` (readiness). Offensive testing proves the defenses those
prescribe actually hold.

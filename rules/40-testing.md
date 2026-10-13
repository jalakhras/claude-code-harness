# Testing | الاختبار

## Two layers per decision | طبقتان لكل قرار

Every function that carries a decision has a **unit test** (the decision at its
bounds: input → output, no DB) **and an integration test** (that every caller
actually reads the decision through the DTO/guard). Write the decision as a domain
function that all sites call, so the unit test covers it and the integration test
covers that the sites call it. Logic that cannot be isolated (needs a query) is
covered by integration, with the reason for the missing unit test in a comment.
**Both layers run after each change** («بعد كل تعديل نشغّلهم»).

## Focused testing | الاختبار المركّز

Test **only the changed area and what it impacts** — the touched screen's specs
plus everything that imports the touched shared pieces (grep the importers) — to
save tokens, time, and effort. **Full suite** is reserved for changes to a shared
foundation (shell, pager, stubs, localization) or before a release/tag.

## Suites run locally; Claude supervises | الحِزم محلّيّاً وكلود مراقب

Playwright (and any long browser/UI suite) is **run through the local runner**,
not read raw («اطلب من المديول المحليه القيام بها لتوفير التوكن وانت تكون
المراقب», 2026-09-20):

```
python ~/.claude/skills/local-tests/scripts/pw-run.py <playwright args…>
```

It runs the suite with a JSON reporter, re-runs the failures once (so a flake is
named a flake, not a defect), and prints a **fixed-size summary** (counts, and per
failure: test, line, expected/received, first error line), with a short local-LLM
triage (Ollama) when it is up. **pytest suites go through `pytest-run.py`** and **.NET suites through `dotnet-run.py`** the same
way (JUnit XML / TRX logger → counts + per-failure name and first error line
only). Claude reads the summary, decides, and opens a screenshot, a trace, a
`.trx` or one test's own output **only** for a failure it is actually fixing.
Never pipe a full report, a screenshot per failure, or a `--debug` session into
the context. **This holds for a focused module as much as for a full suite** — a
pytest run of one file still carries every assertion diff it produces. The three
runners are zero-config (`--cwd` defaults to `.`). Writing tests, falsifying them
and fixing the code stay Claude's job; the local model edits nothing.

## Long suites run on the lab worker | الحِزم الطويلة على جهاز العامل

A second machine (`lab-worker1`) exists to cut the **wall-clock**, not to move every
test off this one. **Heavy suites are split across both machines in parallel** with
`scripts/lab/run-split.ps1`: `-Mode byType` (.NET here, Playwright there — the
default) or `-Mode byProject` (.NET projects and Playwright shards on both); one
merged verdict, wall ≈ the longer half. `scripts/lab/run-on-worker.ps1` alone puts a
whole suite on the worker (sync, fingerprint, evidence, same fixed-size summary).
**Focused** runs (one class, one spec) stay local — the round trip is not worth it.
**Falsification, review and builds for the change in hand stay on this machine**;
the worker carries suites, not the edit-test loop.

- **Probe first:** `ssh -o BatchMode=yes lab-worker1 true`. If the worker is down,
  **say so and run locally — do not wait for it.** The script does this fallback
  automatically (unreachable / sync failed / ssh 255 → local); a suite that *ran*
  on the worker and failed is reported, never silently re-run locally.
- **Do not edit files while a run is in flight on the worker** (a file changing
  mid-run wastes the run — the local `Discipline` rule, over the wire).
- **One run at a time on the worker:** another session's live run makes it *busy*
  (the scripts check and fall back); never start a second sync by hand under it.
- **Self-repair is fenced (a fenced self-repair permission):** on an *environment* failure
  the session may `ssh` in to fix it — restart/recreate the test SQL container,
  restart services, re-sync, clean temp/old test DBs, reinstall project toolchains
  (.NET/Node/Playwright) — and **nothing else**: no users, no SSH/network/firewall,
  no OS upgrade, nothing outside `~/lab` / `~/work`, and never print or store a
  password. **Two repair attempts at most**, then fall back to the main machine and
  record every worker action in the report (`05-guardrails` G11; `85-security`
  owned-asset fence). Full scope and traps: `scripts/lab/README.md`.

## Falsify every new test | تكذيب كل اختبار

Before reporting a fix, disable it and watch the guard **fail alone**, then
restore. A test that passes with the fault put back is worthless — add a control
assertion proving the guard is live. (Two tests once passed with the fault in.)

## Discipline | الانضباط

- **Do not start a full suite until every edit is finished** — a file changing
  mid-run wastes ~20 min; three runs were thrown away this way.
- Validation lives on **both layers, backend + UI, inside the project** (the
  framework's own guards), never a external script («ليس عن طريق سكربت خارجي»).
- Coverage target 80% for new logic.
- **A manual-test scenario per batch** (see `20-reporting.md`).

## The database is not just test data | القاعدة ليست بيانات اختبار فقط

Seeders are additive only; the host account is never touched; no deletes
(«هذه ليست قاعدة فقط بيانات للاختبارات انتبه»). Stack-specific test traps live in
`stacks/*` and the project rules.

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

## Browser suites run locally; Claude supervises | المتصفّح محلّيّاً وكلود مراقب

Playwright (and any long browser/UI suite) is **run through the local runner**,
not read raw («اطلب من المديول المحليه القيام بها لتوفير التوكن وانت تكون
المراقب», 2026-09-20):

```
python ~/.claude/skills/local-tests/scripts/pw-run.py <playwright args…>
```

It runs the suite with a JSON reporter, re-runs the failures once (so a flake is
named a flake, not a defect), and prints a **fixed-size summary** (counts, and per
failure: test, line, expected/received, first error line), with a short local-LLM
triage (Ollama) when it is up. **.NET suites go through `dotnet-run.py`** the same
way (TRX logger → counts + per-failure name/first-error only). Claude reads the
summary, decides, and opens a screenshot/trace/`.trx` only for a failure it is
actually fixing. Never pipe a full Playwright/dotnet report, a screenshot per
failure, or a `--debug` session into the context. Both runners are zero-config
(`--cwd` defaults to `.`). Writing and fixing tests stays Claude's job.

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

# Review & documentation | المراجعة والتوثيق

## After every batch of code | بعد كل كود

Match the review to what the batch touched (owner decision, 2026-10-03).
The two reviewers overlap; running both on every small batch doubles the tokens for
little gain, while dropping one everywhere loses what it alone catches in risky code.

| Batch touches | Run |
|---|---|
| copy, labels, docs, or tests only | `/code-review` |
| ordinary logic (UI or service) | `/code-review-expert` + `/code-review` |
| authentication, authorization/permissions, tokens/secrets, user input, security settings | both + `security-reviewer` |
| database queries, migrations, EF/ORM mappings (+ **data architecture**) | both + `database-reviewer` |
| backend modules/contexts, controllers, cross-context deps | + `arch-modules` |
| HTTP endpoints or their contracts | + `arch-api` |
| frontend components/services/routes/state/i18n | + `arch-frontend` |
| UI styling / tokens / a design-system component | + `design-conformance` |
| a query, endpoint, list/paging path, or a speed claim | + `perf-reviewer` |
| **any behaviour change** | + `ba-analyst` (before **and** after the code) |
| a batch with **screenshots** | + `ux-review` |

Fix what they find before reporting, and say in the report which reviews ran and why
(one line). The pair earns its place on real logic: it has caught a missing
tie-breaker, a range sentence that lied on an empty last page, and twelve docblocks
promising a memory that no longer existed («وبعد كل كود استخدم /code-review-expert و
/code-review», 2026-09 — now tiered as above).

For deeper passes use the trimmed agents: `csharp-reviewer`, `typescript-reviewer`,
`database-reviewer`, `security-reviewer`, plus `silent-failure-hunter` and
`click-path-audit` when handlers may cancel each other out.

## Architecture & judgement agents | وكلاء المعماريّة والحكم

Generic, **read-only** agents that know no project: each reads its rules from the
**active project's profile** (`projects/<name>.md` → a **## References** section) and,
if a reference is missing, **says so and stops — it never guesses**. `arch-modules`,
`arch-api`, `arch-frontend`, `design-conformance`, `perf-reviewer`, `ba-analyst`,
`ux-review` (data architecture lives inside `database-reviewer`). `arch-*` and
`design-*`/`perf` are for **references a machine can't check**; a rule a machine *can*
check becomes an **architecture test**, not an agent note.

- **Placement before code.** Every batch that adds files starts with the planner's
  **placement plan** (one row per new thing: what · where · why (reference line) ·
  does it already exist?). The agents whose parts it touches review the **plan before
  code** and the **diff after**; the plan goes in the report.
- **Triggers & parallel.** Each agent has a trigger table in its file and **runs only
  when the batch touches its part**; `ba-analyst` runs on every behaviour change,
  `ux-review` whenever there are screenshots. All the agents a batch needs run **in
  parallel, alongside `/code-review`**, so wall-time does not grow. Fixes stay inside
  the batch's scope; bigger moves go to the queue.
- **Cite or it's an opinion.** Every finding cites the **reference line** it breaks;
  a finding with no citation is reported separately as an opinion (a `design-conformance`
  or `ux-review` opinion is a **design suggestion for the owner**, never applied).
- **Baseline once.** When the references first exist, run every agent once over the
  whole codebase — a **report only**; its findings become queue items with severity,
  and design suggestions go to the owner as a list.

Keep `security-reviewer` and `perf-reviewer` as the always-available specialist lenses.

## Severity | مستويات الخطورة

| Level | Meaning | Action |
|---|---|---|
| CRITICAL | security/data-loss risk | BLOCK — fix before commit |
| HIGH | bug or significant quality issue | fix before commit |
| MEDIUM | maintainability (e.g. unexplained file over 800 lines) | consider |
| LOW | style | optional |

Address CRITICAL and HIGH; fix MEDIUM when possible.

## Mandatory security-review triggers | محفّزات المراجعة الأمنية

Stop and use `security-reviewer` when the change touches authentication/
authorization, user input, database queries, file operations, external API calls,
or cryptography. See `85-security.md`.

## Documentation | التوثيق

Update the relevant docs after every change («لا تنسى تحديث الوثائق»). For
long-lived projects, keep the four doc roles distinct (Constitution / Map / Status
/ History) so they do not rot. Record significant architectural choices as ADRs in
the vault (`D:\Brain\wiki\<project>\decisions.md`).

## Design work | التصميم

For any UI/design task, use the design skills and commands (`ui-ux-pro-max`,
`frontend-design`, `make-interfaces-feel-better`, `web-design-guidelines`,
`design-system`) — see `90-design.md` and `95-ui.md`.

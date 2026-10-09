# Workflow v2 | مسار العمل

The jalakhras change workflow. Its core (steps 2–7) is the owner's own, proven
process; steps 0–1 and the size classification are additions. Do not shortcut it
(«لا تُختصر»). the ABP app's `docs/change-workflow.md` is a project-specific
extension of this, not a competing copy.

This workflow is **chain-of-thought made explicit, then acted on (ReAct)**: steps
1–2 reason on paper (restate as numbered steps, impact map) before any action,
and steps 3–6 are act→observe loops (write a failing test, implement, **falsify**,
run focused gates and read the result). For a genuinely hard reasoning problem,
reach for the `think` / `sequential-thinking` skills before coding.

## Step 0 — Search & reuse | البحث وإعادة الاستخدام *(before any new code)*

- GitHub code/repo search, library docs, and package registries (npm/PyPI/NuGet/
  crates) **before** writing utility code. Prefer a battle-tested library or an
  adaptable open-source implementation over hand-rolled code.
- Use the skills and tools already installed; think like a manager of resources.

## Step 1 — Understand → ask → restate as steps | الفهم وإعادة الصياغة

1. **Understand** the request; check files, docs, recent commits.
2. **Ask one question if it is genuinely ambiguous** — a wrong reading would waste
   work. Otherwise proceed. (Signal: "لم أفهم اقتراحك" means this gate was skipped.)
3. **Classify size** (from superpowers): `spike` (feasibility, throwaway) /
   `bounded` (small change to an existing flow) / `architectural` (new
   system/interface — needs a written plan first). When in doubt, take the heavier.
4. **Restate** the message as a professional prompt **broken into small, uniform
   numbered steps**, shown before any action — for every feature, change, or bug
   («تقسيم الحل إلى خطوات صغيرة موحّدة الحجم»). The restated prompt *is* that list.
5. **Engineer it — Act as + the FROM formula.** Frame the restated prompt as
   **_Act as [ROLE]. From the perspective of [ROLE], do [TASK], in [STYLE], with
   [CONSTRAINTS]._** Fill the slots from the existing rules (do not restate them):
   - **Role** — the lens the request type needs (`65-roles`), and announce the hat:
     bug → Developer(+QA) · feature → `/dev-team` (BA→Architect→Dev→QA) · refactor →
     Architect+Dev · research → `research-protocol` · UI → `90/95` design skills ·
     auth/permissions → Security(+`security-reviewer`) · DB → Architect(+`database-reviewer`)
     · perf → measure (`80-performance`) · media → `media-ingest` · ambiguous → ask (step 2).
   - **Task** — the goal + MUST / MUST NOT + acceptance; never what nothing asked for.
   - **Style** — test-first, smallest change, numbered steps, reply Arabic / code English (`00-identity`).
   - **Constraints** — format/length, the guardrails that apply (`05-guardrails`, name the G#),
     the review tier (`50-review`), and the model route (`80-performance`).

## Step 2 — Impact map | خريطة الأثر

Before touching a rule written in more than one place, `grep` its **essence, not
its name** (e.g. `LevelId == null` lived in four places). List, in the explanation,
who reads what you are about to change.

## Step 3 — Failing test first | اختبار يفشل أولاً

Reproduce what the owner reported or what you found, **on both layers** where the
behavior is server-side: a unit test (the decision, no DB) and an integration test
(that every caller reads the decision). See `40-testing.md`.

## Step 4 — Implement | التنفيذ

The smallest change that makes the test pass. No scope creep.

## Step 5 — Falsify | التكذيب *(signature step — do not skip)*

Disable the fix, watch its guard **fail alone**, then restore it. Show both
outputs. A test that passes with the fault put back is not a test — add a control
assertion that proves the guard is live.

## Step 6 — Gates (focused) | البوّابات المركّزة

Run **only the touched area + what it impacts** (grep importers/consumers), not
everything, to save tokens/time/effort. Full suite is reserved for changes to a
shared foundation (shell, pager, stubs, localization) or before a release/tag.
Any change claiming a **performance** improvement requires a measured number
before and after (see `80-performance.md`). Gate details by stack live in the
project rule and the stack rules.

## Step 7 — Document & commit | التوثيق والإيداع

Update the relevant docs + a **numbered manual-test scenario** + one commit per
batch, as jalakhras, in English, saying *why*. **Commit only when the owner has
authorized it for this batch** (see `30-git.md`). Tell the owner whether the API
must be restarted or a migrator run.

## "Done" | تعريف «تمّ»

Failing→passing test, falsified; unit + integration; gates green; docs updated;
manual scenario added; one commit; owner told about restart/migration. Not before.

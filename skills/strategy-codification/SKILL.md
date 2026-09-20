---
name: strategy-codification
description: Turn a corpus of trading-strategy sources (many video analyses, books, PDFs, exam answers) into a sequential Arabic guide (stages -> steps -> rules -> conditions), numbered testable rules with source timestamps, an explicit list of what cannot be automated, a falsification test, and an indicator specification — then hand off to pine-developer / mql5-developer for the code. Use after media-ingest has produced analysis.md files, or when the owner asks to turn a strategy explanation into rules, a checklist, a book, or an indicator.
metadata:
  origin: claude-harness
  lane: "2 (trading tools), fed by lane 5 (media)"
allowed-tools: Read, Glob, Grep, Bash, Write, Edit
---

# strategy-codification

Knowledge → rules. This skill **codifies**; it does not write Pine/MQL5 code —
that is `pine-developer` / `pine-manager` / `mql5-developer`. The boundary matters:
a rule that was never stated precisely produces an indicator that is confidently
wrong.

## When to use
- `media-ingest` produced `analysis.md` for many videos and the owner wants the
  strategy itself — rules, a checklist, a book, or an indicator.
- A strategy explanation exists across sources (videos + a book + exam answers)
  and must be reconciled into one consistent rule set.
- Before any indicator work: the spec comes from here.

Do **not** use for a single concept question (answer it directly) or to write code.

## Inputs
`<vault>\raw\videos\<topic>\*\analysis.md` (+ `transcript.md` and `frames/` when a
rule needs the exact wording or a chart), books/PDFs, and the owner's own notes.
Read `analysis.md` first — the raw transcripts only when a rule is ambiguous.

## Steps

### 1. Inventory the corpus
List every source with its length and what it covers. Say plainly which sources
disagree — reconciling them is the work, not a detail.

### 2. Extract numbered rules
Each rule is one line of logic, testable, traceable:

```
R-07 · Condition: <the observable trigger, stated precisely>
     => Result: <what it means / the action it implies>
     ! Exception: <when the rule does not apply>
     Source: [lesson 4 · 42:42] "<the quote it came from>"
```
- **Condition => result (! exception)** — no prose rules.
- **Every rule carries its source and timestamp.** A rule without a source is a
  hypothesis; mark it `<unsourced>` and list it separately.
- Keep the **source's own vocabulary** — do not rename its concepts into generic
  terms; the author will recognise their own words.

### 3. Separate what cannot be automated
An explicit list — this is what keeps an indicator honest:
frame choice, zoom calibration, which historical wave to start from, anything
requiring visual judgement. Each with *why* it resists automation and what the
indicator should do instead (ask the user / expose an input / stay silent).

### 4. Reconcile contradictions
Where sources conflict, state both readings, the evidence for each, and the
decision — or mark it **needs the owner** and stop there for that rule. Never
silently pick one.

### 5. Falsify the rule set ("break the model")
Before the spec, try to break it: construct the chart cases where the rules give
a wrong or undefined answer (a rule that never fails is probably vacuous). List
each break and how the rules handle it. This mirrors the workflow's falsify step.

### 6. The guide — stages → steps → rules → conditions *(owner's required output)*
A **teaching document a person can follow**, not a scattered rule list. Write
`guide.md` in Arabic, ordered so each stage depends only on what came before:

```
## المرحلة 1 — <اسمها> (الهدف في سطر)
### الخطوة 1.1 — <ما يُفعل بالضبط>
- **الشرط قبل البدء:** … (إن لم يتحقق، توقّف واذهب إلى …)
- **كيف تنفّذها:** خطوات ملموسة على الشارت
- **القواعد الحاكمة:** R-03, R-07  ← معرّفات القواعد من rules.md
- **متى تفشل:** … | **ماذا تفعل حينها:** …
- **المصدر:** [الدرس 4 · 42:42]
### الخطوة 1.2 — …
✅ **معيار إتمام المرحلة:** ما الذي يجب أن يكون واضحاً على الشارت قبل الانتقال
```

Requirements:
- **Sequential and gated:** every stage ends with a completion test; a reader must
  not reach stage 3 without satisfying stage 2.
- **Each step names its preconditions, its governing rule ids, and its failure mode.**
  Rules stay in `rules.md`; the guide *references* them — one source of truth.
- Mark every step that depends on a **non-automatable** judgement (§3) so the
  reader knows where their eye is required and an indicator cannot help.
- Include a **one-page checklist** at the end (the owner tests from it).
- The owner's own vocabulary throughout; no invented terminology.

### 7. Indicator specification (the deliverable to review)
Inputs, outputs (plots/labels/zones), the decision logic per bar referencing rule
ids, edge cases, and what it must **not** claim. **Stop here and get the owner's
approval** — a spec is reviewable; generated code is not.

### 8. Hand off (only after approval)
- TradingView → `pine-visualizer` (spec refinement) then `pine-developer` /
  `pine-manager`; validate with `backtest-expert` / `pine-backtester`.
- MT5 → `mql5-developer`.
- A designed book/checklist → use the design skills.

## Outputs
Write to the vault, not the repo — `<vault>\wiki\trading\<strategy>\`:

| File | What it is |
|---|---|
| **`guide.md`** | **the primary human deliverable** — stages → steps → rules → conditions, gated and followable, ending in a one-page checklist |
| `rules.md` | the numbered rule set (`R-07`), each with source + timestamp |
| `non-automatable.md` | what needs the reader's eye and why |
| `breaks.md` | the falsification cases and how the rules answer them |
| `indicator-spec.md` | the spec handed to `pine-*` / `mql5-developer` after approval |

All with frontmatter and `[[wikilinks]]` back to the raw sources. The rule ids
(`R-07`) are the shared language across the guide, the spec, the code, and the tests.

## Cost
Codification is Claude work (it needs judgement), so it costs tokens — read the
`analysis.md` files, not hundreds of raw transcripts. The corpus was produced for
free by `media-ingest`; spend the tokens only on the reasoning.

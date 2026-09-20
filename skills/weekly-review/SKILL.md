---
name: weekly-review
description: Turn recurring lessons into rules — read the growth log and project backlogs, find what keeps recurring across sessions, and propose promoting each pattern into a harness rule, stack layer, hook, or memory. Use weekly (or when the owner says /weekly-review), or whenever the same trap or preference has bitten more than once.
metadata:
  origin: claude-harness
  lane: "meta — continuous learning"
allowed-tools: Read, Glob, Grep, Bash, Edit, Write
---

# weekly-review

The harness improves from use, not just from the owner remembering to ask. Capture
is cheap (a growth-log line per session — see `60-memory`); the intelligence is
here: **distil the recurring into rules**, on a cadence, with the owner's approval.

Not a rewrite of the harness — a small, evidence-backed batch of promotions.

## Inputs
- `<vault>\growth-log.md` — the per-session lessons.
- `<vault>\daily\*.md` (recent) and each `wiki\projects\*\backlog.md`.
- The harness `CHANGELOG.md` (what already became a rule — don't re-propose it).
- Claude memory `feedback`/`project` entries added since the last review.

## Steps

### 1. Gather since the last review
Read the growth log and recent dailies back to the previous `weekly-review` marker
(or the last 7 days). List every distinct lesson with the sessions/dates it appeared.

### 2. Find what recurs
Group lessons by root cause. A pattern earns promotion when it is **recurring or
costly**:
- seen in **2+ sessions or 2+ projects** → likely a rule or stack layer;
- a trap that cost real time even once → at least a stack `Traps` entry;
- a preference the owner restated → a rule (that is exactly how the harness's
  core rules were born — restated 3–6 times each).
A one-off with no cost is **not** promoted — say so and drop it.

### 3. Decide the destination for each
| Pattern kind | Promote to |
|---|---|
| Cross-project principle | a `rules/*.md` (or a line in an existing one) |
| Stack-specific trap/idiom | that stack's `Traps`/`Idioms` (`onboard-stack` if the stack is new) |
| A mechanical guard that should block | a `hooks/` hook (`test-hooks.ps1` proves it) |
| A durable fact, not a rule | Claude memory / the vault, not a rule |
Prefer **editing an existing rule** over adding a new one; the rule set should
stay small and read in full.

### 4. Propose, don't apply blindly
Present a short table: pattern · evidence (where it recurred) · proposed change ·
destination. **Get the owner's approval per item** — this changes always-loaded
behavior. Skipped items stay in the log with a note so they are not re-proposed.

### 5. Apply the approved ones
Edit the harness repo, run `install.ps1` + `doctor.ps1` (and `test-hooks.ps1` if a
hook changed), bump `VERSION`, update `CHANGELOG.md`, and commit as one batch
(owner authorship, English). For a recurring cross-cutting principle, the
`rules-distill` skill can help extract the wording.

### 6. Close the loop
- Mark the reviewed lessons done in the growth log (append a `--- reviewed <date>`
  divider), so the next review starts after it.
- One `daily/` line + a note in `wiki\projects\claude-harness\decisions.md`.

## Cost
Reads a few small local files — cheap. Keep it that way: the growth log is one-line
entries, not transcripts. This runs weekly, not every session.

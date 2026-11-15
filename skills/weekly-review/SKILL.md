---
name: weekly-review
description: Learn from use — mine the week's conversations (the owner's own words), the growth log, both memories (the vault and claude-mem) and the project backlogs; find what keeps recurring; and propose promoting each pattern into a harness rule, stack layer, hook, memory, or a NEW SKILL for a workflow the owner keeps asking for. Use weekly (or when the owner says /weekly-review), or whenever the same trap, preference or request has come up more than once.
metadata:
  origin: claude-harness
  lane: "meta — continuous learning"
allowed-tools: Read, Glob, Grep, Bash, Edit, Write
---

# weekly-review

The harness improves from use, not just from the owner remembering to ask. Capture
is cheap (a growth-log line per session — see `60-memory`; the conversations
themselves are on disk); the intelligence is here: **distil the recurring into
rules and skills**, on a cadence, with the owner's approval.

Not a rewrite of the harness — a small, evidence-backed batch of promotions.

## Inputs
- **The conversations** — the owner's own words since the last review, mined by
  `scripts/mine_sessions.py` (step 1a). They hold what nobody wrote down: the
  corrections given mid-task and the requests made again and again.
- **Vault (Obsidian)** — `<vault>\growth-log.md` (the per-session lessons),
  `<vault>\daily\*.md` (recent) and each `wiki\projects\*\{backlog,decisions}.md`.
- **claude-mem** — the session observations since the last review (step 1b).
- The harness `CHANGELOG.md` (what already became a rule — don't re-propose it) and
  the installed skills (`~/.claude/skills/`) — what already became a skill.
- Claude memory `feedback`/`project` entries added since the last review.

## Steps

### 1. Gather since the last review
The window starts at the latest `--- reviewed <date>` divider in the growth log
(else the last 7 days).

**1a. The conversations.** Run, on this machine:
```
python -I ~/.claude/skills/weekly-review/scripts/mine_sessions.py extract --growth-log <vault>\growth-log.md --out <vault>\raw\sessions\<YYYY-MM-DD>-owner-messages.md
```
`~` works in bash and PowerShell, not in Windows `cmd`. When the owner runs it by
hand from `cmd`, write the path as `"%USERPROFILE%\.claude\skills\weekly-review\scripts\mine_sessions.py"`.
It keeps only what the owner typed (no tool output, harness reminders, subagent
briefs, compaction summaries, claude-mem's own prompts or pasted material), masks
secrets, and groups by project. Read the digest **yourself** — a week is typically
10–20 KB. The `analyze` sub-command (local Ollama, GPU freed after each call) is
only for a digest too large to read; its output is a **draft that invents items**
(seen on the first real run, 2026-11-15) — never promote anything from it without
the quote in the digest.

**1b. claude-mem.** Search the window for corrections, decisions and repeated work
(search → timeline → get_observations, only the records you choose).

**1c. The vault.** Read the growth log and recent dailies back to the divider, and
the backlogs/decisions.

List every distinct lesson **and every repeated request** with the dates and
sessions it appeared in, and its quote.

### 2. Find what recurs
Group by root cause. A pattern earns promotion when it is **recurring or costly**:
- seen in **2+ sessions or 2+ projects** → likely a rule or stack layer;
- a trap that cost real time even once → at least a stack `Traps` entry;
- a preference the owner restated → a rule (that is exactly how the harness's
  core rules were born — restated 3–6 times each);
- **the same kind of job asked for in 2+ sessions** (same steps, maybe different
  words) → a skill candidate.
A one-off with no cost is **not** promoted — say so and drop it.

### 3. Decide the destination for each
| Pattern kind | Promote to |
|---|---|
| Cross-project principle | a `rules/*.md` (or a line in an existing one) |
| Stack-specific trap/idiom | that stack's `Traps`/`Idioms` (`onboard-stack` if the stack is new) |
| A mechanical guard that should block | a `hooks/` hook (`test-hooks.ps1` proves it) |
| **A workflow the owner keeps requesting** | a **skill** in `skills/<name>/` (step 5a) — or a step added to an existing skill that almost covers it |
| A durable fact, not a rule | Claude memory / the vault, not a rule |
Prefer **editing an existing rule or skill** over adding a new one; the rule set
should stay small and read in full, and two skills must never do one job (G5).

### 4. Propose, don't apply blindly
Present a short table: pattern · evidence (quotes + dates) · proposed change ·
destination. For a skill, add: its name, its trigger in the owner's own words, and
its numbered steps. **Get the owner's approval per item** — this changes
always-loaded behavior. Skipped items stay in the log with a note so they are not
re-proposed.

### 5. Apply the approved ones
Edit the harness repo, run `install.ps1` + `doctor.ps1` (and `test-hooks.ps1` if a
hook changed), bump `VERSION`, update `CHANGELOG.md`, and commit as one batch
(owner authorship, English) — only on the owner's consent (`30-git`). For a
recurring cross-cutting principle, the `rules-distill` skill can help extract the
wording.

**5a. A new skill.** Draft it with **Skill Creator** in `skills/<name>/SKILL.md`
(`metadata.origin: claude-harness`, a description built from the owner's trigger
words, the steps as the body). Scripts it needs follow the harness test rules
(failing test, falsify). To use it in the Claude apps too (claude.ai, desktop),
the owner uploads the skill folder as a zip in the app's Skills settings.

**5b. The public repo.** A promotion that is a reusable pattern (not personal data,
paths or project names) is carried to the public guide repo as well, with personal
paths replaced by `<vault>` — ask the owner which items go public.

### 6. Close the loop
- Mark the reviewed lessons done in the growth log (append a `--- reviewed <date>`
  divider), so the next review — and the next mining run — starts after it.
- **Both memories:** one `daily/` line + a note in
  `wiki\projects\claude-harness\decisions.md` (vault), and one claude-mem memory
  per promoted item (what changed and why), so the next session recalls it.

## Cost
The digest is the owner's words only — a week reads in a few thousand tokens; the
raw transcripts (gigabytes) never enter the context. The local `analyze` pass is
free but unreliable; reading the digest directly is the accurate path. This runs
weekly, not every session.

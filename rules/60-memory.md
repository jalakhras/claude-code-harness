# Memory | الذاكرة

Three memory layers, each with one job. Do not duplicate rule text across them.

| Layer | Where | Job |
|---|---|---|
| Session memory | claude-mem (auto) | what happened this session; do not manage by hand |
| Claude memory | `~/.claude/projects/*/memory/*.md` | durable facts, feedback, project pointers |
| Knowledge | `<vault>` (Obsidian) | why-rules, decisions, research, media raw, daily log |

## Per project | لكل مشروع

Keep memory **on the machine and in Obsidian** («ذاكرة على الجهاز واستخدام
أوبسيدين»): a Claude memory file **and** `<vault>\wiki\projects\<name>.md` +
`<name>/{decisions,backlog}.md`, plus a `daily/YYYY-MM-DD.md` line per session.

## Vault rules (`<vault>\CLAUDE.md`) | قواعد الـ vault

- `raw/` is **read-only** — never edit or delete.
- `wiki/` is built from `raw/`; every page cites its source via `[[wikilink]]`.
- Frontmatter is mandatory; use `[[wikilinks]]` heavily; grep before creating a
  page to avoid duplicates.
- **Never delete any file** without explicit confirmation in the same message.
- Vault content is in **Arabic** (the vault's own rule) — this is the one place
  Arabic docs are correct; repo docs stay English.
- Daily log line format: `- **HH:mm** — text`.

## Recall before writing | الاسترجاع قبل الكتابة
Before starting non-trivial work, recall what is already known (the project's
memory file + its vault page) so you build on it instead of re-deriving. Before
writing a new memory, search for an existing one on the topic and **update it
rather than duplicate**; delete a memory that turns out wrong.

## What is worth remembering | ما يستحق الحفظ
A durable fact the code/git does not already record: a trap and its fix, a decision
and its *why*, a preference the owner stated, a pointer to where something lives.
**Not** worth saving: what a `grep` would show, a fixed bug already in git, or
anything that only matters to this one conversation.

## At session end | نهاية الجلسة
A fixed routine, every session:
1. **Claude memory** — add/adjust the durable facts learned (traps, decisions,
   preferences); update the existing file, don't stack duplicates.
2. **Obsidian** — update the project page and `decisions`/`backlog` if they
   changed; add one `daily/YYYY-MM-DD.md` line («نظّم ذاكرتك وحدّث أوبسيدين»).
3. **Growth log** — after a complex task or a failure, append one line to the
   central `<vault>\growth-log.md`: `- **YYYY-MM-DD · <project>** — <lesson>: why
   it happened, how to avoid it`. One line, not a diary. This is the raw material
   the weekly review distils.
4. If a trap or preference recurred, note it in the same line (`(recurred)`) — the
   weekly review looks for those.

## Continuous learning | التعلّم المستمر
Capture is cheap (step 3 above); the intelligence is the **`/weekly-review`**
skill, run weekly: it reads the growth log + project backlogs, finds what recurs
across sessions/projects, and proposes promoting each pattern into a rule, a stack
layer, or a hook — with your approval. That is how the harness improves from use.
A pattern seen in 2+ sessions/projects, or a trap that cost real time, is a
promotion candidate; a one-off with no cost is not.

## Compaction | الضغط

Suggest `/compact` at logical breakpoints — after research/exploration before
implementation, after a milestone, after a failed approach. **Never mid-
implementation** (you lose variable names, paths, partial state).

---
name: onboard-stack
description: Add a new language, framework, or domain to the harness in one repeatable pass — path-scoped rules, an optional reviewer agent, and a traps file — so a change of interest costs minutes, not a rebuild. Use when starting work in a stack the harness does not cover yet (a new language, framework, platform, or problem domain), or when an existing stack's rules have drifted from what the code actually does.
metadata:
  origin: claude-harness
  lane: "meta — keeps the harness general as interests change"
allowed-tools: Read, Glob, Grep, Bash, Write, Edit, WebSearch, WebFetch
---

# onboard-stack

The owner is a generalist whose interests move. The harness must therefore be
**stack-agnostic at its core and extensible at its edges**: the always-loaded
rules (workflow, testing, review, style, security, performance, design) already
apply to any language. What a new stack needs is a thin, path-scoped layer.

Never fork the harness for a stack. Add a layer.

## What a stack layer is

| Piece | Where | Loaded when |
|---|---|---|
| Rules | `rules/stacks/<stack>/<stack>.md` | a project imports it via its `.claude/CLAUDE.md` |
| Reviewer agent *(optional)* | `agents/<stack>-reviewer.md` | invoked by name after a batch |
| Project rule | `projects/<project>.md` → `<repo>/.claude/rules/` | inside that repo only |

Nothing global is touched, so an abandoned interest costs nothing: delete the
layer, or just stop importing it.

## Steps

### 1. Decide it is worth a layer
A layer earns its place when the owner will write **more than a throwaway script**
in it, or when the stack has traps that cost real time. A one-off experiment does
not need one — say so and stop.

### 2. Gather real material (search & reuse first)
- The official docs' idioms and the **security** guidance for that stack.
- What the owner's own code in it already does (`grep` the repo) — inherit the
  existing style rather than imposing a generic one.
- Known traps: the build/encoding/tooling failures that waste hours. Ask the owner
  what has already bitten him; those are worth more than any style guide.

### 3. Write `rules/stacks/<stack>/<stack>.md`
Keep it short — it is loaded into a real session. Sections, in this order:

```markdown
---
paths:
  - "**/*.<ext>"
---
# <Stack> | قواعد <Stack>

Extends the common rules. Only what differs for this stack.

## Idioms            # the 5-10 conventions that matter, not a tutorial
## Security          # injection/secrets/authz specifics for this stack
## Testing           # the test runner, what a unit vs integration test means here
## Traps             # concrete failures with the fix (the highest-value section)
## Gates             # exactly which commands prove a change is safe
```
Rules are **English**; headings may carry an Arabic title. No personal names in
the body (the harness is shareable).

### 4. Reviewer agent (only if reviews will be frequent)
Copy the shape of `agents/csharp-reviewer.md`: role, what to check (idioms, async/
memory model, security, the stack's traps), and a ranked-findings output. Keep it
under ~40 lines; the depth lives in the rules.

### 5. Wire it up
- `install.ps1` already copies `rules/stacks/**`, `agents/*.md` and `skills/*`.
  Run it, then `doctor.ps1`.
- In each project that uses the stack, import the layer from its
  `<repo>/.claude/CLAUDE.md` (git-excluded), e.g. `@rules/harness/stacks/<stack>/<stack>.md`.

### 6. Prove it, then record it
- **Falsify the traps:** for at least one trap, reproduce the failure and show the
  documented fix resolves it. A trap nobody verified is folklore.
- Add the decision to `<vault>\wiki\projects\claude-harness\decisions.md` and a
  `daily/` line; commit as one batch.

## Keeping the harness general
- **Lanes are open-ended.** `00-identity` lists the owner's current lanes; add or
  retire one as the work changes — it is a list, not a schema.
- **Do not let a domain leak into the core.** If a rule only makes sense for one
  stack, it belongs in that stack's layer, never in `10-workflow` or `55-coding-style`.
- **Retire dead layers.** When an interest ends, delete its stack file and agent;
  `doctor.ps1` will stop checking them. Nothing else depends on them.
- When a stack skill is genuinely needed (a full workflow, not just rules), create
  it under `skills/` — but only once real work demands it, not in anticipation.

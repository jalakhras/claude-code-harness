---
name: consult
description: Get a concise second opinion from a Gemini model (Google AI Studio API) on a NON-sensitive decision, or keep working when the Claude budget is low. Advisor only — Claude Code and the owner make the final call. Use when a hard decision wants an independent cross-check from a different model family, or to offload drafting/first-pass when Claude tokens run short. Never for sensitive/trading content (use local Ollama for that).
allowed-tools: Bash, Read
metadata:
  origin: claude-harness
  added: 2026-10-02
---

# consult

A thin stdlib CLI that sends a prompt to a Gemini model and prints the answer. It
is a **second opinion, never the decider**: Claude Code weighs the reply and the
owner approves (`rules/80-performance.md` → "Agent & model routing";
`rules/65-roles.md` delegation contract — "you own collection").

`SKILL_DIR` = the directory of THIS file. The script is `$SKILL_DIR/scripts/consult.py`.

## When to use (the owner's two triggers)
1. **On demand** — a hard decision or design choice wants an independent cross-check.
2. **Low Claude budget** — offload drafting/first-pass so work continues; the owner
   can also run it standalone when Claude is unavailable.

## When NOT to use
- **Never send sensitive / proprietary / trading / client content** — the prompt
  leaves the machine to Google and the free tier may train on it. For sensitive or
  bulk work use the **local Ollama** path instead (private, free, zero cloud).
- Not for a correctness-bearing *final* call — that stays with the strongest model
  and the owner.

## Which offload path (routing)
- **Local Ollama** → sensitive · bulk · first-pass drafting (private, free).
- **consult (Gemini)** → a strong second opinion on *non-sensitive* decisions, or
  to keep moving when the Claude budget is low.

## Usage
```
python "$SKILL_DIR/scripts/consult.py" --list                      # models the key unlocks
python "$SKILL_DIR/scripts/consult.py" "your question"             # default gemini-3.8-flash (free), output capped
python "$SKILL_DIR/scripts/consult.py" --max 800 "longer question" # raise the output cap
CONSULT_ALLOW_PAID=1 python "$SKILL_DIR/scripts/consult.py" --model gemini-pro-latest "critical decision"
```
- **Default model** `gemini-3.8-flash` (free). Output is capped (`--max`, default
  800 tokens) and extended thinking is disabled, so a reply stays concise and
  cannot flood the caller's context.
- **Paid guard:** any Pro model is refused unless `CONSULT_ALLOW_PAID=1` — no
  accidental paid calls. Use a paid model only on the owner's explicit say-so.
- **Key:** read from `GEMINI_API_KEY`, else `~/.claude/tools/.gemini_key` (one
  line). The key never enters git (`.gemini_key` is git-ignored). A free key comes
  from Google AI Studio.

## Manual test
1. `--list` prints model ids → the key works.
2. A trivial prompt on the default model returns an answer tagged `[free]` with a
   token line.
3. `--model gemini-pro-latest` **without** the env flag is **REFUSED**; with
   `CONSULT_ALLOW_PAID=1` it runs.

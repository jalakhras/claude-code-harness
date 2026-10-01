---
name: narrate
description: Speak text (a summary, a passage, a note) to a local audio file in Arabic (or any language) via VoiceStudio's on-machine OpenAI-compatible API. Local-first, no cloud, no key. For the content lane; Claude Code calls it, the owner decides. OPTIONAL skill — needs the separately-installed VoiceStudio app running locally.
allowed-tools: Bash, Read
metadata:
  origin: claude-harness
  added: 2026-10-02
  optional: true
  requires: "VoiceStudio (local app, AGPL-3.0, user-installed) on http://127.0.0.1:3900"
---

# narrate

Turn text into speech **locally** via VoiceStudio's OpenAI-compatible endpoint
(`POST /v1/audio/speech` on `127.0.0.1:3900`, no auth on loopback). Arabic is the
default — the spoken **language comes from the input text**; `voice` is only a
timbre. VoiceStudio is a separate **AGPL-3.0** app the owner installed; this skill
calls its HTTP API and ships none of its code.

`SKILL_DIR` = the directory of THIS file. Script: `$SKILL_DIR/scripts/narrate.py`.

## Optional skill (opt-in, togglable)
Not installed by default. Install with `install.ps1 -WithOptional` (or
`-Skills narrate`); disable by re-running `install.ps1` without the flag (it is
removed from `~/.claude/skills`). It does nothing unless VoiceStudio is running.

## When to use
- Narrate a summary, a codified booklet, or a passage to an Arabic audio file (lane 5),
  **only when the owner asked for audio**.

## When NOT to use
- VoiceStudio not installed/running → report clearly, never force it.
- Never trigger a model download without the owner's OK (guard below).

## Usage
```
python "$SKILL_DIR/scripts/narrate.py" "النص العربي" --out out.wav
echo "long text" | python "$SKILL_DIR/scripts/narrate.py" - --out out.wav --voice alloy
```
- **Health-first:** calls `GET /health`; if unreachable it prints a clear message
  and exits — no silent failure, no partial file.
- **Model-download guard:** the first generation may fetch the OmniVoice model
  (~2.3GB). The script **refuses** until `--yes-download` is passed — ask the owner
  first. After one authorized run a marker lets later calls proceed.
- **Local-first · Arabic default · no cloud · no key.**

## Manual test
1. VoiceStudio running + download authorized → narrate a short Arabic sentence →
   a playable `.wav` is written.
2. VoiceStudio stopped (or `--url` to a dead port) → a clear "not reachable"
   message, and **no** file.
3. First run without `--yes-download` → **REFUSED** with the ~2.3GB notice; with
   the flag → proceeds.

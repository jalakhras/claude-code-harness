---
name: local-tests
description: Run a Playwright (or any long browser) suite on the machine and read only a fixed-size summary — failures re-run once so flakes are named, expected/received per failure, an optional local-LLM triage via Ollama. Use whenever a Playwright suite is to be run; Claude supervises and reads the summary instead of the raw report.
metadata:
  origin: claude-harness
  lane: "1 (product engineering); any project with a Playwright suite"
allowed-tools: Bash, Read
---

# local-tests

The suite runs on the machine; Claude is the supervisor («اطلب من المديول
المحليه القيام بها لتوفير التوكن وانت تكون المراقب» — owner, 2026-09-20).

## Run

```
python ~/.claude/skills/local-tests/scripts/pw-run.py --cwd <playwright dir> <playwright args…>

python ~/.claude/skills/local-tests/scripts/pw-run.py --cwd <projects>/x/angular return-to --project=desktop
python ~/.claude/skills/local-tests/scripts/pw-run.py --cwd <projects>/x/angular return-to preview exam-form
```

What it does:

1. `npx playwright test <args> --reporter=json` — nothing of the raw output is shown.
2. Failures are re-run once with `--last-failed`; a test that passes the second
   time is reported as **flaky**, not as a defect.
3. Prints a summary that does not grow with the suite: counts, and per failure
   the spec file and line, the project (desktop/mobile), the test title, the
   first `Error`/`Expected`/`Received` lines, and the screenshot path.
4. With Ollama up (`qwen2.5:7b` by default), appends a six-line triage: failures
   grouped by likely cause, test-side vs application-side, which to open first.
   `--no-llm` skips it; the summary is the deliverable, the triage a bonus.

Exit code 1 when anything still fails after the re-run, else 0.

## How Claude uses it

- Read the summary. Open a screenshot or trace **only** for a failure being fixed.
- A flake is reported as a flake; fix its race if it is in a test we own
  (`expect.poll` on the request, not on a card that may already be right).
- Never pipe a full report, `--debug`, or one screenshot per failure into the context.
- Writing tests, falsifying them and fixing the app stay Claude's job; the
  local model does not edit anything.

## .NET suites — same idea | حِزم .NET

The other token-noisy suite (a .NET repo may run both) goes through `dotnet-run.py`:

```
python ~/.claude/skills/local-tests/scripts/dotnet-run.py --cwd <dir> [--filter <expr>]
python ~/.claude/skills/local-tests/scripts/dotnet-run.py --cwd <projects>/x --filter "FullyQualifiedName~MyFeature"
```
It runs `dotnet test` with a TRX logger and prints only counts + per failure the
test name and first error line (the full `.trx` path is given for a deep dive on a
failure being fixed). Zero-config: from a solution/project dir it just works; a
`--filter` scopes it for focused testing. `dotnet test` output and stack traces
never enter the context.

## Requirements

Python 3.10+; for Playwright the project's `npx playwright`; for .NET the SDK on
PATH; Ollama optional (triage). Both runners are **zero-config** — point `--cwd`
at the project (default `.`) and pass the usual test args. The
`PLAYWRIGHT_JSON_OUTPUT_NAME` variable is set by pw-run; a `reporter` in
`playwright.config` is overridden by the command-line reporter.

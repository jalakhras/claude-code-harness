<div align="center">

# 🧰 Harness tools — catalog by usage flow

![Claude Code](https://img.shields.io/badge/Claude_Code-harness-d97757?style=flat-square)
![rules](https://img.shields.io/badge/rules-15_+_4_stacks-0969da?style=flat-square)
![skills](https://img.shields.io/badge/skills-13-6f42c1?style=flat-square)
![agents](https://img.shields.io/badge/agents-7-1f6feb?style=flat-square)
![hooks](https://img.shields.io/badge/hooks-13-cf222e?style=flat-square)
![MCP](https://img.shields.io/badge/MCP_servers-1-2da44e?style=flat-square)
![runners](https://img.shields.io/badge/test_runners-3-bf8700?style=flat-square)

**Every tool the harness installs or routes to, ordered by where it falls in the change workflow.**

</div>

Flow (`rules/10-workflow.md`): **search → understand → research/design → implement → test → review → performance → commit → remember.** Harness-managed tools are generated into `~/.claude` by `install.ps1` and verified by `doctor.ps1`; **external / routed** tools are driven per the rules but installed on their own.

> [!TIP]
> **Type legend** — 🧩 `skill` · 🤖 `agent` (pinned model) · 🪝 `hook` (event) · 🔌 `mcp` · 📜 `script` · 🌐 `external`.
> MCP tools are **deferred**: an always-registered server costs no context until a session loads it.

---

## 📏 Always-loaded rules — the foundation under every stage
Imported into `~/.claude/CLAUDE.md` via `@import`, so they load **every session** (`rules/` → `rules/harness/`).

| Rule | What it governs |
|---|---|
| `00-identity` | The five work lanes; reply Arabic / code English; **no AI trace** anywhere public. |
| `05-guardrails` | AI-failure-mode guardrails **G1–G26** (intent · context · correctness · tests · security · debt · cost) — one report line per batch. |
| `10-workflow` | The change workflow: search → understand → restate → impact map → failing test → **falsify** → focused gates → document → commit-on-consent (chain-of-thought then ReAct). |
| `20-reporting` | Report progress unprompted; answer "done?" literally; the discussion queue; keep the manual-test list current. |
| `30-git` | Author **the owner** (configured name), English messages, no AI trace; commit only on per-batch consent; review before push. |
| `40-testing` | Two layers per decision; focused testing; **falsify every test**; local runners; split heavy suites across both machines. |
| `50-review` | Tiered review after every batch; severity levels; mandatory security-review triggers. |
| `55-coding-style` | KISS · DRY · YAGNI · immutability; small focused files/functions; validate at boundaries. |
| `60-memory` | Three memory layers (session · Claude · vault); recall before writing; the session-end routine + growth log. |
| `65-roles` | Role lenses (BA · PM · Architect · Dev · QA · Researcher · Security) worn sequentially; parallel agents only for independent work. |
| `70-media-and-research` | Raw evidence saved before analysis; every claim sourced & dated; the local media pipeline. |
| `80-performance` | Measure before/after; per-layer budget (SQL/API/UI); model-by-task routing; free the local GPU. |
| `85-security` | Secure-coding checklist; no system-structure leak; secrets handling; the owned-asset offensive fence. |
| `90-design` | One set of design tokens; semantic color; identity over decoration. |
| `95-ui` | Arabic-first RTL; four states (empty/loading/error/full); responsive & interactive; bilingual strings. |
| `stacks/{csharp, typescript, angular, pine}` | Path-scoped stack rules, loaded per project via its `.claude/CLAUDE.md`. |

---

## 🔍 0 · Search & reuse — before new code
| Tool | Type | What it does |
|---|---|---|
| GitHub / registry / docs search | 🌐 external | Find a battle-tested library or existing helper before hand-rolling (`10-workflow` Step 0). |

## 🧠 1 · Understand → restate → plan
| Tool | Type | What it does |
|---|---|---|
| `dev-team` | 🧩 skill | One-context multi-lens pass (BA → Architect → Dev → QA) — the cheap default for planning a feature. |
| `planner` | 🤖 agent · opus | Deep plan for architectural / multi-file work; design before code. |
| `onboard-stack` | 🧩 skill | Add a thin path-scoped layer (rules + optional reviewer) when work starts in a stack the harness doesn't cover. |

## 🔬 2 · Research & media — lanes 3 & 5
| Tool | Type | What it does |
|---|---|---|
| `research-protocol` | 🧩 skill | Evidence-first research that ends in a **decision**; every claim sourced & dated, contrarian evidence required. |
| `market-study` | 🧩 skill | `research-protocol` extended for competitors / markets. |
| `regulatory-scan` | 🧩 skill | `research-protocol` extended for regulation (engineering analysis, not legal advice). |
| `problem-hunting` | 🧩 skill | `research-protocol` extended for finding problems worth solving. |
| `media-ingest` | 🧩 skill | Watch a video/audio/folder: yt-dlp + ffmpeg frames + faster-whisper transcript → vault; hands off below. |
| `strategy-codification` | 🧩 skill | A corpus (analyses, books) → numbered, testable trading rules + indicator spec (no code). |
| `consult` | 🧩 skill → 🌐 Gemini | A strong **second opinion** on non-sensitive work, or to continue when the Claude budget is low (free flash default). |

## 🛠️ 3 · Implement
| Tool | Type | What it does |
|---|---|---|
| `tdd-guide` | 🤖 agent · sonnet | Enforces failing test → smallest fix → **falsify**. |
| `build-error-resolver` | 🤖 agent · sonnet | Resolves build / `tsc` / `ng build` / type errors. |
| Pi (`pi -p`) | 🌐 external | A multi-step read/write/edit/bash loop on a **local Ollama** model for a low-stakes, scoped sub-task. |
| Orca (`orca-cli`) | 🌐 external | Orchestrates several agents in isolated git worktrees with a review queue — genuinely independent work only. |

## ✅ 4 · Test — local runner first, worker for the heavy suites
| Tool | Type | What it does |
|---|---|---|
| `local-tests` | 🧩 skill | The rule + entry point: long/UI suites go through the runners below, never raw output into context. |
| `pw-run.py` | 📜 script | Playwright → JSON reporter, re-run failures once (flake vs defect), fixed-size summary (+ `--progress`). |
| `pytest-run.py` | 📜 script | pytest → JUnit XML → counts + per-failure first line; zero-tests / bad exit are **not** a pass. |
| `dotnet-run.py` | 📜 script | One `dotnet test` per project **in parallel** after one build; aggregates every `.trx`; a crash never reads green. |
| `run-split.ps1` | 📜 script | **Split the heavy suites across both machines in parallel** (`-Mode byType` / `byProject`); one merged verdict, wall ≈ the longer half. |
| `run-on-worker.ps1` | 📜 script | Put a whole suite on the lab worker (sync, fingerprint, evidence, fixed-size summary); falls back to local when it can't carry it. |
| `sync-to-worker.ps1` | 📜 script | Mirror the working tree to the worker (git archive + rsync, LF-faithful) with a content fingerprint. |
| `split_plan.py` · `redact.py` · `lab-common.ps1` | 📜 script | Split planning, secret redaction for evidence, shared PowerShell helpers. |
| Ollama | 🌐 external | Local LLM (`qwen2.5` / `aya-expanse`) for runner triage and media work; started on demand, freed when done. |

## 👁️ 5 · Review — tiered after every batch (`rules/50-review.md`)
| Tool | Type | What it does |
|---|---|---|
| `/code-review`, `/code-review-expert` | 🌐 external | The two general reviewers; the pair runs on real logic. |
| `csharp-reviewer` | 🤖 agent · sonnet | C#/.NET/ABP conventions, async, nullable, EF Core. |
| `typescript-reviewer` | 🤖 agent · sonnet | TypeScript / Angular / Astro / Chrome-ext review. |
| `database-reviewer` | 🤖 agent · sonnet | Queries, schema, migrations, pagination correctness. |
| `security-reviewer` | 🤖 agent · sonnet | Auth, input, files, crypto, IDOR — the mandatory-trigger review. |

## ⚡ 6 · Performance & design
| Tool | Type | What it does |
|---|---|---|
| `chrome-devtools` | 🔌 mcp | Live-page **performance traces** (LCP), DOM/CSS, network/CORS, console — backs "measure before/after" (`80-performance`). |
| `claude-in-chrome` | 🌐 mcp | Browser automation: navigate, click, forms, console, screenshots, network. |
| design companions | 🌐 external | `ui-ux-pro-max`, `frontend-design`, `make-interfaces-feel-better`, `design-system`, `design-audit`, `web-design-guidelines`, `impeccable` (`rules/90`, `95`). |

## 🔒 7 · Commit & push — guarded, not optional (`rules/30-git.md`)
| Hook · event | What it enforces |
|---|---|
| `git-author` · PreToolUse | Every commit passes `--author="<owner> …"` — no other author. |
| `git-commit-consent` · PreToolUse | Blocks a commit unless a `.claude/commit-consent` marker exists (owner authorizes per batch). |
| `git-push-review` · PreToolUse | Shows `git log origin..HEAD` before a push; no force to `main`. |
| `ef-no-build` / `ef-history-delete` · PreToolUse | Block `dotnet ef … --no-build` and deleting `__EFMigrationsHistory` rows. |
| `destructive-ops` · PreToolUse | Blocks `rm -rf` and other irreversible destruction (use `find -delete`). |
| `full-suite-dirty` · PreToolUse | Blocks a full suite while the tree is changing mid-edit. |
| `dev-server-fresh` · PreToolUse | Guards the stale-bundle trap (a dev server serving a pre-edit build). |
| `gateguard` · PreToolUse | Opt-in edit gate — **off by default** via `HARNESS_DISABLED_HOOKS`. |
| `strategic-compact` · PreToolUse | Nudges `/compact` at logical breakpoints, never mid-implementation. |
| `json-bom` · PostToolUse | Strips a BOM from JSON after a write (the `ar.json`/`en.json` trap). |
| `delivery-gate` · Stop | Delivery checks when a turn ends. |
| `session-start` · SessionStart | Injects the session-start reminders (workflow + authorship). |

## 📚 8 · Remember & improve (`rules/60-memory.md`)
| Tool | Type | What it does |
|---|---|---|
| `weekly-review` | 🧩 skill | Reads the growth log + backlogs, finds what recurs, proposes promoting a pattern into a rule / stack layer / hook. |
| `security-lab` | 🧩 skill | Authorized offensive testing on **owned assets only** (scope-fenced, `85-security`). |
| claude-mem | 🌐 mcp | Session memory + work-state; the durable record across sessions. |
| `narrate` | 🧩 skill | Optional, **off** by default — enable with `install.ps1 -Skills narrate`. |

---

<div align="center">

### 🏗️ How the harness installs & checks these

</div>

- **`install.ps1`** generates rules, hooks (via `scripts/merge-hooks.js` → `settings.json`), agents, skills, `scripts/lab/`, and registers MCP servers from [`mcp/servers.json`](../mcp/servers.json) at user scope (via `claude mcp`).
- **`doctor.ps1`** reports drift for every managed file, hook, agent, skill, lab script, and MCP server.
- **MCP servers** → [`mcp/README.md`](../mcp/README.md); their tools are deferred, costing no context until loaded.

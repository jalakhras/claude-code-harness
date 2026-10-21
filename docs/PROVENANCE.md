# Provenance

claude-harness is an original personal system that **adapts ideas and selected
files** from ECC ("Everything Claude Code", MIT-licensed,
github.com/affaan-m/ecc). It does **not** install the `ecc@ecc` plugin.

- Pinned ECC source: see `ECC-SOURCE.txt`.
- What we take: rule structure, a trimmed set of agents, hook architecture
  (profiles, disabled-hooks env, stdin JSON), and ~35 skill concepts.
- What we add: 9 custom skills, jalakhras working rules, jalakhras traps,
  vault + claude-mem + superpowers integration.
- License note: ECC is MIT; adapted files retain that permissive origin.

## Externally fetched skills (not vendored)

Some skills are **not committed** to this repo (no licence file, or third-party
reference content). `install.ps1` fetches them into `~/.claude/skills`, pinned to a
commit SHA; nothing of them enters this repository, and a failed fetch is non-fatal.

- **apple-design-skill** — `github.com/dickwu/apple-design-skill`, pinned
  `914b6a377c22755597e4405e54911b996de822d7`. The `ux-review` agent's aesthetic lens.
  **Not vendored:** it has no LICENSE file and its reference text is Apple's Human
  Interface Guidelines (belongs to Apple Inc.). If the fetch fails or a project names
  no lens, `ux-review` falls back to the harness design skills and says so.

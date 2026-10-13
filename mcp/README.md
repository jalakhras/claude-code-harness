# Harness-managed MCP servers

MCP servers the harness registers at **user scope** (`claude mcp add --scope user`),
so **every session on this machine has them directly** — no per-project setup.
`mcp/servers.json` is the source of truth; `install.ps1` registers each one through
the official `claude mcp` CLI (it never hand-edits the live `~/.claude.json`), and
`doctor.ps1` verifies each is present and connected.

Tools from these servers are **deferred**: they cost no context until a session
loads them (via the tool search), so an always-registered server is cheap until used.

## Servers

| Server | Transport | Command | Why it's here |
|---|---|---|---|
| `chrome-devtools` | stdio | `npx chrome-devtools-mcp@latest` | Live-page **performance traces** (LCP), DOM/CSS, network/CORS, console, and interaction for the Angular/Astro UI + performance lanes. Fills the gap `claude-in-chrome` leaves (no perf tracing) and backs the `80-performance` "measure before/after" rule. Official, by the Chrome DevTools team. |

## Add / change / remove

1. Edit `mcp/servers.json`.
2. `./install.ps1` (re-registers idempotently at user scope).
3. `./doctor.ps1` to confirm, or `claude mcp get <name>`.
4. **Open sessions pick up a new server only after a restart.**

Manual equivalent (what install runs): `claude mcp add --scope user --transport stdio <name> -- <command> <args…>`; remove with `claude mcp remove --scope user <name>`.

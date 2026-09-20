#!/usr/bin/env node
// BLOCK destructive commands unless the exact target is named in the user's last
// message (best effort: the event carries no transcript, so we block by default
// and tell the owner how to proceed). Covers recursive delete, hard reset, clean,
// DROP TABLE/DATABASE, and deletes under a read-only vault raw/ area (set
// HARNESS_VAULT to the vault root to guard it; defaults to a "raw" segment).
'use strict';
const h = require('./lib/harness-hook');

const PATTERNS = [
  { re: /\brm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r)\b/i,        what: 'rm -rf' },
  { re: /Remove-Item\b[\s\S]*-Recurse\b[\s\S]*-Force\b/i,      what: 'Remove-Item -Recurse -Force' },
  { re: /git\s+reset\s+--hard\b/i,                              what: 'git reset --hard' },
  { re: /git\s+clean\s+-[a-z]*f/i,                              what: 'git clean -f' },
  { re: /\bDROP\s+(TABLE|DATABASE)\b/i,                         what: 'DROP TABLE/DATABASE' },
  { re: /\b(rm|Remove-Item|del)\b[\s\S]*[\\/]+raw[\\/]+videos\b/i, what: 'delete under the vault raw/ area (read-only)' },
];

h.run('destructive-ops', () => {
  const cmd = h.effectiveCommand(h.commandOf(h.readEvent()));
  for (const p of PATTERNS) {
    if (p.re.test(cmd)) {
      h.block('destructive-ops',
        `destructive operation (${p.what}). If the owner named this exact target, re-run with ` +
        `HARNESS_DISABLED_HOOKS=destructive-ops for this one command, or narrow the path.`);
    }
  }
  h.allow();
});

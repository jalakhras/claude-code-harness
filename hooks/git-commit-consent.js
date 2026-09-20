#!/usr/bin/env node
// BLOCK a `git commit` unless the repo has a consent marker (.claude/commit-consent)
// or a standing-consent marker. The owner authorizes commits per batch.
'use strict';
const fs = require('fs');
const path = require('path');
const h = require('./lib/harness-hook');

h.run('git-commit-consent', () => {
  const evt = h.readEvent();
  const raw = h.commandOf(evt);
  const cmd = h.effectiveCommand(raw);
  if (!/\bgit\b[\s\S]*\bcommit\b/.test(cmd)) return h.allow();

  // Candidate repo dirs: the event cwd, plus any `cd <dir>` / `Set-Location <dir>`
  // the command changes into before committing (common: `cd X && git commit`).
  const dirs = [String(evt.cwd || process.cwd())];
  const cdRe = /(?:\bcd\b|Set-Location|\bsl\b)\s+(?:"([^"]+)"|'([^']+)'|(\S+))/gi;
  let m;
  while ((m = cdRe.exec(raw)) !== null) {
    const d = m[1] || m[2] || m[3];
    if (d && !d.startsWith('-')) dirs.push(d);
  }
  for (const d of dirs) {
    try { if (fs.existsSync(path.join(d, '.claude', 'commit-consent'))) return h.allow(); } catch (_) {}
  }

  h.block('git-commit-consent',
    `no commit consent for this repo. The owner authorizes each batch. To allow: create ` +
    `a ".claude/commit-consent" marker in the repo after the owner says so. ` +
    `Checked: ${dirs.join(', ')}`);
});

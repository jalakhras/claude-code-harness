#!/usr/bin/env node
// BLOCK a `git commit` that would not be authored as {{AUTHOR}} <{{EMAIL}}>,
// or that carries any Claude attribution. Non-commit commands pass.
'use strict';
const h = require('./lib/harness-hook');
const AUTHOR = '{{AUTHOR}}';
const EMAIL  = '{{EMAIL}}';

h.run('git-author', () => {
  const cmd = h.effectiveCommand(h.commandOf(h.readEvent()));
  if (!/\bgit\b[\s\S]*\bcommit\b/.test(cmd)) return h.allow();

  // Amend/rebase without a message and interactive edits still need the author.
  const hasAuthor = new RegExp(`--author\\s*=?\\s*["']?${AUTHOR}\\s*<${EMAIL}>`, 'i').test(cmd);
  if (!hasAuthor) {
    h.block('git-author',
      `commit must pass --author="${AUTHOR} <${EMAIL}>". No commit is authored under any other name.`);
  }
  if (/co-authored-by|generated with|🤖|noreply@anthropic/i.test(cmd)) {
    h.block('git-author',
      'commit message carries a Claude/attribution trailer. Remove it — the work ships under the owner only.');
  }
  h.allow();
});

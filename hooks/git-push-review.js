#!/usr/bin/env node
// WARN before `git push` (review outgoing commits first). BLOCK a force-push to main.
'use strict';
const h = require('./lib/harness-hook');

h.run('git-push-review', () => {
  const cmd = h.effectiveCommand(h.commandOf(h.readEvent()));
  if (!/\bgit\s+push\b/.test(cmd)) return h.allow();

  const force = /--force\b|--force-with-lease\b|\s-f\b/.test(cmd);
  const toMain = /\b(main|master)\b/.test(cmd);
  if (force && toMain) {
    h.block('git-push-review', 'force-push to main/master is blocked. Push a branch and open a PR.');
  }
  h.warn('git-push-review', 'about to push — review outgoing commits first: git log origin..HEAD');
});

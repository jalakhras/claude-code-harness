#!/usr/bin/env node
// WARN when starting a full test suite (no spec/filter) while the tree is dirty.
// Three full runs were thrown away because a file changed mid-run.
'use strict';
const { execSync } = require('child_process');
const h = require('./lib/harness-hook');

h.run('full-suite-dirty', () => {
  const evt = h.readEvent();
  const cmd = h.effectiveCommand(h.commandOf(evt));
  const playwrightAll = /playwright\s+test\b/.test(cmd) && !/[\w./-]+\.spec\.[tj]s|--grep|-g\b/.test(cmd);
  const dotnetAll = /dotnet\s+test\b/.test(cmd) && !/--filter\b/.test(cmd);
  if (!playwrightAll && !dotnetAll) return h.allow();

  let dirty = '';
  try {
    dirty = execSync('git status --porcelain', { cwd: evt.cwd || process.cwd(), stdio: ['ignore','pipe','ignore'] })
      .toString().trim();
  } catch (_) { return h.allow(); }
  if (dirty) {
    h.warn('full-suite-dirty',
      'starting a FULL suite while the tree is dirty. A file changing mid-run wastes ~20 min. ' +
      'Finish edits, or run targeted specs (spec name / --filter) first.');
  }
  h.allow();
});

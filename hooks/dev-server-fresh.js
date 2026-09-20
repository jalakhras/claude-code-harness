#!/usr/bin/env node
// WARN when running Playwright while a stale `ng serve` may be on 4200 (the
// stale-bundle trap, hit 5x). Best effort: we cannot inspect process mtimes
// portably here, so we remind on any Playwright run in an Angular project.
'use strict';
const fs = require('fs');
const path = require('path');
const h = require('./lib/harness-hook');

h.run('dev-server-fresh', () => {
  const evt = h.readEvent();
  const cmd = h.effectiveCommand(h.commandOf(evt));
  if (!/playwright\s+test\b/.test(cmd)) return h.allow();
  const cwd = String(evt.cwd || process.cwd());
  // Only nudge in an Angular workspace.
  const isAngular = fs.existsSync(path.join(cwd, 'angular.json')) ||
                    fs.existsSync(path.join(cwd, 'angular', 'angular.json'));
  if (!isAngular) return h.allow();
  h.warn('dev-server-fresh',
    'stale-bundle trap: a dev server started before your last edit keeps serving the old bundle. ' +
    'Check the 4200 node start time, or kill 4200 and let Playwright start its own. ' +
    'Run check:templates before trusting an e2e result.');
});

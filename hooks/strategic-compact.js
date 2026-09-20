#!/usr/bin/env node
// WARN roughly every ~50 Edit/Write calls to suggest a logical /compact. Uses a
// per-session counter file keyed by session_id under the OS temp dir.
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const h = require('./lib/harness-hook');
const EVERY = 50;

h.run('strategic-compact', () => {
  const evt = h.readEvent();
  const sid = String(evt.session_id || 'nosession').replace(/[^\w-]/g, '');
  const f = path.join(os.tmpdir(), `harness-compact-${sid}.count`);
  let n = 0;
  try { n = parseInt(fs.readFileSync(f, 'utf8'), 10) || 0; } catch (_) {}
  n += 1;
  try { fs.writeFileSync(f, String(n)); } catch (_) {}
  if (n % EVERY === 0) {
    h.warn('strategic-compact',
      `~${n} edits this session. If you are at a logical breakpoint (research done, milestone ` +
      `complete), consider /compact — never mid-implementation.`);
  }
  h.allow();
});

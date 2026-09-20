#!/usr/bin/env node
// PreToolUse on Edit/Write: force investigation before the FIRST edit of each file
// in a session. Disabled by default (in HARNESS_DISABLED_HOOKS); enable for
// sensitive code. Tracks seen files per session in a temp file.
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const h = require('./lib/harness-hook');

h.run('gateguard', () => {
  const evt = h.readEvent();
  const fp = h.filePathOf(evt);
  if (!fp) return h.allow();
  const sid = String(evt.session_id || 'nosession').replace(/[^\w-]/g, '');
  const store = path.join(os.tmpdir(), `harness-gateguard-${sid}.json`);
  let seen = {};
  try { seen = JSON.parse(fs.readFileSync(store, 'utf8')); } catch (_) {}
  if (seen[fp]) return h.allow();            // already investigated this file
  seen[fp] = 1;
  try { fs.writeFileSync(store, JSON.stringify(seen)); } catch (_) {}
  h.block('gateguard',
    `first edit of ${fp} this session. Before editing, state: (1) who imports/consumes it ` +
    `(grep the essence, not the name), (2) the guard/test that protects this behavior, ` +
    `(3) the owner's instruction this serves. Then retry — this file is now cleared.`);
});

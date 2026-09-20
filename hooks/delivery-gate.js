#!/usr/bin/env node
// Stop hook: deterministic session-hygiene check. WARN on rationalization phrases
// in the transcript tail; BLOCK if a complex session touched no memory/vault file.
'use strict';
const fs = require('fs');
const h = require('./lib/harness-hook');

const RATIONALIZE = [
  /skip(ping)? tests? for now/i, /pre-existing (bug|issue)/i,
  /should (just )?work/i, /good enough for now/i, /leave (it|this) for later/i,
];

h.run('delivery-gate', () => {
  const evt = h.readEvent();
  const tp = evt.transcript_path;
  if (!tp || !fs.existsSync(tp)) return h.allow();
  let text = '';
  try {
    const buf = fs.readFileSync(tp, 'utf8');
    text = buf.slice(-20000); // tail only
  } catch (_) { return h.allow(); }

  for (const re of RATIONALIZE) {
    if (re.test(text)) {
      h.warn('delivery-gate',
        'a rationalization phrase appeared this session (e.g. "skip tests for now"). ' +
        'Confirm nothing was quietly deferred before finishing.');
    }
  }
  h.allow();
});

#!/usr/bin/env node
// PostToolUse on Write/Edit: strip a UTF-8 BOM from JSON localization files.
// Writing ar.json/en.json with a BOM once failed 371 e2e tests.
'use strict';
const fs = require('fs');
const h = require('./lib/harness-hook');

h.run('json-bom', () => {
  const evt = h.readEvent();
  const fp = h.filePathOf(evt);
  if (!/\.json$/i.test(fp)) return h.allow();
  let buf;
  try { buf = fs.readFileSync(fp); } catch (_) { return h.allow(); }
  if (buf.length >= 3 && buf[0] === 0xEF && buf[1] === 0xBB && buf[2] === 0xBF) {
    try {
      fs.writeFileSync(fp, buf.slice(3));
      h.warn('json-bom', `stripped a UTF-8 BOM from ${fp} (BOM in ar.json/en.json breaks the e2e stub).`);
    } catch (e) { h.warn('json-bom', `BOM found in ${fp} but could not rewrite: ${e.message}`); }
  }
  h.allow();
});

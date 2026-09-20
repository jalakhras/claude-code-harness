#!/usr/bin/env node
// Merge claude-harness hooks into ~/.claude/settings.json — idempotently and
// without touching other tools' hooks (e.g. claude-mem). JSON is handled in Node
// for reliability (PS 5.1 ConvertTo-Json is lossy).
//
// Usage: node merge-hooks.js <claudeRoot> <installedHooksDir> <manifestPath> [--remove] [--dry-run]
//   claudeRoot        e.g. C:\Users\jalak\.claude
//   installedHooksDir e.g. C:\Users\jalak\.claude\hooks\harness
//   manifestPath      the repo's hooks/hooks.manifest.json (source of truth)
'use strict';
const fs = require('fs');
const path = require('path');

const [, , claudeRoot, hooksDir, manifestArg, ...flags] = process.argv;
const REMOVE = flags.includes('--remove');
const DRY = flags.includes('--dry-run');
if (!claudeRoot || !hooksDir || !manifestArg) { console.error('usage: merge-hooks.js <claudeRoot> <hooksDir> <manifestPath> [--remove] [--dry-run]'); process.exit(1); }

const MARKER = 'harness'; // identifies our entries by command path fragment
const settingsPath = path.join(claudeRoot, 'settings.json');
const manifestPath = manifestArg;

const settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));

// 1. Strip any existing harness entries from every event (idempotent re-run / uninstall).
if (settings.hooks && typeof settings.hooks === 'object') {
  for (const event of Object.keys(settings.hooks)) {
    if (!Array.isArray(settings.hooks[event])) continue;
    settings.hooks[event] = settings.hooks[event].filter(entry => {
      const cmds = (entry.hooks || []).map(h => String(h.command || ''));
      const isOurs = cmds.some(c => c.includes(MARKER) || c.includes('harness'));
      return !isOurs;
    });
    if (settings.hooks[event].length === 0) delete settings.hooks[event];
  }
  if (Object.keys(settings.hooks).length === 0) delete settings.hooks;
}

let added = 0;
if (!REMOVE) {
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  settings.hooks = settings.hooks || {};
  for (const h of manifest.hooks) {
    const abs = path.join(hooksDir, h.file);
    const command = `node "${abs}"`;
    settings.hooks[h.event] = settings.hooks[h.event] || [];
    settings.hooks[h.event].push({ matcher: h.matcher, hooks: [{ type: 'command', command }] });
    added++;
  }
  // env defaults (do not clobber an existing value the owner set)
  settings.env = settings.env || {};
  for (const [k, v] of Object.entries(manifest.envDefaults || {})) {
    if (!(k in settings.env)) settings.env[k] = v;
  }
}

const out = JSON.stringify(settings, null, 2) + '\n';
if (DRY) {
  console.log(`[merge-hooks] ${REMOVE ? 'would remove' : 'would register ' + added} harness hooks in ${settingsPath}`);
  process.exit(0);
}
fs.writeFileSync(settingsPath, out, { encoding: 'utf8' }); // Node writes UTF-8 no BOM
console.log(`[merge-hooks] ${REMOVE ? 'removed harness hooks' : 'registered ' + added + ' harness hooks'} in settings.json`);

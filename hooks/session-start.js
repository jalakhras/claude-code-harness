#!/usr/bin/env node
// SessionStart hook: print a short context block (project guess, vault page, WF
// step-1 reminder). Output on stdout is added to the session context.
'use strict';
const fs = require('fs');
const path = require('path');
const h = require('./lib/harness-hook');

if (!h.hooksEnabled() || h.isDisabled('session-start')) process.exit(0);
try {
  const evt = h.readEvent();
  const cwd = String(evt.cwd || process.cwd());
  const name = path.basename(cwd);
  // Guess the kind of work from generic signals in the repo, not hard-coded names.
  const has = (p) => { try { return fs.existsSync(path.join(cwd, p)); } catch (_) { return false; } };
  const glob1 = (ext) => { try { return fs.readdirSync(cwd).some(f => f.endsWith(ext)); } catch (_) { return false; } };
  const hatByPath = () => {
    if (has('angular.json')) return 'product engineering (Angular)';
    if (has('astro.config.mjs') || has('astro.config.ts')) return 'product engineering (Astro)';
    if (glob1('.csproj') || glob1('.sln')) return 'product engineering (.NET)';
    if (has('manifest.json') && has('background.js')) return 'a browser extension';
    if (glob1('.pine')) return 'trading tools (Pine Script)';
    return null;
  };
  const hat = hatByPath();
  // Optional knowledge vault; set HARNESS_VAULT to enable the pointer.
  const vault = process.env.HARNESS_VAULT || '';
  const vaultPage = vault ? path.join(vault, 'wiki', 'projects', `${name}.md`) : '';
  const lines = [];
  lines.push('[harness] session-start:');
  lines.push(`- cwd: ${cwd}${hat ? ` — likely hat: ${hat}` : ''}`);
  if (fs.existsSync(vaultPage)) lines.push(`- vault page: ${vaultPage}`);
  lines.push('- WF step 1: restate the request as small, uniform numbered steps before acting.');
  lines.push('- commit as the owner only; commit only on consent.');
  process.stdout.write(lines.join('\n') + '\n');
} catch (_) {}
process.exit(0);

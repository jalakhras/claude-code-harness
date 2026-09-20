// Shared helper for claude-harness hooks (Node.js, no dependencies).
// Every hook reads a JSON event from stdin: { tool_name, tool_input, cwd, ... }.
// Exit codes: 0 = allow/warn (stderr shown, tool proceeds), 2 = block.
'use strict';

const fs = require('fs');

// Read the whole stdin synchronously and parse the hook event.
function readEvent() {
  let raw = '';
  try { raw = fs.readFileSync(0, 'utf8'); } catch (_) { raw = ''; }
  try { return raw ? JSON.parse(raw) : {}; } catch (_) { return {}; }
}

// The command string a Bash/PowerShell tool is about to run (best effort).
function commandOf(evt) {
  const ti = evt.tool_input || {};
  return String(ti.command || ti.script || ti.cmd || '');
}

// A command with echo/print statements and comments removed, so a trigger word
// that only appears as text being echoed (or in a comment) does not cause a
// false block. Narrow on purpose: it must NOT blank general quoted arguments,
// because git --author="..." values and quoted SQL are real signals hooks read.
function effectiveCommand(cmd) {
  let s = String(cmd);
  // drop echo/printf/Write-Host/Write-Output and their args up to a separator
  s = s.replace(/\b(echo|printf|Write-Host|Write-Output)\b[^\n;&|]*/gi, '');
  s = s.replace(/#[^\n]*/g, '');   // shell comments
  return s;
}

// The file path an Edit/Write tool targets (best effort).
function filePathOf(evt) {
  const ti = evt.tool_input || {};
  return String(ti.file_path || ti.path || ti.notebook_path || '');
}

// Is this hook id switched off via HARNESS_DISABLED_HOOKS=a,b,c ?
function isDisabled(id) {
  const list = String(process.env.HARNESS_DISABLED_HOOKS || '')
    .split(',').map(s => s.trim()).filter(Boolean);
  return list.includes(id);
}

// Master switch: HARNESS_HOOKS_ENABLED=false turns all harness hooks off.
function hooksEnabled() {
  const v = String(process.env.HARNESS_HOOKS_ENABLED || 'true').toLowerCase();
  return v !== 'false' && v !== '0' && v !== 'off';
}

// Block the tool: print reason to stderr, exit 2.
function block(id, message) {
  process.stderr.write(`[harness:${id}] BLOCKED — ${message}\n`);
  process.exit(2);
}

// Warn but allow: print to stderr, exit 0.
function warn(id, message) {
  process.stderr.write(`[harness:${id}] ${message}\n`);
  process.exit(0);
}

// Allow silently.
function allow() { process.exit(0); }

// Standard entry: skip when globally disabled or this id is disabled.
function run(id, fn) {
  if (!hooksEnabled() || isDisabled(id)) process.exit(0);
  try { fn(); } catch (e) {
    // A hook must never hard-fail the tool on its own bug: warn and allow.
    process.stderr.write(`[harness:${id}] hook error (allowing): ${e && e.message}\n`);
    process.exit(0);
  }
  process.exit(0);
}

module.exports = {
  readEvent, commandOf, effectiveCommand, filePathOf, isDisabled, hooksEnabled,
  block, warn, allow, run,
};

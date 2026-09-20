#!/usr/bin/env node
// BLOCK `dotnet ef migrations add ... --no-build`. It scaffolds an empty or wrong
// migration from a stale assembly (cost the owner twice).
'use strict';
const h = require('./lib/harness-hook');

h.run('ef-no-build', () => {
  const cmd = h.effectiveCommand(h.commandOf(h.readEvent()));
  const isEfMigration = /dotnet\s+ef\s+migrations\s+(add|remove)/i.test(cmd);
  if (isEfMigration && /--no-build\b/.test(cmd)) {
    h.block('ef-no-build',
      'dotnet ef migrations with --no-build reads a stale assembly and scaffolds an empty/wrong ' +
      'migration. Remove --no-build and use --startup-project ...HttpApi.Host.');
  }
  h.allow();
});

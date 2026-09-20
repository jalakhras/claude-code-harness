#!/usr/bin/env node
// BLOCK any command that deletes rows from __EFMigrationsHistory. Falsifying a
// migration this way leaves the DB stuck (SQL 2705).
'use strict';
const h = require('./lib/harness-hook');

h.run('ef-history-delete', () => {
  const cmd = h.effectiveCommand(h.commandOf(h.readEvent()));
  if (/__EFMigrationsHistory/i.test(cmd) && /\bdelete\b|\btruncate\b|\bdrop\b/i.test(cmd)) {
    h.block('ef-history-delete',
      'never delete/truncate __EFMigrationsHistory rows — it leaves the DB stuck. ' +
      'Roll back with `dotnet ef migrations remove` or a proper down migration.');
  }
  h.allow();
});

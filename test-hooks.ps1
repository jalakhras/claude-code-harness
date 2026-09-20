#requires -Version 5.1
<#
.SYNOPSIS
  Prove each blocking hook actually blocks, and each allow-case actually passes,
  by feeding synthetic hook events (JSON on stdin) to the installed hook scripts.
.DESCRIPTION
  A failing hook that silently allows is worse than no hook. This runs the real
  installed hooks under node with crafted events and checks the exit code
  (2 = block, 0 = allow). Read-only: it never runs the dangerous commands.
#>
[CmdletBinding()]
param([string]$Author = 'jalakhras', [string]$Email = 'you@example.com')
$ErrorActionPreference = 'Stop'
$HooksDir = Join-Path $env:USERPROFILE '.claude\hooks\harness'
$fails = 0

function Invoke-Hook([string]$file, [hashtable]$evt, [hashtable]$envOverride = @{}) {
  # Deliver the event via a temp FILE redirected to stdin. Piping a string to a
  # native exe in PS 5.1 does not reliably reach node's readFileSync(0); a file does.
  $json = $evt | ConvertTo-Json -Compress -Depth 6
  $path = Join-Path $HooksDir $file
  $tmp  = Join-Path $env:TEMP ("harness-ev-" + [guid]::NewGuid().ToString('N') + ".json")
  [System.IO.File]::WriteAllText($tmp, $json, (New-Object System.Text.UTF8Encoding($false)))
  $old = @{}
  foreach ($k in $envOverride.Keys) { $old[$k] = [Environment]::GetEnvironmentVariable($k); [Environment]::SetEnvironmentVariable($k, $envOverride[$k]) }
  $savedEAP = $ErrorActionPreference
  $ErrorActionPreference = 'SilentlyContinue'   # a hook writing to stderr is expected, not a script error
  try { & cmd /c "node `"$path`" < `"$tmp`"" 2>&1 | Out-Null } finally {
    $ErrorActionPreference = $savedEAP
    foreach ($k in $old.Keys) { [Environment]::SetEnvironmentVariable($k, $old[$k]) }
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
  }
  return $LASTEXITCODE
}

function Check([string]$name, [int]$got, [int]$want) {
  if ($got -eq $want) { Write-Host ("  PASS: {0} (exit {1})" -f $name, $got) -ForegroundColor DarkGreen }
  else { Write-Host ("  FAIL: {0} (exit {1}, expected {2})" -f $name, $got, $want) -ForegroundColor Red; $script:fails++ }
}

Write-Host "claude-harness hook tests" -ForegroundColor Cyan

# git-author: block bad, allow good
Check 'git-author blocks commit without --author' `
  (Invoke-Hook 'git-author.js' @{ tool_name='Bash'; tool_input=@{ command='git commit -m "x"' } }) 2
Check 'git-author blocks Co-Authored-By trailer' `
  (Invoke-Hook 'git-author.js' @{ tool_name='Bash'; tool_input=@{ command=("git commit --author=""{0} <{1}>"" -m ""x`n`nCo-Authored-By: Claude""" -f $Author,$Email) } }) 2
Check 'git-author allows correct author' `
  (Invoke-Hook 'git-author.js' @{ tool_name='Bash'; tool_input=@{ command=("git commit --author=""{0} <{1}>"" -m ""x""" -f $Author,$Email) } }) 0
Check 'git-author ignores non-commit' `
  (Invoke-Hook 'git-author.js' @{ tool_name='Bash'; tool_input=@{ command='git status' } }) 0

# ef-no-build
Check 'ef-no-build blocks --no-build migration' `
  (Invoke-Hook 'ef-no-build.js' @{ tool_name='Bash'; tool_input=@{ command='dotnet ef migrations add X --no-build' } }) 2
Check 'ef-no-build allows normal migration' `
  (Invoke-Hook 'ef-no-build.js' @{ tool_name='Bash'; tool_input=@{ command='dotnet ef migrations add X --startup-project src/Host' } }) 0

# ef-history-delete
Check 'ef-history-delete blocks DELETE on history' `
  (Invoke-Hook 'ef-history-delete.js' @{ tool_name='Bash'; tool_input=@{ command='sqlcmd -Q "DELETE FROM __EFMigrationsHistory"' } }) 2

# destructive-ops
Check 'destructive-ops blocks rm -rf' `
  (Invoke-Hook 'destructive-ops.js' @{ tool_name='Bash'; tool_input=@{ command='rm -rf ./build' } }) 2
Check 'destructive-ops blocks git reset --hard' `
  (Invoke-Hook 'destructive-ops.js' @{ tool_name='Bash'; tool_input=@{ command='git reset --hard HEAD~1' } }) 2
Check 'destructive-ops allows normal rm' `
  (Invoke-Hook 'destructive-ops.js' @{ tool_name='Bash'; tool_input=@{ command='rm ./tmp.txt' } }) 0

# git-commit-consent (no marker in a temp cwd -> block)
$tmp = Join-Path $env:TEMP ("harness-test-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
Check 'git-commit-consent blocks without marker' `
  (Invoke-Hook 'git-commit-consent.js' @{ tool_name='Bash'; cwd=$tmp; tool_input=@{ command='git commit -m "x"' } }) 2
New-Item -ItemType Directory -Force -Path (Join-Path $tmp '.claude') | Out-Null
Set-Content -Path (Join-Path $tmp '.claude\commit-consent') -Value 'ok'
Check 'git-commit-consent allows with marker' `
  (Invoke-Hook 'git-commit-consent.js' @{ tool_name='Bash'; cwd=$tmp; tool_input=@{ command='git commit -m "x"' } }) 0
Remove-Item -Recurse -Force $tmp

# disabled-hook honored
Check 'HARNESS_DISABLED_HOOKS disables git-author' `
  (Invoke-Hook 'git-author.js' @{ tool_name='Bash'; tool_input=@{ command='git commit -m "x"' } } @{ HARNESS_DISABLED_HOOKS='git-author' }) 0

Write-Host ""
if ($fails -eq 0) { Write-Host "All hook tests passed." -ForegroundColor Green; exit 0 }
else { Write-Host "$fails hook test(s) FAILED." -ForegroundColor Red; exit 1 }

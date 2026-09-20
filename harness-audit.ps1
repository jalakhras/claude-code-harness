#requires -Version 5.1
<#
.SYNOPSIS
  Deterministic compliance audit: not "do the rules exist" but "are they actually
  in force". Read-only, ~free (no tokens, no agents).
.DESCRIPTION
  Checks the machine-verifiable half of harness compliance:
    - install integrity (doctor: installed == repo, hooks registered)
    - hooks actually block (runs test-hooks.ps1)
    - CLAUDE.md loads the rules (@import block present)
    - authorship: recent harness commits are the owner, no Claude trace
    - project rules installed into their repos (where the repo exists)
    - memory hygiene: growth log + vault status exist and are recent
  Each check prints PASS / WARN / FAIL. Exit 0 if no FAIL.
  Behavioural compliance (does Claude *follow* a rule in practice) is out of scope
  here - that needs scenario runs and tokens; this is the cheap objective layer.
#>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Continue'
$RepoRoot   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ClaudeRoot = Join-Path $env:USERPROFILE '.claude'
$fails = 0; $warns = 0
function Read-Utf8([string]$p){ [IO.File]::ReadAllText($p,[Text.Encoding]::UTF8) }
function Pass([string]$m){ Write-Host "  PASS: $m" -ForegroundColor DarkGreen }
function Warn([string]$m){ Write-Host "  WARN: $m" -ForegroundColor Yellow; $script:warns++ }
function Fail([string]$m){ Write-Host "  FAIL: $m" -ForegroundColor Red; $script:fails++ }
function Section([string]$m){ Write-Host "`n== $m ==" -ForegroundColor Cyan }

Write-Host "claude-harness audit (deterministic compliance)" -ForegroundColor Cyan

# 1. install integrity
Section "install integrity"
& (Join-Path $RepoRoot 'doctor.ps1') *> $null
if ($LASTEXITCODE -eq 0) { Pass "doctor clean (installed matches repo, hooks registered)" }
else { Fail "doctor reports drift - run install.ps1" }

# 2. hooks actually block
Section "hooks enforce"
& (Join-Path $RepoRoot 'test-hooks.ps1') *> $null
if ($LASTEXITCODE -eq 0) { Pass "test-hooks 13/13 - blocking hooks block, allow-cases pass" }
else { Fail "a blocking hook did not block - run test-hooks.ps1 to see which" }

# 3. rules load
Section "rules load"
$cm = Join-Path $ClaudeRoot 'CLAUDE.md'
if ((Test-Path $cm) -and ((Read-Utf8 $cm) -match 'claude-harness:managed')) {
  $n = ([regex]::Matches((Read-Utf8 $cm), '(?m)^@rules/harness/')).Count
  if ($n -ge 13) { Pass "CLAUDE.md imports $n always-loaded rules" }
  else { Warn "CLAUDE.md imports only $n rules (expected >= 13)" }
} else { Fail "CLAUDE.md missing the managed @import block" }

# 4. authorship (recent harness commits)
Section "authorship (last 15 harness commits)"
Push-Location $RepoRoot
$authors = (git log -15 --format='%an <%ae>' 2>$null | Sort-Object -Unique)
$trace   = git log -15 --format='%b' 2>$null | Select-String -Pattern 'Co-Authored-By|Generated with|noreply@anthropic'
Pop-Location
if (($authors | Measure-Object).Count -eq 1 -and $authors -match 'jalakhras') { Pass "all authored as $authors" }
else { Fail "unexpected author(s): $($authors -join '; ')" }
if ($trace) { Fail "Claude attribution trace found in a commit body" } else { Pass "no Claude trace in commit bodies" }

# 5. project rules installed
Section "project rules in their repos"
Get-ChildItem (Join-Path $RepoRoot 'projects') -Filter '*.md' | ForEach-Object {
  $t = Read-Utf8 $_.FullName; $name = $_.BaseName
  $repo = ''; if ($t -match 'repo:\s*(.+)') { $repo = $Matches[1].Trim() }
  if (-not $repo) { return }                         # e.g. a-pine-strategy - nothing to install
  if (-not (Test-Path $repo)) { Warn "${name}: repo not found ($repo)"; return }
  if (Test-Path (Join-Path $repo ".claude\rules\harness-$name.md")) { Pass "${name}: rule installed in repo" }
  else { Warn "${name}: not installed - run install-projects.ps1 (safe when no session is live there)" }
}

# 6. memory hygiene
Section "memory hygiene"
$gl = '<vault>\growth-log.md'
if (Test-Path $gl) {
  $age = (New-TimeSpan -Start (Get-Item $gl).LastWriteTime -End (Get-Date)).Days
  if ($age -le 10) { Pass "growth log present, updated $age d ago" }
  else { Warn "growth log stale ($age d) - a /weekly-review may be due" }
} else { Warn "growth log missing (<vault>\growth-log.md)" }
$vs = '<vault>\wiki\projects\claude-harness\status.md'
if (Test-Path $vs) { Pass "vault status page present" } else { Warn "vault status page missing" }

# verdict
Write-Host ""
if ($fails -eq 0 -and $warns -eq 0) { Write-Host "AUDIT: clean - rules and enforcement are in force." -ForegroundColor Green; exit 0 }
elseif ($fails -eq 0) { Write-Host "AUDIT: $warns warning(s), 0 failures." -ForegroundColor Yellow; exit 0 }
else { Write-Host "AUDIT: $fails failure(s), $warns warning(s) - fix the failures." -ForegroundColor Red; exit 1 }

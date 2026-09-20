#requires -Version 5.1
<#
.SYNOPSIS
  Compare the installed claude-harness files in ~/.claude with the repo and report drift.
.DESCRIPTION
  Read-only. Checks: manifest present; every managed rule exists and matches the
  repo (after token substitution); the @import block is present in ~/.claude/CLAUDE.md.
  Reports OK / DRIFT / MISSING per file. Exit code 0 if clean, 1 if drift found.
#>
[CmdletBinding()]
param(
  [string]$Author = 'jalakhras',
  [string]$Email  = 'you@example.com'
)
$ErrorActionPreference = 'Stop'
$RepoRoot   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ClaudeRoot = Join-Path $env:USERPROFILE '.claude'
$Manifest   = Join-Path $ClaudeRoot '.harness-manifest.json'
$Marker     = '<!-- claude-harness:managed -->'
$issues = 0

function Say([string]$m,[string]$c='Gray'){ Write-Host $m -ForegroundColor $c }
function Norm([string]$s){ ($s -replace "`r`n","`n").TrimEnd() }
function Read-Utf8([string]$path){ [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8) }
function Expand-Tokens([string]$t){ $t.Replace('{{AUTHOR}}',$Author).Replace('{{EMAIL}}',$Email) }

Say "claude-harness doctor" 'Cyan'
if (-not (Test-Path $Manifest)) { Say "MISSING: manifest ($Manifest) - run install.ps1" 'Red'; exit 1 }
$m = Get-Content $Manifest -Raw | ConvertFrom-Json
Say "  installed version: $($m.version), phase: $($m.phase), at $($m.installedAt)`n"

# rule files
Get-ChildItem (Join-Path $RepoRoot 'rules') -Filter '*.md' -File | Sort-Object Name | ForEach-Object {
  $dst = Join-Path $ClaudeRoot "rules\harness\$($_.Name)"
  $want = Norm (Expand-Tokens (Read-Utf8 $_.FullName))
  if (-not (Test-Path $dst)) { Say "  MISSING: $($_.Name)" 'Red'; $script:issues++ }
  elseif ((Norm (Read-Utf8 $dst)) -ne $want) { Say "  DRIFT:   $($_.Name) (edited in ~/.claude - re-run install)" 'Yellow'; $script:issues++ }
  else { Say "  OK:      $($_.Name)" 'DarkGreen' }
}

# CLAUDE.md import block
$cm = Join-Path $ClaudeRoot 'CLAUDE.md'
if (-not (Test-Path $cm)) { Say "  MISSING: CLAUDE.md" 'Red'; $issues++ }
elseif ((Read-Utf8 $cm) -notmatch [regex]::Escape($Marker)) { Say "  DRIFT:   CLAUDE.md missing @import block" 'Yellow'; $issues++ }
else { Say "  OK:      CLAUDE.md @import block present" 'DarkGreen' }

# hooks: files present + registered in settings.json
$manifestPath = Join-Path $RepoRoot 'hooks\hooks.manifest.json'
if (Test-Path $manifestPath) {
  $hm = Get-Content $manifestPath -Raw | ConvertFrom-Json
  $hooksDir = Join-Path $ClaudeRoot 'hooks\harness'
  foreach ($e in $hm.hooks) {
    $dst = Join-Path $hooksDir $e.file
    if (-not (Test-Path $dst)) { Say "  MISSING: hook $($e.file)" 'Red'; $issues++ }
    else { Say "  OK:      hook $($e.file)" 'DarkGreen' }
  }
  $sp = Join-Path $ClaudeRoot 'settings.json'
  $reg = 0
  if (Test-Path $sp) {
    $st = Get-Content $sp -Raw | ConvertFrom-Json
    if ($st.hooks) {
      foreach ($ev in $st.hooks.PSObject.Properties.Name) {
        foreach ($entry in $st.hooks.$ev) {
          foreach ($hk in $entry.hooks) { if ($hk.command -match 'hooks[\\/]+harness') { $reg++ } }
        }
      }
    }
  }
  if ($reg -eq $hm.hooks.Count) { Say "  OK:      $reg/$($hm.hooks.Count) hooks registered in settings.json" 'DarkGreen' }
  else { Say "  DRIFT:   $reg/$($hm.hooks.Count) hooks registered in settings.json" 'Yellow'; $issues++ }
}

# agents present in ~/.claude/agents/
$agentsSrc = Join-Path $RepoRoot 'agents'
if (Test-Path $agentsSrc) {
  Get-ChildItem $agentsSrc -Filter '*.md' -File | ForEach-Object {
    $dst = Join-Path $ClaudeRoot "agents\$($_.Name)"
    if (-not (Test-Path $dst)) { Say "  MISSING: agent $($_.Name)" 'Red'; $script:issues++ }
    else { Say "  OK:      agent $($_.Name)" 'DarkGreen' }
  }
}

# skills: each skill dir's SKILL.md present
$skillsSrc = Join-Path $RepoRoot 'skills'
if (Test-Path $skillsSrc) {
  Get-ChildItem $skillsSrc -Directory | ForEach-Object {
    $dst = Join-Path $ClaudeRoot "skills\$($_.Name)\SKILL.md"
    if (-not (Test-Path $dst)) { Say "  MISSING: skill $($_.Name)" 'Red'; $script:issues++ }
    else { Say "  OK:      skill $($_.Name)" 'DarkGreen' }
  }
}

Say ""
if ($issues -eq 0) { Say "Clean. No drift." 'Green'; exit 0 }
else { Say "$issues issue(s) found. Re-run install.ps1 to restore." 'Yellow'; exit 1 }

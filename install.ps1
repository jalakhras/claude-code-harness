#requires -Version 5.1
<#
.SYNOPSIS
  Install claude-harness into the Claude Code config directory (~/.claude).
.DESCRIPTION
  The repo is the source of truth. This script GENERATES and copies the managed
  files into ~/.claude/, substituting the {{AUTHOR}}/{{EMAIL}} tokens, and wires
  the always-loaded rules into ~/.claude/CLAUDE.md via @import lines.

  Everything it writes is tracked in ~/.claude/.harness-manifest.json for a safe
  doctor/uninstall. It never touches files it does not own.

  M1 scope: CLAUDE.md + rules/. Hooks (M2), agents (M3), skills (M4) are added by
  later phases; this script is structured to extend to them.
.PARAMETER Author
  Commit author name substituted into rules/hooks. Default: jalakhras.
.PARAMETER Email
  Commit author email. Default: you@example.com.
.PARAMETER DryRun
  Print planned actions without writing anything.
.EXAMPLE
  .\install.ps1
  .\install.ps1 -DryRun
  .\install.ps1 -Author "Jane Doe" -Email "jane@example.com"
#>
[CmdletBinding()]
param(
  [string]$Author = 'jalakhras',
  [string]$Email  = 'you@example.com',
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$RepoRoot   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ClaudeRoot = Join-Path $env:USERPROFILE '.claude'
$RulesDst   = Join-Path $ClaudeRoot 'rules\harness'
$Manifest   = Join-Path $ClaudeRoot '.harness-manifest.json'
$Marker     = '<!-- claude-harness:managed -->'
$Version    = (Get-Content (Join-Path $RepoRoot 'VERSION') -Raw).Trim()
$Phase      = 'M5'  # setup.ps1 + docs

function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Do-Write([string]$path, [string]$content) {
  if ($DryRun) { Say "  would write: $path ($($content.Length) chars)" 'DarkYellow'; return }
  $dir = Split-Path -Parent $path
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  # Write UTF-8 without BOM (the ar.json/en.json BOM trap taught us this).
  [System.IO.File]::WriteAllText($path, $content, (New-Object System.Text.UTF8Encoding($false)))
  Say "  wrote: $path" 'DarkGreen'
}

function Expand-Tokens([string]$text) {
  $text.Replace('{{AUTHOR}}', $Author).Replace('{{EMAIL}}', $Email)
}
# PS 5.1 Get-Content -Raw reads as ANSI and mangles UTF-8 (Arabic). Read UTF-8 explicitly.
function Read-Utf8([string]$path) { [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8) }

Say "claude-harness installer v$Version" 'Cyan'
Say "  repo:   $RepoRoot"
Say "  target: $ClaudeRoot"
Say "  author: $Author <$Email>"
if ($DryRun) { Say "  MODE:   DRY RUN (no writes)" 'Yellow' }
Say ""

# --- Backup CLAUDE.md + settings.json before touching -----------------------
$stamp   = Get-Date -Format 'yyyyMMdd-HHmmss'
$backups = @()
foreach ($f in @('CLAUDE.md','settings.json')) {
  $src = Join-Path $ClaudeRoot $f
  if (Test-Path $src) {
    $bak = Join-Path $ClaudeRoot ("backups\{0}.{1}.bak" -f $f, $stamp)
    if (-not $DryRun) {
      New-Item -ItemType Directory -Force -Path (Split-Path $bak) | Out-Null
      Copy-Item $src $bak -Force
    }
    $backups += $bak
    Say "  backup: $f -> $bak" 'DarkGray'
  }
}

# --- 1. Copy global rule files (10-95 + stacks) to ~/.claude/rules/harness/ --
Say "`n[1/4] rules" 'Cyan'
$managed = @()
$globalRules = @()  # order-preserving list for the @import block
Get-ChildItem (Join-Path $RepoRoot 'rules') -Filter '*.md' -File |
  Sort-Object Name | ForEach-Object {
    $content = Expand-Tokens (Read-Utf8 $_.FullName)
    $dst = Join-Path $RulesDst $_.Name
    Do-Write $dst $content
    $managed += $dst
    $globalRules += "rules/harness/$($_.Name)"
  }
# stacks (copied but NOT globally imported; a project's .claude/CLAUDE.md imports them)
$stackDir = Join-Path $RepoRoot 'rules\stacks'
if (Test-Path $stackDir) {
  Get-ChildItem $stackDir -Filter '*.md' -File -Recurse | ForEach-Object {
    $rel = $_.FullName.Substring($stackDir.Length).TrimStart('\','/')
    $dst = Join-Path (Join-Path $RulesDst 'stacks') $rel
    Do-Write $dst (Expand-Tokens (Read-Utf8 $_.FullName))
    $managed += $dst
  }
}

# --- 2. Generate ~/.claude/CLAUDE.md (repo body + @import block) -------------
Say "`n[2/4] CLAUDE.md (with @import block)" 'Cyan'
$body = Expand-Tokens (Read-Utf8 (Join-Path $RepoRoot 'CLAUDE.md'))
$importBlock = @()
$importBlock += ""
$importBlock += "## Always-loaded rules (managed) $Marker"
$importBlock += ""
$importBlock += "> Imported so they load every session. Edit the repo, not this file."
$importBlock += ""
foreach ($r in $globalRules) { $importBlock += "@$r" }
$claudeMd = $body.TrimEnd() + "`n" + ($importBlock -join "`n") + "`n"
Do-Write (Join-Path $ClaudeRoot 'CLAUDE.md') $claudeMd

# --- 2b. Hooks: copy files + register in settings.json -----------------------
Say "`n[hooks] copy + register" 'Cyan'
$HooksSrc = Join-Path $RepoRoot 'hooks'
$HooksDst = Join-Path $ClaudeRoot 'hooks\harness'
if (Test-Path $HooksSrc) {
  # copy every hook file, substituting {{AUTHOR}}/{{EMAIL}} (git-author.js needs it)
  Get-ChildItem $HooksSrc -File -Recurse | ForEach-Object {
    $rel = $_.FullName.Substring($HooksSrc.Length).TrimStart('\','/')
    $dst = Join-Path $HooksDst $rel
    Do-Write $dst (Expand-Tokens (Read-Utf8 $_.FullName))
    $managed += $dst
  }
  # register in settings.json via the Node merger (reliable JSON)
  $merger = Join-Path $RepoRoot 'scripts\merge-hooks.js'
  $hooksManifest = Join-Path $HooksSrc 'hooks.manifest.json'
  if ($DryRun) {
    Say "  would run: node merge-hooks.js (register 13 hooks)" 'DarkYellow'
    & node $merger $ClaudeRoot $HooksDst $hooksManifest --dry-run
  } else {
    & node $merger $ClaudeRoot $HooksDst $hooksManifest
    if ($LASTEXITCODE -ne 0) { throw "merge-hooks.js failed (exit $LASTEXITCODE)" }
  }
}

# --- 2c. Agents: copy to ~/.claude/agents/ (skip foreign name collisions) ----
Say "`n[agents] copy" 'Cyan'
$AgentsSrc = Join-Path $RepoRoot 'agents'
$AgentsDst = Join-Path $ClaudeRoot 'agents'
if (Test-Path $AgentsSrc) {
  $ours = @{}
  foreach ($p in $managed) { $ours[$p] = $true }
  Get-ChildItem $AgentsSrc -Filter '*.md' -File | ForEach-Object {
    $dst = Join-Path $AgentsDst $_.Name
    # Do not overwrite a pre-existing agent we do not manage.
    if ((Test-Path $dst) -and -not $ours.ContainsKey($dst) -and ($managed -notcontains $dst)) {
      # allow overwrite only if a previous manifest marked it ours
      $prevMine = $false
      if (Test-Path $Manifest) { $prevMine = ((Read-Utf8 $Manifest) -match [regex]::Escape($dst.Replace('\','\\'))) }
      if (-not $prevMine) { Say "  SKIP (foreign): $($_.Name) already exists and is not harness-managed" 'Yellow'; return }
    }
    Do-Write $dst (Expand-Tokens (Read-Utf8 $_.FullName))
    $managed += $dst
  }
}

# --- 2d. Skills: copy each skill dir to ~/.claude/skills/<name>/ -------------
Say "`n[skills] copy" 'Cyan'
$SkillsSrc = Join-Path $RepoRoot 'skills'
$SkillsDst = Join-Path $ClaudeRoot 'skills'
$prevManaged = @()
if (Test-Path $Manifest) {
  try { $prevManaged = (Get-Content $Manifest -Raw | ConvertFrom-Json).managed } catch { $prevManaged = @() }
}
if (Test-Path $SkillsSrc) {
  Get-ChildItem $SkillsSrc -Directory | ForEach-Object {
    $skillName = $_.Name
    # foreign-collision guard: skip a pre-existing skill we do not manage.
    # Compare parsed manifest paths (JSON), not regex on escaped backslashes.
    $dstDir = Join-Path $SkillsDst $skillName
    $prevMine = $false
    # (a) manifest lists a path under this skill, or (b) the installed SKILL.md
    # self-identifies with our origin marker — robust against a clobbered manifest.
    foreach ($p in $prevManaged) { if ($p -like (Join-Path $dstDir '*')) { $prevMine = $true; break } }
    $instSkill = Join-Path $dstDir 'SKILL.md'
    if (-not $prevMine -and (Test-Path $instSkill)) {
      if ((Read-Utf8 $instSkill) -match 'origin:\s*claude-harness') { $prevMine = $true }
    }
    if ((Test-Path $dstDir) -and -not $prevMine) {
      Say "  SKIP (foreign): skill '$skillName' already exists and is not harness-managed" 'Yellow'; return
    }
    Get-ChildItem $_.FullName -File -Recurse | Where-Object {
      # never ship build junk into ~/.claude
      $_.FullName -notmatch '\\__pycache__\\' -and $_.Extension -notin @('.pyc', '.pyo')
    } | ForEach-Object {
      $rel = $_.FullName.Substring($SkillsSrc.Length).TrimStart('\','/')
      $dst = Join-Path $SkillsDst $rel
      # scripts/binaries copied verbatim; only .md carries tokens
      if ($_.Extension -eq '.md') { Do-Write $dst (Expand-Tokens (Read-Utf8 $_.FullName)) }
      else {
        if (-not $DryRun) {
          $d = Split-Path -Parent $dst
          if (-not (Test-Path $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
          Copy-Item $_.FullName $dst -Force
          Say "  copied: $dst" 'DarkGreen'
        } else { Say "  would copy: $dst" 'DarkYellow' }
      }
      $managed += $dst
    }
  }
}

# --- 3. Manifest (for doctor / uninstall) -----------------------------------
Say "`n[3/4] manifest" 'Cyan'
$manifestObj = [ordered]@{
  version    = $Version
  installedAt= (Get-Date).ToString('o')
  author     = $Author
  email      = $Email
  phase      = $Phase
  managed    = $managed
  claudeMd   = (Join-Path $ClaudeRoot 'CLAUDE.md')
  settings   = (Join-Path $ClaudeRoot 'settings.json')
  backups    = $backups
}
Do-Write $Manifest ($manifestObj | ConvertTo-Json -Depth 5)

# --- 4. Status report to the Obsidian vault ---------------------------------
Say "`n[4/4] vault status" 'Cyan'
$vault = '<vault>\wiki\projects\claude-harness\status.md'
if (Test-Path (Split-Path $vault)) {
  $line = "`n- **{0}** - install.ps1 v{1} ran ({2} files) as {3}. Phase {4}.`n" -f `
    (Get-Date -Format 'yyyy-MM-dd HH:mm'), $Version, $managed.Count, $Author, $Phase
  if ($DryRun) { Say "  would append status line to $vault" 'DarkYellow' }
  else { Add-Content -Path $vault -Value $line -Encoding UTF8; Say "  appended status: $vault" 'DarkGreen' }
} else { Say "  (vault path not found; skipped)" 'DarkGray' }

Say "`nDone. $($managed.Count) files managed." 'Green'
if ($DryRun) { Say "Dry run only - nothing was written." 'Yellow' }
else {
  Say "Verify with: .\doctor.ps1" 'Gray'
  # Nudge the media/local-LLM prerequisites if they are not provisioned yet.
  if (-not (Get-Command ollama -ErrorAction SilentlyContinue) -and
      -not (Test-Path (Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'))) {
    Say "For free local video analysis (media-ingest), run: .\setup.ps1" 'Cyan'
  }
}

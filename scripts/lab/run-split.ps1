# Splits the heavy suites across THIS machine and lab-worker1 and runs both halves at the same time,
# then prints one merged verdict. The value is the parallelism: wall clock ~ the longer half, not the sum.
#
#   powershell -ExecutionPolicy Bypass -File scripts\lab\run-split.ps1                       # byType: .NET here, Playwright on the worker
#   ... run-split.ps1 -Mode byType -DotnetOn worker                                          # the other way round
#   ... run-split.ps1 -Mode byProject                                                        # .NET projects and Playwright shards on both
#   ... run-split.ps1 -Mode byProject -ShardsTotal 3 -LocalShards 1,2                         # weight Playwright towards this machine
#
# It reuses what exists: the worker half goes through run-on-worker.ps1 (sync, fingerprint, redaction,
# evidence, orphan cleanup); the local half runs the local-tests runners directly. split_plan.py decides
# the split and merges the results (unit-tested). The local Playwright half runs with CI=true for parity
# with the worker (parallel workers, retries); a normal local run is not affected.
#
# Fallback: worker unreachable at the start -> everything runs here, one suite after the other, and the
# reason is printed. A worker step that could not run (run-on-worker exit 3) is re-run here afterwards; a
# step that RAN on the worker and failed is reported, never re-run.
# Exit: 0 passed and a gate · 1 a part failed / a project counted twice or missing · 4 passed, not a gate.
param(
    [ValidateSet('byType', 'byProject')]
    [string]$Mode = 'byType',
    [ValidateSet('local', 'worker')]
    [string]$DotnetOn = 'local',            # byType: where .NET runs; Playwright runs on the other side
    [ValidateSet('local', 'worker')]
    [string]$HeavyOn = 'local',             # byProject: which side takes the heavier .NET bin (EFCore) - measured 2026-10-13
    [int]$ShardsTotal = 3,                  # byProject: Playwright --shard=k/N (worker carries N-1: it runs Playwright faster)
    [string]$LocalShards = '1',             # byProject: the shards run here, e.g. "1" or "1,2"
    # No double quotes: PowerShell 5.1 does not escape them for a native command (python), so the
    # filter would arrive altered — and with --allow-empty a share could then pass having matched nothing.
    [ValidateScript({ $_ -notmatch '"' })]
    [string]$Filter = '',
    [ValidateScript({ $_ -notmatch '"' })]
    [string]$PwArgs = '--project=desktop --project=mobile',
    [int]$ProgressInterval = 30,
    [string]$Repo = 'D:\Projects\your-project',
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')]
    [string]$Worker = 'lab-worker1',
    [string]$EvidenceRoot = 'D:\Projects\evidence',
    [string]$Phase = '',
    # test seam: the script that carries a worker step (default run-on-worker.ps1)
    [string]$WorkerScript = ''
)
# Continue, not Stop: native tools write warnings to stderr (see run-on-worker.ps1). Exit codes are checked.
$ErrorActionPreference = 'Continue'
$sw = [Diagnostics.Stopwatch]::StartNew()
$Lab = $PSScriptRoot
$Runners = Join-Path (Split-Path -Parent (Split-Path -Parent $Lab)) 'skills\local-tests\scripts'
$SplitPlan = Join-Path $Lab 'split_plan.py'   # not $Plan: PowerShell names are case-insensitive and $plan holds the plan
$Ssh = if (Test-Path "$env:WINDIR\System32\OpenSSH\ssh.exe") { "$env:WINDIR\System32\OpenSSH\ssh.exe" } else { 'ssh' }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$Utf8 = New-Object Text.UTF8Encoding $false

# --- output: one prefixed, password-safe stream, kept for summary.txt --------------------------------------
$log = New-Object Collections.Generic.List[string]
. (Join-Path $Lab 'lab-common.ps1')   # Hide, Get-TreeIdentity
if (-not $WorkerScript) { $WorkerScript = Join-Path $Lab 'run-on-worker.ps1' }
function Say([string]$s) { $s = Hide $s; Write-Host $s; $log.Add($s) }

# --- evidence folder: <EvidenceRoot>\<Phase>\split\<stamp>\ ----------------------------------------------
if ($EvidenceRoot -and (Test-Path $EvidenceRoot) -and -not $Phase) {
    $Phase = Get-ChildItem $EvidenceRoot -Directory | Where-Object Name -match '^P\d+$' |
        Sort-Object { [int]$_.Name.Substring(1) } | Select-Object -Last 1 -ExpandProperty Name
}
$out = if ($EvidenceRoot -and $Phase -and (Test-Path $EvidenceRoot)) { Join-Path $EvidenceRoot "$Phase\split\$stamp" }
       else { Join-Path $env:TEMP "run-split-$stamp" }
$runDir = Join-Path $out '_run'
New-Item -ItemType Directory -Force $runDir | Out-Null

# --- identity of the local tree: the local half tests the LIVE tree (tracked AND untracked files), so a
# change mid-run voids the gate ------------------------------------------------------------------------------
function Get-Identity { Get-TreeIdentity $Repo $runDir }
$id0 = Get-Identity

# --- what to run where ------------------------------------------------------------------------------------
$projects = @(& python $SplitPlan discover --repo $Repo --runners $Runners 2>$null | Where-Object { $_ })
if ($projects.Count -eq 0) { Say '[run-split] no test project found'; exit 1 }
$expected = ($projects | ForEach-Object { [IO.Path]::GetFileNameWithoutExtension($_) }) -join ','

& $Ssh -o BatchMode=yes -o ConnectTimeout=5 $Worker true 2>$null
$workerUp = ($LASTEXITCODE -eq 0)
if ($workerUp) {
    $planJson = & python $SplitPlan plan --mode $Mode --projects ($projects -join ',') --dotnet-on $DotnetOn `
        --heavy-on $HeavyOn --shards-total $ShardsTotal --local-shards $LocalShards 2>&1
    if ($LASTEXITCODE -ne 0) { Say "[run-split] $planJson"; exit 1 }
    $plan = $planJson | ConvertFrom-Json
} else {
    Say "[run-split] worker '$Worker' unreachable -> everything runs on $env:COMPUTERNAME, one suite after the other"
    $plan = [pscustomobject]@{
        local  = [pscustomobject]@{ dotnet = $projects; playwright = @($null) }
        worker = [pscustomobject]@{ dotnet = @(); playwright = @() } }
}

function Get-Steps($half) {
    $steps = @()
    if (@($half.dotnet).Count -gt 0) { $steps += [pscustomobject]@{ kind = 'dotnet'; projects = @($half.dotnet); shard = $null } }
    foreach ($s in @($half.playwright)) { $steps += [pscustomobject]@{ kind = 'playwright'; projects = @(); shard = $s } }
    $steps
}
function Get-StepName($st) { if ($st.kind -eq 'dotnet') { 'dotnet' } elseif ($st.shard) { "playwright $($st.shard)" } else { 'playwright' } }
function Quote([string]$s) { "'" + ($s -replace "'", "''") + "'" }

# The child scripts print "[split-step] <name> exit=<n>" after each step; the verdict is read from those.
function New-LocalScript($steps, [string]$tag) {
    $lines = @('$ErrorActionPreference = ''Continue''')
    foreach ($st in $steps) {
        $name = Get-StepName $st
        $ev = Join-Path $out "$tag\$(($name -replace '[ /]', '-'))"
        if ($st.kind -eq 'dotnet') {
            $a = @((Join-Path $Runners 'dotnet-run.py'), '--cwd', $Repo, '--progress', '--progress-interval', "$ProgressInterval", '--results-dir', $ev)
            foreach ($p in $st.projects) { $a += @('--project', $p) }
            # a share may match nothing under -Filter; the merge checks the whole
            if ($Filter) { $a += @('--filter', $Filter, '--allow-empty') }
            $lines += "& python $(($a | ForEach-Object { Quote $_ }) -join ' ') 2>&1 | ForEach-Object { `"`$_`" }"
        } else {
            $a = @((Join-Path $Runners 'pw-run.py'), '--cwd', (Join-Path $Repo 'angular'), '--no-llm', '--progress', '--progress-interval', "$ProgressInterval",
                   '--html-report', (Join-Path $ev 'report'), '--artifacts-dir', $ev, '--') + (($PwArgs -split '\s+') | Where-Object { $_ })
            if ($st.shard) { $a += "--shard=$($st.shard)" }
            $lines += '$env:CI = ''true'''
            $lines += "& python $(($a | ForEach-Object { Quote $_ }) -join ' ') 2>&1 | ForEach-Object { `"`$_`" }"
            $lines += 'Remove-Item Env:CI -ErrorAction SilentlyContinue'
        }
        $lines += "`"[split-step] $name exit=`$LASTEXITCODE`""
    }
    $lines -join "`r`n"
}
function New-WorkerScript($steps) {
    # The step script is called IN-PROCESS (& script.ps1 -Param 'literal'), not through powershell -File:
    # PowerShell parameters bind the single-quoted literals exactly, with no native-argument quoting.
    $common = "-Repo $(Quote $Repo) -Worker $Worker -NoFallback -ProgressInterval $ProgressInterval" +
              $(if ($EvidenceRoot) { " -EvidenceRoot $(Quote $EvidenceRoot)" } else { '' }) + $(if ($Phase) { " -Phase $(Quote $Phase)" } else { '' })
    $lines = @('$ErrorActionPreference = ''Continue''')
    foreach ($st in $steps) {
        $name = Get-StepName $st
        if ($st.kind -eq 'dotnet') {
            $extra = "-Suite dotnet -Projects @($(($st.projects | ForEach-Object { Quote $_ }) -join ','))" + $(if ($Filter) { " -Filter $(Quote $Filter) -AllowEmpty" } else { '' })
        } else {
            $pa = $PwArgs + $(if ($st.shard) { " --shard=$($st.shard)" } else { '' })
            $extra = "-Suite playwright -PwArgs $(Quote $pa)"
        }
        $lines += "`$global:LASTEXITCODE = 99   # a step that dies without setting an exit code is not a pass"
        $lines += "& $(Quote $WorkerScript) $common $extra 2>&1 | ForEach-Object { `"`$_`" }"
        $lines += "`"[split-step] $name exit=`$LASTEXITCODE`""
    }
    $lines -join "`r`n"
}

# --- run the halves at the same time, streaming both, prefixed -------------------------------------------
function Start-Half([string]$tag, [string]$script) {
    $f = Join-Path $runDir "$tag.ps1"; [IO.File]::WriteAllText($f, $script, $Utf8)
    $o = Join-Path $runDir "$tag.out"; $e = Join-Path $runDir "$tag.err"
    $p = Start-Process powershell -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $f `
        -RedirectStandardOutput $o -RedirectStandardError $e -WindowStyle Hidden -PassThru
    $null = $p.Handle   # cache the handle now, or .ExitCode reads empty after the process ends
    [pscustomobject]@{ tag = $tag; proc = $p; out = $o; err = $e; seen = 0; t0 = Get-Date; t1 = $null }
}
function Read-New($h) {
    if (-not (Test-Path $h.out)) { return }
    $fs = [IO.File]::Open($h.out, 'Open', 'Read', 'ReadWrite')
    try { $text = (New-Object IO.StreamReader($fs)).ReadToEnd() } finally { $fs.Dispose() }
    $lines = $text -split "`r?`n"
    $complete = $lines.Count - 1   # the last piece is '' after a newline, or a line still being written
    for ($i = $h.seen; $i -lt $complete; $i++) { if ($lines[$i] -ne '') { Say "[$($h.tag)] $($lines[$i])" } }
    $h.seen = [math]::Max($h.seen, $complete)
}
function Wait-Halves($halves) {
    while (@($halves | Where-Object { -not $_.proc.HasExited }).Count -gt 0) {
        foreach ($h in $halves) { Read-New $h; if ($h.proc.HasExited -and -not $h.t1) { $h.t1 = Get-Date } }
        Start-Sleep -Milliseconds 700
    }
    foreach ($h in $halves) { $h.proc.WaitForExit(); if (-not $h.t1) { $h.t1 = Get-Date }; Read-New $h }
}
function Get-StepExits($h) {
    $exits = @{}
    foreach ($l in (Get-Content -LiteralPath $h.out -ErrorAction SilentlyContinue)) {
        if ($l -match '^\[split-step\] (.+) exit=(-?\d+)$') { $exits[$Matches[1]] = [int]$Matches[2] }
    }
    $exits
}

$localSteps = @(Get-Steps $plan.local)
$workerSteps = @(Get-Steps $plan.worker)
Say ("[run-split] {0} tree {1} | mode {2} | local: {3} | worker: {4}" -f $stamp, $id0, $Mode,
    (($localSteps | ForEach-Object { Get-StepName $_ }) -join ', '), (($workerSteps | ForEach-Object { Get-StepName $_ }) -join ', '))
$halves = @()
if ($localSteps.Count) { $halves += Start-Half 'local' (New-LocalScript $localSteps 'local') }
if ($workerSteps.Count) { $halves += Start-Half 'worker' (New-WorkerScript $workerSteps) }
# The orchestrator's own Ctrl+C must not leave the halves running.
try { Wait-Halves $halves }
finally {
    foreach ($h in $halves) { if (-not $h.proc.HasExited) { Say "[run-split] stopping the $($h.tag) half"; taskkill /PID $h.proc.Id /T /F 2>$null | Out-Null } }
}

# --- worker steps that could not run (exit 3) are run here afterwards --------------------------------------
$parts = @()
foreach ($h in $halves) {
    $exits = Get-StepExits $h
    $text = Hide ((Get-Content -LiteralPath $h.out -Raw -ErrorAction SilentlyContinue) + '')
    # Judge every PLANNED step, not the lines that happen to be there: a half that died before printing
    # a step line must fail the run, never vanish from the merge (a false pass).
    $planned = @(if ($h.tag -eq 'local') { $localSteps } else { $workerSteps })
    $missing = @($planned | Where-Object { -not $exits.ContainsKey((Get-StepName $_)) })
    $lostHere = @($planned | Where-Object { $h.tag -eq 'worker' -and $exits[(Get-StepName $_)] -eq 3 })
    $ranExits = @($planned | Where-Object { $exits.ContainsKey((Get-StepName $_)) -and $_ -notin $lostHere } | ForEach-Object { $exits[(Get-StepName $_)] })
    $code = if ($missing.Count -or @($ranExits | Where-Object { $_ -notin 0, 4 }).Count) { 1 } elseif ($ranExits -contains 4) { 4 } else { 0 }
    if ($missing.Count) { Say "[run-split] the $($h.tag) half never reported: $(($missing | ForEach-Object { Get-StepName $_ }) -join ', ') (exit $($h.proc.ExitCode)) -> failed" }
    $evidence = if ($h.tag -eq 'local') { Join-Path $out 'local' } else {
        ((Select-String -LiteralPath $h.out -Pattern 'evidence \(worker\): (.+)$' -AllMatches).Matches | ForEach-Object { $_.Groups[1].Value }) -join ' ; ' }
    # The worker re-syncs per step: if two steps tested different trees, the half is not a gate.
    $gate = $null
    if ($h.tag -eq 'worker') {
        $fps = @([regex]::Matches($text, 'fingerprint MATCH (\w+)') | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique)
        if ($fps.Count -gt 1) { $gate = "NOT A GATE (the worker steps tested different trees: $($fps -join ', '))" }
    }
    if ($lostHere.Count -lt $planned.Count) {
        # gate null: the worker's comes from its own output (parsed in merge), the local one is set below
        $parts += [pscustomobject]@{ side = $h.tag; exit = $code; seconds = [int]($h.t1 - $h.t0).TotalSeconds; text = $text; evidence = $evidence; gate = $gate
            pw_steps = @($planned | Where-Object { $_.kind -eq 'playwright' -and $_ -notin $lostHere }).Count }
    }
    if ($h.tag -eq 'worker') {
        $lost = $lostHere
        if ($lost.Count) {
            Say "[run-split] worker could not run: $(($lost | ForEach-Object { Get-StepName $_ }) -join ', ') -> running here instead"
            $fb = Start-Half 'local-fallback' (New-LocalScript $lost 'local-fallback')
            try { Wait-Halves @($fb) } finally { if (-not $fb.proc.HasExited) { taskkill /PID $fb.proc.Id /T /F 2>$null | Out-Null } }
            $fe = Get-StepExits $fb
            $fcode = if (@($fe.Values | Where-Object { $_ -notin 0, 4 }).Count -or $fe.Count -lt $lost.Count) { 1 } else { 0 }
            $parts += [pscustomobject]@{ side = 'local-fallback'; exit = $fcode; seconds = [int]($fb.t1 - $fb.t0).TotalSeconds
                text = Hide ((Get-Content -LiteralPath $fb.out -Raw -ErrorAction SilentlyContinue) + ''); evidence = (Join-Path $out 'local-fallback'); gate = $null
                pw_steps = @($lost | Where-Object { $_.kind -eq 'playwright' }).Count }
        }
    }
}

# The local half(s) tested the live tree: if it changed while they ran, they are not a gate.
$id1 = Get-Identity
foreach ($p in $parts) {
    if ($p.side -like 'local*') {
        $p.gate = if ($id1 -eq $id0) { "local tree $id0" } else { "NOT A GATE (the working tree changed during the run: $id0 -> $id1)" }
    }
}

# --- one merged verdict ------------------------------------------------------------------------------------
$partsFile = Join-Path $runDir 'parts.json'
[IO.File]::WriteAllText($partsFile, (ConvertTo-Json @($parts) -Depth 4), $Utf8)
$merged = & python $SplitPlan merge $partsFile --expected-projects $expected 2>&1
$rc = $LASTEXITCODE
$merged | ForEach-Object { Say "$_" }
Say ("[run-split] {0} finished in {1:N0}s (wall), exit={2} | evidence {3}" -f $stamp, $sw.Elapsed.TotalSeconds, $rc, $out)
[IO.File]::WriteAllLines((Join-Path $out 'summary.txt'), [string[]]$log, $Utf8)
exit $rc

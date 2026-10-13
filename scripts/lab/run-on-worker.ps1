# Syncs the working tree to the lab worker, runs a suite there with live progress, verifies the tree
# fingerprint, and copies the evidence back. The main machine stays free meanwhile.
#
#   powershell -ExecutionPolicy Bypass -File scripts\lab\run-on-worker.ps1 -Suite dotnet
#   ... -Suite dotnet -Filter "FullyQualifiedName~AdministratorRole"
#   ... -Suite playwright -PwArgs "--project=desktop return-to"
#   ... -Suite playwright -Headed            # with a display (xvfb on the worker)
#   ... -Suite playwright -Headed -OnScreen  # on the worker's own screen (owner logged in)
#
# Fingerprint (): the worker recomputes the tree fingerprint from its files and it must equal the
# one sync-to-worker.ps1 computed here. A mismatch, or -NoSync, means the run is NOT a gate — said on
# the first and last line. Evidence (summary, one .trx per test project, the Playwright HTML report
# and traces) lands in <EvidenceRoot>\<Phase>\worker\<timestamp>\ (or \local\ on fallback).
#
# Fallback: the worker path is for speed, never a single point of failure. If the worker cannot be
# reached, the sync fails, the runners cannot be refreshed, or ssh reports a transport error (255),
# the suite runs LOCALLY instead and the reason is printed. A suite that actually RAN on the worker
# and failed is reported as a failure — never silently re-run locally. -NoFallback requires the worker.
# See scripts\lab\README.md for the worker contract and the  self-repair scope.
param(
    [ValidateSet('dotnet', 'playwright', 'all')]
    [string]$Suite = 'dotnet',
    [string]$Filter = '',
    # test .csproj paths relative to the repo; empty = every test project (run-split passes a share)
    [string[]]$Projects = @(),
    [switch]$AllowEmpty,       # run-split: this share may match nothing under -Filter (the merge checks the whole)
    [string]$PwArgs = '--project=desktop --project=mobile',
    [switch]$NoSync,
    [switch]$NoFallback,
    [switch]$Headed,
    [switch]$OnScreen,
    [int]$ProgressInterval = 30,
    [string]$Repo = 'D:\Projects\your-project',
    # a hostname/alias only: a leading '-' would be read by ssh as an option
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')]
    [string]$Worker = 'lab-worker1',
    [string]$EvidenceRoot = 'D:\Projects\evidence',
    [string]$Phase = ''          # default: the highest P<n> folder under EvidenceRoot
)
# Continue, not Stop: native tools (git, ssh) write warnings to stderr, and under Stop PowerShell 5.1
# turns the first one into a terminating error — that is how every worker run used to "fail to sync"
# and fall back. Each native call checks its exit code instead.
$ErrorActionPreference = 'Continue'
$sw = [Diagnostics.Stopwatch]::StartNew()
# `powershell -File … -Projects a,b` binds one string "a,b"; accept both forms.
$Projects = @($Projects | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # harness repo root
$Runners  = Join-Path $RepoRoot 'skills\local-tests\scripts'
# Use Windows OpenSSH explicitly: Git's bundled ssh.exe cannot see the Windows
# ssh-agent that holds the passphrase-protected lab key and is rejected (publickey).
$Ssh = if (Test-Path "$env:WINDIR\System32\OpenSSH\ssh.exe") { "$env:WINDIR\System32\OpenSSH\ssh.exe" } else { 'ssh' }
$Scp = if (Test-Path "$env:WINDIR\System32\OpenSSH\scp.exe") { "$env:WINDIR\System32\OpenSSH\scp.exe" } else { 'scp' }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$branchHead = "{0}@{1}" -f (git -C $Repo branch --show-current), (git -C $Repo rev-parse --short HEAD)
$log = New-Object Collections.Generic.List[string]
. (Join-Path $PSScriptRoot 'lab-common.ps1')   # Hide (second layer of password masking), Get-WorkerLockScript
function Say([string]$s) { $s = Hide $s; Write-Host $s; $log.Add($s) }

# --- evidence folder ------------------------------------------------------------------------------
$evidenceBase = $null
if ($EvidenceRoot -and (Test-Path $EvidenceRoot)) {
    if (-not $Phase) {
        $Phase = Get-ChildItem $EvidenceRoot -Directory | Where-Object Name -match '^P\d+$' |
            Sort-Object { [int]$_.Name.Substring(1) } | Select-Object -Last 1 -ExpandProperty Name
    }
    if ($Phase) { $evidenceBase = Join-Path $EvidenceRoot $Phase }
}

function Save-Evidence([string]$where, [string]$dir) {
    if (-not $dir) { return }
    New-Item -ItemType Directory -Force $dir | Out-Null
    # $log holds only lines that already went through Hide (see Say).
    [IO.File]::WriteAllLines((Join-Path $dir 'summary.txt'), [string[]]$log, (New-Object Text.UTF8Encoding $false))
    Write-Host "[run-on-worker] evidence ($where): $dir"
}

function Test-WorkerUp([string]$w) {
    # A quick, key-only probe; 5 s so a sleeping worker does not stall the run.
    & $Ssh -o BatchMode=yes -o ConnectTimeout=5 $w true 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Invoke-Local([string]$dir) {
    # Run the same local-tests runners on THIS machine, the way they ran before the worker existed.
    $rc = 0
    if ($Suite -eq 'dotnet' -or $Suite -eq 'all') {
        Say "===== .NET locally on $env:COMPUTERNAME ====="
        $a = @((Join-Path $Runners 'dotnet-run.py'), '--cwd', $Repo, '--progress', '--progress-interval', $ProgressInterval)
        if ($Filter) { $a += @('--filter', $Filter) }
        foreach ($p in $Projects) { $a += @('--project', $p) }
        if ($AllowEmpty) { $a += '--allow-empty' }
        if ($dir) { $a += @('--results-dir', (Join-Path $dir 'dotnet')) }
        & python @a 2>&1 | ForEach-Object { Say "$_" }; if ($LASTEXITCODE -ne 0) { $rc = 1 }
    }
    if ($Suite -eq 'playwright' -or $Suite -eq 'all') {
        Say "===== Playwright locally on $env:COMPUTERNAME ====="
        $pw = @((Join-Path $Runners 'pw-run.py'), '--cwd', (Join-Path $Repo 'angular'), '--no-llm', '--progress',
                '--progress-interval', $ProgressInterval)
        if ($dir) { $pw += @('--html-report', (Join-Path $dir 'playwright\report'), '--artifacts-dir', (Join-Path $dir 'playwright')) }
        $pw += '--'   # ends pw-run's own options; "--project=…" is not taken into the REMAINDER without it
        $pw += (($PwArgs -split '\s+') | Where-Object { $_ })
        if ($Headed) { $pw += '--headed' }
        & python @pw 2>&1 | ForEach-Object { Say "$_" }; if ($LASTEXITCODE -ne 0) { $rc = 1 }
    }
    return $rc
}

# --- decide whether the worker can carry this run -------------------------------------------------
$infra = $null
$mainFp = $null; $identity = $null
if (-not (Test-WorkerUp $Worker)) { $infra = "worker '$Worker' unreachable" }

# One run at a time: reserve the worker (an atomic lock) BEFORE syncing, so a second session can never
# rewrite ~/work/<project> under a run in progress. Released by the run itself (trap) or below.
$lockHeld = $false
function Invoke-WorkerLock([string]$action) {
    (Get-WorkerLockScript $stamp $action) | & $Ssh -o BatchMode=yes -o ConnectTimeout=5 $Worker bash -s 2>$null |
        Where-Object { $_ -match '^LOCK=' } | Select-Object -Last 1
}
if (-not $infra) {
    $lock = Invoke-WorkerLock 'acquire'
    if ($lock -match '^LOCK=ok') {
        $lockHeld = $true
        if ($lock -match '^LOCK=ok-stale (\S+)') { Write-Host "[run-on-worker] took over a stale worker lock (holder $($Matches[1]) is gone)" }
    } elseif ($lock -match '^LOCK=busy (\S+)') { $infra = "worker '$Worker' busy (run $($Matches[1]) from another session holds it)" }
    else { $infra = "worker '$Worker' lock check failed" }
}

if (-not $infra -and -not $NoSync) {
    $syncOut = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'sync-to-worker.ps1') -Repo $Repo -Worker $Worker 2>&1 |
        ForEach-Object { "$_" } | Where-Object { $_ -notmatch 'LF will be replaced by CRLF' }
    $syncRc = $LASTEXITCODE
    $syncOut | Where-Object { $_ -notmatch '^(FINGERPRINT|IDENTITY)=' } | ForEach-Object { Say $_ }
    foreach ($l in $syncOut) {
        if ($l -match '^FINGERPRINT=(\w+)') { $mainFp = $Matches[1] }
        if ($l -match '^IDENTITY=(.+)$') { $identity = $Matches[1] }
    }
    if ($syncRc -ne 0 -or -not $mainFp) { $infra = "sync failed (exit $syncRc)" }
    elseif ($lockHeld) {
        # heartbeat: a long sync must not let the lock look dead to another session
        $hb = Invoke-WorkerLock 'refresh'
        if ($hb -notmatch '^LOCK=refreshed') { $lockHeld = $false; $infra = "lost the worker lock during the sync ($hb)" }
    }
}

if (-not $infra) {
    # Always refresh the worker's copy of the runners, so a runner fix reaches the worker.
    & $Ssh -o BatchMode=yes $Worker 'mkdir -p ~/lab/runners' 2>$null
    & $Scp -q -o BatchMode=yes (Join-Path $Runners 'dotnet-run.py') (Join-Path $Runners 'pw-run.py') (Join-Path $Runners 'pytest-run.py') `
        (Join-Path $PSScriptRoot 'redact.py') "${Worker}:lab/runners/"
    if ($LASTEXITCODE -ne 0) { $infra = "could not refresh worker runners (scp exit $LASTEXITCODE)" }
}

# --- run on the worker ----------------------------------------------------------------------------
if (-not $infra) {
    function ConvertTo-B64([string]$s) { [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($s)) }
    $header = @(
        ':',
        "SUITE='$Suite'", "INTERVAL=$ProgressInterval", "STAMP='$stamp'",
        "FILTER=`$(echo '$(ConvertTo-B64 $Filter)' | base64 -d)",
        "PW_ARGS=`$(echo '$(ConvertTo-B64 $PwArgs)' | base64 -d)",
        "PROJECTS_TEXT=`$(echo '$(ConvertTo-B64 (($Projects | ForEach-Object { $_ -replace '\\', '/' }) -join "`n"))' | base64 -d)",
        "ALLOW_EMPTY=$([int][bool]$AllowEmpty)", "HEADED=$([int][bool]$Headed)", "ONSCREEN=$([int][bool]$OnScreen)"
    ) -join "`n"
    # Single-quoted: nothing below is expanded by PowerShell. The last line is a comment because
    # PowerShell appends CRLF to piped stdin and a CR on a real command breaks it.
    $body = @'
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH" DOTNET_NOLOGO=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
# A reachable but mis-configured worker must FALL BACK (exit 255, the infra sentinel), never
# masquerade as a failed suite (the runner's own exit 1).
command -v python3 >/dev/null 2>&1 || exit 255
cd ~/work/project || exit 255
[ -f ~/lab/runners/dotnet-run.py ] && [ -f ~/lab/runners/pw-run.py ] && [ -f ~/lab/runners/redact.py ] || exit 255
[ -r ~/lab/sql/.env ] || exit 255

# --- leftovers: a run whose ssh connection is gone but whose process group survived -------------
# Each run records "<process group> <sshd pid>" in ~/lab/runs/<stamp>.run. Only groups whose own
# connection has ended are stopped, so a run another session started right now is never touched.
mkdir -p ~/lab/runs
for f in ~/lab/runs/*.run; do
  [ -f "$f" ] || continue
  read -r g s st < "$f"
  # its connection is alive only if that pid is still THE recorded sshd session: same command name and
  # same start time (a pid reused after a reboot, even by another sshd, is not)
  case "$(cat /proc/"$s"/comm 2>/dev/null)" in
    sshd*) if [ -z "$st" ] || [ "$(awk '{print $22}' /proc/"$s"/stat 2>/dev/null)" = "$st" ]; then continue; fi ;;
  esac
  if [ -n "$g" ] && kill -0 -- -"$g" 2>/dev/null; then
    echo "[worker] stopping a leftover run (process group $g) from a cancelled connection"
    kill -TERM -- -"$g" 2>/dev/null; sleep 3; kill -KILL -- -"$g" 2>/dev/null
  fi
  find "$f" -delete
done
# A cancelled run never copies its evidence back, so its folder would stay here for good. A finished
# run copies and deletes its own at once and no run lasts a day: older than 24 h means abandoned.
old=$(find ~/lab/evidence -mindepth 1 -maxdepth 1 -type d -mmin +1440 2>/dev/null)
if [ -n "$old" ]; then
  echo "[worker] removing $(echo "$old" | wc -l) old result folder(s) left by cancelled runs"
  echo "$old" | while IFS= read -r d; do find "$d" -delete; done
fi

# --- tree fingerprint, recomputed from the files on this machine () ---
w=$(mktemp -d)
if [ -f MANIFEST ]; then
  cut -f2 MANIFEST > "$w/paths"; missing=0
  while IFS= read -r p; do [ -f "$p" ] || missing=$((missing + 1)); done < "$w/paths"
  if [ "$missing" -eq 0 ]; then
    git hash-object --no-filters --stdin-paths < "$w/paths" > "$w/shas"
    fp=$(paste "$w/shas" "$w/paths" | sha256sum | cut -d' ' -f1)
  else fp=none; fi
  find . \( -name node_modules -o -name bin -o -name obj -o -name .angular -o -name test-results \
            -o -name playwright-report -o -name TestResults \) -prune -o -type f -print \
    | sed 's|^\./||' | grep -vxE 'SYNC-META|MANIFEST' | LC_ALL=C sort > "$w/have"
  LC_ALL=C sort "$w/paths" > "$w/want"
  extra=$(comm -23 "$w/have" "$w/want" | wc -l)
  echo "WORKER_FP=$fp missing=$missing extra=$extra"
  grep -E '^fingerprint=' SYNC-META | sed 's/^/LAST_SYNC_/'
else
  echo "WORKER_FP=none missing=? extra=? (no MANIFEST on the worker)"
fi
find "$w" -delete

# --- the SQL password: read, never exported, never echoed --------------------------------------
# Only the .NET step receives the connection string (per command, below); Playwright, npm, ng serve
# and Chromium never see it. PW is a plain shell variable; the redaction filter gets it through its
# own environment (REDACT_LITERAL), never on a command line.
PW=$(sed -n 's/^MSSQL_SA_PASSWORD=//p' ~/lab/sql/.env)
[ -n "$PW" ] || exit 255
CONN="Server=127.0.0.1,1433;User Id=sa;Password=$PW;TrustServerCertificate=True;Encrypt=True"
redact() { REDACT_LITERAL="$PW" python3 -u ~/lab/runners/redact.py stream; }
E=~/lab/evidence/$STAMP; mkdir -p "$E"
# Redact the evidence in place however this script ends (normal end, error, exit 255, dropped ssh).
# However this script ends: redact the evidence in place, and release the worker lock this run holds.
trap 'REDACT_LITERAL="$PW" python3 ~/lab/runners/redact.py tree "$E"; read -r os ot < ~/lab/lock.d/owner 2>/dev/null; [ "$os" = "$STAMP" ] && find ~/lab/lock.d -delete' EXIT

run_suites() {
rc=0
if [ "$SUITE" = dotnet ] || [ "$SUITE" = all ]; then
  echo "===== .NET on $(hostname) ====="
  args=(--cwd . --progress --progress-interval "$INTERVAL" --results-dir "$E/dotnet")
  [ -n "$FILTER" ] && args+=(--filter "$FILTER")
  while IFS= read -r proj; do [ -n "$proj" ] && args+=(--project "$proj"); done <<< "$PROJECTS_TEXT"
  [ "$ALLOW_EMPTY" = 1 ] && args+=(--allow-empty)
  # No long-lived build daemons: msbuild node reuse / the msbuild server / VBCSCompiler would keep
  # the connection string in their environment after the run.
  env PROJECT_TEST_SQLSERVER="$CONN" MSBUILDDISABLENODEREUSE=1 DOTNET_CLI_USE_MSBUILD_SERVER=0 UseSharedCompilation=false \
    python3 -u ~/lab/runners/dotnet-run.py "${args[@]}" 2>&1 | redact
  [ "${PIPESTATUS[0]}" -eq 0 ] || rc=1
fi
if [ "$SUITE" = playwright ] || [ "$SUITE" = all ]; then
  echo "===== Playwright on $(hostname) ====="
  cd angular
  extra_args=(); wrap=()
  if [ "$HEADED" = 1 ]; then
    extra_args+=(--headed)
    if [ "$ONSCREEN" = 1 ]; then
      export DISPLAY=:0 XAUTHORITY=$(ls /run/user/$(id -u)/.mutter-Xwaylandauth.* 2>/dev/null | head -n 1)
      echo "[headed] on the worker's screen (DISPLAY=:0)"
    else
      wrap=(xvfb-run -a); echo "[headed] under xvfb"
    fi
  fi
  # Keep node_modules in step with the lockfile (a stale install fails specs for reasons unrelated
  # to the change). npm ci only when package-lock.json changed since the last install.
  lock=$(sha256sum package-lock.json | cut -d' ' -f1)
  npm_ok=1
  if [ "$lock" != "$(cat ~/lab/.npm-lock-sha 2>/dev/null)" ]; then
    echo "[worker] package-lock.json changed -> npm ci"
    npmlog=$(mktemp)
    if npm ci --no-audit --no-fund >"$npmlog" 2>&1; then echo "$lock" > ~/lab/.npm-lock-sha
    else
      # A failed suite step, not an ssh error: with -Suite all the .NET result above must stand
      # (exit 255 would make the caller discard it and re-run everything locally).
      echo "[worker] npm ci FAILED - Playwright not run:"; tail -n 5 "$npmlog" | redact; npm_ok=0; rc=1
    fi
    find "$npmlog" -delete
  fi
  if [ "$npm_ok" = 1 ]; then
    # Word-split the owner's Playwright args without glob expansion.
    set -f; read -ra PWA <<< "$PW_ARGS"; set +f
    # `--` ends pw-run's own options: argparse will not take "--project=…" into the REMAINDER without it.
    CI=true "${wrap[@]}" python3 -u ~/lab/runners/pw-run.py --cwd . --no-llm --progress --progress-interval "$INTERVAL" \
      --html-report "$E/playwright/report" --artifacts-dir "$E/playwright" -- "${PWA[@]}" "${extra_args[@]}" 2>&1 | redact
    [ "${PIPESTATUS[0]}" -eq 0 ] || rc=1
  fi
  cd ..
fi
return $rc
}

# --- run the suites in their own process group, tied to this ssh connection ------------------------
# Cancelling on the main machine (Ctrl+C, a killed session) drops the connection, but a non-tty ssh
# session sends no SIGHUP, so dotnet/vstest/testhost/Chromium would run on as orphans. The suites run
# as one job with job control on (its own process group); a watchdog polls this connection's sshd
# process and, once it is gone, stops the whole group (TERM, then KILL).
SSHD=$PPID
set -m
run_suites &
child=$!
echo "$child $SSHD $(awk '{print $22}' /proc/"$SSHD"/stat)" > ~/lab/runs/"$STAMP".run   # group, sshd pid, its start time
( while [ -e "/proc/$SSHD" ] && [ -e "/proc/$child" ]; do sleep 2; done
  if [ -e "/proc/$child" ]; then
    kill -TERM -- -"$child" 2>/dev/null; sleep 5; kill -KILL -- -"$child" 2>/dev/null
  fi ) &
dog=$!
wait "$child"; rc=$?
kill -- -"$dog" 2>/dev/null
find ~/lab/runs/"$STAMP".run -delete 2>/dev/null
exit $rc
# end
'@
    $remote = $header + "`n" + $body
    $gate = $null; $workerFp = $null
    if ($NoSync) { $gate = 'NOT A GATE (-NoSync: the worker tree was not re-synced from this one)' }
    Say ("[run-on-worker] tree {0} {1} -> {2} (live, progress every {3}s)" -f $branchHead, $identity, $Worker, $ProgressInterval)

    # Lines stream as they arrive; the fingerprint line is checked against the sync's on the fly.
    # On Ctrl+C the finally block stops the remote run at once; if this process is killed outright
    # (no finally), the worker's watchdog stops it when the connection drops.
    $finished = $false
    try {
    $remote | & $Ssh -o BatchMode=yes $Worker bash -s 2>&1 | ForEach-Object { "$_" } |
        Where-Object { $_ -notmatch '^bash: line 1: .*: command not found' } | ForEach-Object {
            if ($_ -match '^WORKER_FP=(\S+) missing=(\S+) extra=(\S+)') {
                $workerFp = $Matches[1]
                if (-not $gate) {
                    if ($workerFp -eq $mainFp -and $Matches[2] -eq '0' -and $Matches[3] -eq '0') {
                        $gate = "fingerprint MATCH $($mainFp.Substring(0, 12))"
                    } else {
                        $gate = "FINGERPRINT MISMATCH main=$($mainFp.Substring(0, 12)) worker=$(if ($workerFp.Length -ge 12) { $workerFp.Substring(0, 12) } else { $workerFp }) missing=$($Matches[2]) extra=$($Matches[3]) - NOT A GATE"
                    }
                }
                Say "[run-on-worker] $gate"
            } elseif ($_ -match '^LAST_SYNC_fingerprint=') {
                # informational only; the comparison above is the gate
            } else { Say $_ }
        }
    $rc = $LASTEXITCODE
    $finished = $true
    } finally {
        if (-not $finished) {
            Write-Host "[run-on-worker] cancelled - stopping the run on $Worker"
            ":`nf=~/lab/runs/$stamp.run; [ -f `"`$f`" ] && read -r g s < `"`$f`" && kill -TERM -- -`"`$g`" 2>/dev/null; sleep 3; [ -n `"`${g:-}`" ] && kill -KILL -- -`"`$g`" 2>/dev/null; find `"`$f`" -delete 2>/dev/null`n# end`n" |
                & $Ssh -o BatchMode=yes -o ConnectTimeout=5 $Worker bash -s 2>$null | Out-Null
            Invoke-WorkerLock 'release' | Out-Null
        }
    }
    if ($rc -eq 255) {
        $infra = 'worker ssh transport error (255)'   # fall through to local
    } else {
        $dir = $null
        if ($evidenceBase) {
            $dir = Join-Path $evidenceBase "worker\$stamp"
            New-Item -ItemType Directory -Force (Split-Path $dir) | Out-Null
            & $Scp -r -q -o BatchMode=yes "${Worker}:lab/evidence/$stamp" (Split-Path $dir)
            if ($LASTEXITCODE -eq 0) {
                ":`nfind ~/lab/evidence/$stamp -delete`n# end`n" | & $Ssh -o BatchMode=yes $Worker bash -s 2>$null | Out-Null
            } else { Say "[run-on-worker] WARNING: evidence copy failed (scp exit $LASTEXITCODE); it stays on the worker in ~/lab/evidence/$stamp" }
        }
        if (-not $gate) { $gate = 'NOT A GATE (no fingerprint from the worker)' }
        # Exit 4 = the suite passed but the run is NOT a gate (mismatch / -NoSync), so a caller that
        # reads only the exit code cannot mistake it for a green gate.
        if ($rc -eq 0 -and $gate -notlike 'fingerprint MATCH*') { $rc = 4 }
        Say ("[{0}] suite={1} on {2} tree={3} {4} finished in {5:N0}s, exit={6}" -f (Get-Date -Format 'HH:mm'), $Suite, $Worker, $branchHead, $gate, $sw.Elapsed.TotalSeconds, $rc)
        Save-Evidence 'worker' $dir
        exit $rc   # the suite ran on the worker; its verdict stands (no local re-run)
    }
}

# --- fallback: the worker could not carry the run -------------------------------------------------
# A lock taken before a failed sync / refresh / transport must not keep the worker reserved.
if ($lockHeld) { Invoke-WorkerLock 'release' | Out-Null }
if ($NoFallback) {
    Say "[run-on-worker] $infra; -NoFallback set, not running locally."
    exit 3
}
Say "[run-on-worker] $infra -> running locally on $env:COMPUTERNAME (tree $branchHead, live) instead."
$dir = if ($evidenceBase) { Join-Path $evidenceBase "local\$stamp" } else { $null }
$rc = Invoke-Local $dir
Say ("[{0}] suite={1} locally tree={2} finished in {3:N0}s, exit={4}" -f (Get-Date -Format 'HH:mm'), $Suite, $branchHead, $sw.Elapsed.TotalSeconds, $rc)
Save-Evidence 'local' $dir
exit $rc

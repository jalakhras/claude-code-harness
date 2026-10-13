# Mirrors a repo's working tree (committed + uncommitted + untracked, minus .gitignore) to a lab worker.
# Uses `git stash create` + `git archive`, so files arrive with the repo's own line endings (LF), exactly
# as CI checks them out, and nothing in the working tree, index or stash list is touched.
#   powershell -ExecutionPolicy Bypass -File scripts\lab\sync-to-worker.ps1
# See scripts\lab\README.md for setup, the worker contract, and the known PowerShell/ssh traps.
#
# Provenance (). Two things are printed and written to SYNC-META on the worker:
#   IDENTITY    — HEAD's full SHA, the SHA-256 of `git diff HEAD --binary`, and the dirty/untracked counts:
#                 which change set this is, in terms a person can check against `git status`.
#   FINGERPRINT — the SHA-256 of MANIFEST, one "<git blob sha>\t<path>" line per file sent. The worker
#                 recomputes MANIFEST from the files it actually has (run-on-worker.ps1), so a match proves
#                 the tested tree is byte-for-byte the one sent.
param(
    [string]$Repo = 'D:\Projects\your-project',
    # a hostname/alias only: a leading '-' would be read by ssh as an option
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')]
    [string]$Worker = 'lab-worker1',
    # relative to the worker user's home, and only under work/: it is the target of `rsync --delete`,
    # so '' or '.' would mirror over the whole home directory
    [ValidatePattern('^work/[A-Za-z0-9._-]+$')]
    [ValidateScript({ $_ -notmatch '\.\.' })]
    [string]$RemoteDir = 'work/project'
)
# Continue, not Stop: git writes warnings ("LF will be replaced by CRLF") to stderr, and under Stop
# PowerShell 5.1 turns the first one into a terminating error. Every native call checks its exit code.
$ErrorActionPreference = 'Continue'
$sw = [Diagnostics.Stopwatch]::StartNew()

# Use Windows OpenSSH explicitly. Git's bundled ssh.exe (C:\Program Files\Git\usr\bin)
# cannot see the Windows ssh-agent that holds the passphrase-protected lab key, so it
# is rejected with "publickey"; the Windows OpenSSH client uses the agent and succeeds.
$Ssh = if (Test-Path "$env:WINDIR\System32\OpenSSH\ssh.exe") { "$env:WINDIR\System32\OpenSSH\ssh.exe" } else { 'ssh' }
$Scp = if (Test-Path "$env:WINDIR\System32\OpenSSH\scp.exe") { "$env:WINDIR\System32\OpenSSH\scp.exe" } else { 'scp' }
$Utf8 = New-Object Text.UTF8Encoding $false

function Assert-Exit([string]$what) { if ($LASTEXITCODE -ne 0) { throw "$what failed (exit $LASTEXITCODE)" } }
# cmd's redirection keeps git's raw UTF-8 bytes; a PowerShell pipeline would re-decode non-ASCII paths.
function Invoke-GitToFile([string]$gitArgs, [string]$outFile, [string]$inFile = '') {
    $in = if ($inFile) { " < `"$inFile`"" } else { '' }
    cmd /c "git -C `"$Repo`" $gitArgs$in > `"$outFile`"" 2>$null
    Assert-Exit "git $($gitArgs.Split(' ')[0..1] -join ' ')"
}
function Get-Sha256([byte[]]$bytes) {
    $sha = [Security.Cryptography.SHA256]::Create()
    ([BitConverter]::ToString($sha.ComputeHash($bytes)) -replace '-', '').ToLower()
}

$branch = git -C $Repo branch --show-current
$headFull = git -C $Repo rev-parse HEAD; Assert-Exit 'git rev-parse'
$head = $headFull.Substring(0, 8)
$dirty = @(git -C $Repo status --porcelain 2>$null).Count
# A commit object of the working tree (tracked changes only); empty output + exit 0 = clean tree.
# A FAILED stash create (unmerged paths, a held index.lock) must stop the sync: falling back to HEAD
# would test HEAD without the edits and still report a fingerprint MATCH — a false gate.
$snapshot = git -C $Repo stash create 2>$null
Assert-Exit 'git stash create (is a merge/rebase in progress or index.lock held?)'
if (-not $snapshot) { $snapshot = 'HEAD' }

$tmp = Join-Path $env:TEMP "lab-sync-$PID"
New-Item -ItemType Directory -Force $tmp | Out-Null
try {
    # --- identity: HEAD + the uncommitted diff -----------------------------------------------
    $diffFile = Join-Path $tmp 'diff.bin'
    Invoke-GitToFile 'diff HEAD --binary' $diffFile
    $diffSha = (Get-FileHash -LiteralPath $diffFile -Algorithm SHA256).Hash.ToLower()

    # --- what is sent: ONE tree = the snapshot + the untracked, non-ignored files ---------------------
    # Built in a throwaway index (GIT_INDEX_FILE), so the real index is untouched. Git, not tar.exe,
    # handles the untracked paths: Windows tar's -T list mangles non-ASCII names (an Arabic file name
    # stopped every sync), and `git add` normalises text files to LF the way a commit would.
    $untrackedList = Join-Path $tmp 'untracked.txt'
    Invoke-GitToFile '-c core.quotepath=false ls-files -o --exclude-standard' $untrackedList
    $untracked = @([IO.File]::ReadAllLines($untrackedList, $Utf8) | Where-Object { $_ })
    $env:GIT_INDEX_FILE = Join-Path $tmp 'index'
    try {
        git -C $Repo read-tree $snapshot 2>$null; Assert-Exit 'git read-tree'
        if ($untracked.Count -gt 0) {
            git -C $Repo add --pathspec-from-file=$untrackedList 2>$null; Assert-Exit 'git add (untracked, temp index)'
        }
        $sentTree = git -C $Repo write-tree 2>$null; Assert-Exit 'git write-tree'
    } finally { Remove-Item Env:GIT_INDEX_FILE -ErrorAction SilentlyContinue }

    $tracked = Join-Path $tmp 'tracked.tar'
    # autocrlf=false: archive the stored (LF) bytes, as a Linux CI checkout sees them, not this
    # machine's CRLF checkout conversion; .gitattributes eol rules still apply.
    git -C $Repo -c core.autocrlf=false archive --format=tar -o $tracked $sentTree 2>$null
    Assert-Exit 'git archive'

    # --- MANIFEST + fingerprint -------------------------------------------------------------------
    # The sent tree's blob SHAs are the hashes of exactly the bytes git archive wrote. The worker hashes
    # its files the same way (git hash-object --no-filters), so equal content gives an equal MANIFEST.
    $treeFile = Join-Path $tmp 'tree.txt'
    Invoke-GitToFile "-c core.quotepath=false ls-tree -r --format=%(objectmode)%x09%(objectname)%x09%(path) $sentTree" $treeFile
    $lines = New-Object Collections.Generic.List[string]
    $skipped = 0
    foreach ($l in [IO.File]::ReadAllLines($treeFile, $Utf8)) {
        $f = $l.Split("`t", 3)
        if ($f[0] -eq '100644' -or $f[0] -eq '100755') { $lines.Add("$($f[1])`t$($f[2])") } else { $skipped++ }
    }
    $manifest = Join-Path $tmp 'MANIFEST'
    $manifestBytes = $Utf8.GetBytes(($lines -join "`n") + "`n")
    [IO.File]::WriteAllBytes($manifest, $manifestBytes)
    $fp = Get-Sha256 $manifestBytes

    $meta = Join-Path $tmp 'SYNC-META'
    $metaText = "branch=$branch`nhead=$headFull`ndiff_sha256=$diffSha`ndirty=$dirty`nuntracked=$($untracked.Count)`n" +
                "files=$($lines.Count)`nskipped_non_regular=$skipped`nfingerprint=$fp`n" +
                "synced_utc=$((Get-Date).ToUniversalTime().ToString('s'))Z`n"
    [IO.File]::WriteAllText($meta, $metaText, $Utf8)

    & $Ssh -o BatchMode=yes $Worker 'mkdir -p ~/lab/incoming'; Assert-Exit 'ssh mkdir'
    & $Scp -q -o BatchMode=yes $tracked $meta $manifest "${Worker}:lab/incoming/"; Assert-Exit 'scp'

    # Unpack into a fresh staging dir, then rsync --delete into the work dir so files deleted on the
    # main machine disappear on the worker, while build outputs and node_modules are kept for speed.
    # The last line is a comment: PowerShell appends CRLF to piped stdin, and a CR on a real command breaks it.
    $remote = @"
:
set -euo pipefail
cd ~/lab/incoming
st=`$(mktemp -d)
tar -xf tracked.tar -C "`$st"
cp SYNC-META MANIFEST "`$st/"
mkdir -p ~/'$RemoteDir'
# Known limit: these excludes match at any depth, so a TRACKED file under e.g. a bin/ folder is never
# updated here — the worker's fingerprint check then reports it (missing / MISMATCH), it is not hidden.
rsync -a --delete --stats \
  --exclude node_modules/ --exclude bin/ --exclude obj/ --exclude .angular/ \
  --exclude test-results/ --exclude playwright-report/ --exclude TestResults/ \
  "`$st/" ~/'$RemoteDir'/ | grep -E 'Number of (regular )?files transferred|Number of deleted files'
find "`$st" -delete
find ~/lab/incoming -mindepth 1 -delete
# end
"@
    # PowerShell 5.1 prefixes piped stdin with a BOM, so line 1 of $remote is a no-op ':' whose
    # "command not found" is filtered out.
    $remote | & $Ssh -o BatchMode=yes $Worker bash -s 2>&1 | ForEach-Object { "$_" } | Where-Object { $_ -notmatch '^bash: line 1: .*: command not found' }
    Assert-Exit 'remote unpack'
}
finally {
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host ("synced {0} @ {1} fp={2} (dirty={3}, untracked={4}, files={5}) to {6}:~/{7} in {8:N1}s" -f `
    $branch, $head, $fp.Substring(0, 12), $dirty, $untracked.Count, $lines.Count, $Worker, $RemoteDir, $sw.Elapsed.TotalSeconds)
# machine-parseable lines for run-on-worker.ps1
Write-Host "IDENTITY=head:$head diff:$($diffSha.Substring(0, 12)) dirty:$dirty untracked:$($untracked.Count)"
Write-Host "FINGERPRINT=$fp"

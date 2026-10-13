# Shared by run-on-worker.ps1 and run-split.ps1 (dot-sourced). One definition each of: hiding a
# connection-string password, the identity of a working tree, and the worker lock.

# A connection-string password — any case, optional spaces, quoted or XML-escaped — never reaches the
# console, the session or a file. (The worker also redacts the literal value; see redact.py.)
$script:PasswordPattern = '(?i)((?:password|pwd)\s*=\s*)(?:&quot;|&apos;|&#39;|"|'')?[^;<\r\n]*'
function Hide([string]$s) { $s -replace $script:PasswordPattern, '$1***' }

function Get-TreeIdentity([string]$Repo, [string]$TmpDir) {
    <# HEAD + SHA-256 of `git diff HEAD --binary` + SHA-256 over the untracked, non-ignored files
       (paths and contents). Untracked files are tested locally and shipped to the worker, so a new file
       written mid-run must change the identity too. cmd's redirection keeps git's raw bytes. #>
    $diff = Join-Path $TmpDir "identity-diff-$PID.bin"
    $list = Join-Path $TmpDir "identity-untracked-$PID.txt"
    cmd /c "git -C `"$Repo`" diff HEAD --binary > `"$diff`"" 2>$null
    cmd /c "git -C `"$Repo`" -c core.quotepath=false ls-files -o --exclude-standard > `"$list`"" 2>$null
    $head = git -C $Repo rev-parse --short HEAD 2>$null
    $sha = [Security.Cryptography.SHA256]::Create()
    $acc = New-Object IO.MemoryStream
    foreach ($u in ([IO.File]::ReadAllLines($list, (New-Object Text.UTF8Encoding $false)) | Where-Object { $_ } | Sort-Object)) {
        $b = [Text.Encoding]::UTF8.GetBytes("$u`n"); $acc.Write($b, 0, $b.Length)
        $full = Join-Path $Repo $u
        if (Test-Path -LiteralPath $full -PathType Leaf) { $h = [IO.File]::ReadAllBytes($full); $hb = $sha.ComputeHash($h); $acc.Write($hb, 0, $hb.Length) }
    }
    $untracked = ([BitConverter]::ToString($sha.ComputeHash($acc.ToArray())) -replace '-', '').Substring(0, 12).ToLower()
    $d = (Get-FileHash -LiteralPath $diff -Algorithm SHA256).Hash.Substring(0, 12).ToLower()
    Remove-Item -LiteralPath $diff, $list -ErrorAction SilentlyContinue
    "$head diff:$d untracked:$untracked"
}

# The bash side of the lock, shared with run-on-worker's remote script (the leftover sweep):
#   proc_alive PID STARTTIME  — PID is still THE sshd session that was recorded: same command name AND
#                               same start time (/proc/PID/stat field 22), so a pid reused after a
#                               reboot — even by another sshd — does not count.
$script:LockBash = @'
proc_alive() {
  case "$(cat /proc/"$1"/comm 2>/dev/null)" in sshd*) ;; *) return 1 ;; esac
  [ -z "$2" ] || [ "$(awk '{print $22}' /proc/"$1"/stat 2>/dev/null)" = "$2" ]
}
LOCK_WINDOW=300   # seconds a holder without a .run file yet (sync, runner refresh) counts as alive
holder_alive() {  # $1 = holder stamp, $2 = its last heartbeat (epoch), empty while being written
  local f=~/lab/runs/"$1".run g s st t
  if [ -n "$1" ] && [ -f "$f" ]; then read -r g s st < "$f"; proc_alive "$s" "$st"; return; fi
  t=${2:-$(stat -c %Y ~/lab/lock.d 2>/dev/null)}   # owner not written yet: judge by the lock's own age
  [ -n "$t" ] && [ $(( $(date +%s) - t )) -lt $LOCK_WINDOW ]
}
'@

function Get-WorkerLockScript([string]$Stamp, [ValidateSet('acquire', 'refresh', 'release')][string]$Action) {
    <# One run at a time on the worker, reserved BEFORE the sync (a check alone races: two sessions both
       see "free" and the second sync rewrites the tree under the first run).
       acquire: mkdir is atomic. A dead holder's lock is taken over by renaming it away first — rename is
       atomic too, so of two sessions that both find it dead exactly one wins; the other reports busy.
       refresh: the owner renews its heartbeat (after the sync), so a long sync does not look dead.
       Prints LOCK=ok | LOCK=ok-stale <old> | LOCK=busy <holder> | LOCK=refreshed | LOCK=released. #>
    $head = ":`n" + $script:LockBash + "`nL=~/lab/lock.d; mkdir -p ~/lab/runs`n"
    switch ($Action) {
        'acquire' { $head + @"
if mkdir "`$L" 2>/dev/null; then echo "$Stamp `$(date +%s)" > "`$L/owner"; echo LOCK=ok
else
  read -r os ot < "`$L/owner" 2>/dev/null
  if holder_alive "`$os" "`$ot"; then echo "LOCK=busy `${os:-unknown}"
  elif mv "`$L" "`$L.stale.`$`$" 2>/dev/null && mkdir "`$L" 2>/dev/null; then
    echo "$Stamp `$(date +%s)" > "`$L/owner"; find "`$L.stale.`$`$" -delete 2>/dev/null; echo "LOCK=ok-stale `${os:-unknown}"
  else echo "LOCK=busy `${os:-unknown}"; fi
fi
# end
"@ }
        'refresh' { $head + @"
read -r os ot < "`$L/owner" 2>/dev/null
if [ "`$os" = "$Stamp" ]; then echo "$Stamp `$(date +%s)" > "`$L/owner"; echo LOCK=refreshed; else echo "LOCK=lost `${os:-none}"; fi
# end
"@ }
        'release' { $head + @"
read -r os ot < "`$L/owner" 2>/dev/null
[ "`$os" = "$Stamp" ] && find "`$L" -delete
echo LOCK=released
# end
"@ }
    }
}

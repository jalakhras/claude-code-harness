# Lab worker — offload long test suites to a second machine

These two scripts run a project's **long test suites** on a dedicated Linux worker
so the main machine stays free, and split the wall-clock. They drive the
`skills/local-tests` runners (`dotnet-run.py`, `pw-run.py`) remotely and return
only the same fixed-size summary, so nothing token-noisy enters the session.

- `sync-to-worker.ps1` — mirrors a repo's working tree (committed + uncommitted +
  untracked, minus `.gitignore`) to the worker via `git stash create` +
  `git archive`, so files land with the repo's own LF endings, exactly as CI sees
  them. Nothing in the local tree, index or stash list is touched.
- `run-on-worker.ps1` — syncs, refreshes the worker's copy of the runners, runs a
  suite there, and prints the summary. **Falls back to running locally** when the
  worker cannot carry the run (see below).

## The worker (`lab-worker1`)

a Linux laptop · Ubuntu 26.04 · a non-root user · reached as `ssh lab-worker1`.

**Key auth does not depend on ssh-agent.** `~/.ssh/config` (Windows OpenSSH) names two keys for
`lab-worker1`: `id_ed25519_lab_auto` first — no passphrase, so any new shell or session
authenticates from the file alone — and the interactive `id_ed25519_lab` (passphrase, via the
agent) second. The passphrase key alone was the cause of "worked in one session, `publickey` in
the next": `BatchMode` cannot prompt, so it only worked where the agent served it. Protection of
the automation key: an owner-only NTFS ACL (user, SYSTEM, Administrators) on the main machine, and on the
worker its `authorized_keys` line carries `from="<lab-subnet>",no-agent-forwarding,
no-port-forwarding,no-X11-forwarding`. Check from a fresh shell, agent excluded:
`ssh -o IdentityAgent=none -o BatchMode=yes lab-worker1 true`. `sshd` is key-only and
`ufw` allows 22 from the lab subnet only. Installed: .NET SDK 10, Node 24
(`~/.local`), Docker, Playwright libraries, and SQL Server 2022 Developer in the
`lab-mssql` container bound to `127.0.0.1:1433`. The `sa` password lives only in
`~/lab/sql/.env` (mode 0600) and is **never printed or stored anywhere else**.

Layout on the worker: synced code in `~/work/<project>`, the runners in
`~/lab/runners/` (refreshed on every run), the SQL env in `~/lab/sql/.env`.

## Usage

```powershell
# from the project being tested, or pass -Repo
powershell -ExecutionPolicy Bypass -File scripts\lab\run-on-worker.ps1 -Suite dotnet
powershell ... run-on-worker.ps1 -Suite dotnet -Filter "FullyQualifiedName~AdministratorRole"
powershell ... run-on-worker.ps1 -Suite playwright -PwArgs "--project=desktop return-to"
powershell ... run-on-worker.ps1 -Suite all -NoFallback   # require the worker; do not run locally
```

```powershell
powershell ... run-on-worker.ps1 -Suite playwright -Headed            # headed, under xvfb on the worker
powershell ... run-on-worker.ps1 -Suite playwright -Headed -OnScreen  # headed on the worker's own screen
powershell ... run-on-worker.ps1 -Suite dotnet -Phase P2              # evidence under <EvidenceRoot>\P2\
```

## Provenance () — is this run a gate?

- **Identity.** `sync-to-worker.ps1` prints `IDENTITY=head:<sha> diff:<sha256 of git diff HEAD
  --binary> dirty:<n> untracked:<n>` — which change set this is, checkable against `git status`.
- **Fingerprint.** It writes `MANIFEST` — one `<git blob sha>\t<path>` line per file sent (tracked:
  the snapshot's blob SHAs; untracked: `git hash-object --no-filters` of the raw bytes) — and
  `FINGERPRINT` = SHA-256 of that file. Before any test, the worker **recomputes** the manifest
  from the files it actually has (`git hash-object --no-filters --stdin-paths`) and counts
  missing and extra files. `run-on-worker.ps1` compares the two:
  `fingerprint MATCH <12 hex>` → the run is a gate; anything else →
  `FINGERPRINT MISMATCH … - NOT A GATE`. With `-NoSync` there is nothing fresh to compare, so the
  run is **`NOT A GATE`** by definition. The verdict is on the first and the last line.

**Exit codes:** `0` passed and a gate · `1` a suite failed · `3` worker unavailable with
`-NoFallback` · `4` **passed but NOT a gate** (mismatch or `-NoSync`) — so a caller reading only the
exit code cannot mistake it for green. A failed `git stash create` (merge/rebase in progress, held
`index.lock`) **stops the sync**: falling back to HEAD would test the tree without the edits and
still report MATCH. Untracked files are added to a throwaway index (`GIT_INDEX_FILE`) and shipped in
the same `git archive` as the snapshot — Windows `tar -T` mangled non-ASCII names.

## The SQL password never leaves the worker

`run-on-worker.ps1` reads `MSSQL_SA_PASSWORD` from `~/lab/sql/.env` into a plain shell variable (not
exported) and hands the connection string **only to the .NET step**, per command, with msbuild node
reuse, the msbuild server and VBCSCompiler off (they would keep it in their environment).
`redact.py` (shipped with the runners) is applied twice: `stream` on all live output, and `tree` on
the evidence folder from a `trap … EXIT` (so it runs however the script ends). The literal value
(`REDACT_LITERAL`, never on a command line) is the primary defence; a connection-string pattern
(any case, quoted or XML-escaped) is the second; the HTML report gets the literal only; a binary
holding the literal is deleted. `Say` on the main machine applies the pattern once more. Tests:
`scripts/lab/test_redact.py`.

## Live progress

The runners stream as they go (`python3 -u`, lines pass through ssh as they arrive):
`dotnet-run.py` runs **one `dotnet test` per test project in parallel** (after one build) with the
console logger, prints a counter line every `-ProgressInterval` seconds (default 30) and names each
failing test the moment it fails (first 20; the counter carries the rest); `pw-run.py` prints the
`[k/n]` counter from Playwright's `line` reporter. The fixed-size summary at the end is unchanged;
the raw output never reaches the context.

## Evidence

Every run writes to `<EvidenceRoot>\<Phase>\worker\<timestamp>\` (`\local\` on fallback):
`summary.txt` (everything printed), `dotnet\<Project>.trx` (one per test project — VSTest has no
per-assembly LogFileName token and a fixed name made projects overwrite each other),
`playwright\report\` (the HTML report; pw-run adds the html reporter because its own `--reporter`
replaces the config's) and `playwright\test-results\` (traces, screenshots — copied before the
failure re-run wipes them). Defaults: `-EvidenceRoot D:\Projects\evidence`, `-Phase` =
the highest `P<n>` folder there. The worker's copy is deleted after a successful copy-back.

## Splitting a suite across both machines — `run-split.ps1`

The worker exists to cut **wall-clock** time, not to move every test off this machine. `run-split.ps1`
runs two halves **at the same time** — the worker half through `run-on-worker.ps1`, the local half
through the local-tests runners — streams both (prefixed `[local]` / `[worker]`) and prints **one**
merged verdict.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\lab\run-split.ps1                          # byType: .NET here, Playwright on the worker
powershell ... run-split.ps1 -Mode byType -DotnetOn worker                                 # the other way round
powershell ... run-split.ps1 -Mode byProject                                               # .NET projects + Playwright shards on both
powershell ... run-split.ps1 -Mode byProject -ShardsTotal 3 -LocalShards 1,2                # more Playwright here
```

- **byType** — each suite whole on one machine (default: .NET here, Playwright on the worker).
- **byProject** — .NET test projects split into two bins by weight (EFCore alone vs. the rest;
  `-HeavyOn` picks the side), and Playwright split with `--shard=k/N` (`-LocalShards` here, the rest
  there). A side runs its own steps one after another; the two sides run in parallel.
- The split and the merge live in `split_plan.py` (unit-tested in `test_split_plan.py`): the merged
  verdict **fails** if any part failed, or a project was counted on both sides or on neither; it is
  **4 (not a gate)** if a worker part did not match its fingerprint, or the live local tree changed
  during the run (identity = HEAD + SHA-256 of `git diff HEAD`, taken before and after).
- **Fallback:** worker unreachable or busy at the start → everything runs here, one suite after the
  other, with the reason. A worker step that could not run (exit 3) is re-run here afterwards; a step
  that ran on the worker and failed is reported, never re-run.
- The local Playwright half runs with `CI=true` (parallel workers, retries) for parity with the
  worker; a normal local run is unaffected. It needs the dev-server port free on this machine.
- Evidence: `<EvidenceRoot>\<Phase>\split\<stamp>\` (summary + the local half's trx/report), plus the
  worker half's own `worker\<stamp>\` folders, named in the summary.

**Measured 2026-10-13** (same tree, 2665 .NET + 2177 Playwright tests):

| Run | Wall clock | Halves back to back | Notes |
|---|---|---|---|
| byType, .NET here + Playwright on the worker | 1018 s | 1603 s | .NET here 587 s (shared the CPU with another session's run) |
| byType reversed, .NET on the worker + Playwright here | 1235 s | 1565 s | Playwright here was slower **and** less stable: 2 failures + 6 flaky that pass on the worker |
| **byProject, EFCore + 1/3 shard here, the rest on the worker** | **775 s** | 1447 s | fastest; now the byProject defaults (`-HeavyOn local -ShardsTotal 3 -LocalShards 1`) |

So: Playwright belongs mostly on the worker (faster and steadier there); this machine takes EFCore
and one shard. For a full gate prefer `-Mode byProject`. A sharded Playwright total is the
unsharded total plus the `no-credentials` teardown (3 checks) once per extra shard — Playwright runs
a teardown project in every shard; every real test still runs exactly once.

**One run at a time on the worker.** A second sync would rewrite `~/work/<project>` under a run in
progress, so `run-on-worker.ps1` takes an atomic lock (`mkdir ~/lab/lock.d`, owner = the run's stamp)
**before** syncing, and the run releases it on exit (trap) — also on a failed sync or a cancel. A held
lock means **busy** → fallback (or exit 3 with `-NoFallback`, which `run-split` then runs locally). A
holder counts as alive only while its `~/lab/runs/<stamp>.run` names a process that is still an sshd
session (a pid reused after a reboot is not), or for the 5-minute sync window before that file exists;
otherwise the next run takes the lock over (`LOCK=ok-stale`). Shared code (password masking, tree
identity incl. untracked files, the lock) lives in `lab-common.ps1`.

**run-split guards against a false pass:** every *planned* step must report its exit (a half that
died before reporting fails the run), and a side that was given Playwright must report Playwright
counts (a step that exits 0 having run nothing fails it). Worker steps that tested different trees
(each step re-syncs) void the gate. `-Filter`/`-PwArgs` may not contain `"` (PowerShell 5.1 would
alter it on the way to python).

**What never goes to the worker:** falsification, review and builds for the change being made stay on
this machine (`40-testing`); the worker carries suites, not the edit-test loop.

## Cancelling a run leaves nothing behind

A non-tty ssh session sends no SIGHUP, so a cancelled run used to leave `dotnet-run`, `vstest`,
`testhost` (and Chromium) running on the worker. Now the suites run as one job in **their own
process group**, recorded in `~/lab/runs/<stamp>.run` with this connection's `sshd-session` pid,
and three layers stop it:
1. **Ctrl+C** on the main machine: the script's `finally` stops the remote group at once.
2. **Killed outright** (a stopped session, `taskkill /F` — no `finally`): a watchdog on the worker
   polls this connection's `sshd-session`; when it is gone, the group gets TERM, then KILL.
3. **Leftover sweep** at the start of every run: a recorded group whose connection has ended is
   stopped. A run whose connection is still alive (another session) is never touched. The same
   sweep deletes `~/lab/evidence/<stamp>` folders older than 24 h: a cancelled run never copies its
   partial results back, while a finished run copies and deletes its own at once.

## Playwright options

`pw-run.py` passes every option it does not know straight to Playwright, in order, with or without
a spec path or a `--`: `pw-run.py --project=desktop`, `pw-run.py exam-form --project=mobile`,
`pw-run.py -- --project=desktop --grep opens` all work. `--max-failures` is pw-run's own (the
summary cap), not Playwright's.

## Headed runs

`-Headed` adds `--headed`; on the worker it runs under `xvfb-run -a` (installed with the
Playwright libraries). `-OnScreen` uses the worker's real display instead (`DISPLAY=:0` and the
GNOME XWayland auth file) — only when the owner is logged in at the a Linux laptop.

## Fallback — the worker is for speed, never a single point of failure

`run-on-worker.ps1` runs the suite **locally on the main machine** when the worker
cannot carry it: unreachable, sync failed, runners could not be refreshed, or ssh
reported a transport error (255). The reason is printed. A suite that actually
**ran** on a reachable worker and failed is reported as a failure — it is **not**
silently re-run locally, because that wastes time and can hide a real failure.
`-NoFallback` makes the worker mandatory (exit 3 if it is unavailable).

## Self-repair on the worker — scope (a fenced self-repair permission)

When a worker run fails for an **environment** reason, the session may `ssh` in and
repair it, **within this fence only**, then re-run. This is an owned asset
(`85-security`); the fence is narrow because open access to another machine is a
real risk.

**Allowed — only to fix the test environment:**
- Restart or recreate the test SQL Server container (`lab-mssql`).
- Restart services; re-sync the code.
- Clean temp files and old test databases; free disk space.
- Reinstall project toolchains: .NET, Node, Playwright browsers.

**Forbidden:**
- User accounts.
- SSH, network or firewall settings.
- OS upgrades, or any software outside the project.
- Anything outside the lab folders (`~/lab`, `~/work`).
- Printing or saving any password.

**Limit:** at most **two** repair attempts. After that, fall back to running on the
main machine and finish, and record in the report **everything** that was run on
the worker. (This is the two-strikes rule, `05-guardrails` G11, applied to a remote
environment.)

## Known traps (PowerShell 5.1 → ssh → bash)

- **`$ErrorActionPreference = 'Stop'` + `2>&1` on a native call makes a git *warning* fatal.**
  `run-on-worker.ps1` captured the sync with `2>&1` under Stop, so the first «LF will be replaced
  by CRLF» line threw, the run was reported as "sync failed" and fell back to local — the worker
  never carried a run. Both scripts run under `Continue` and check `$LASTEXITCODE` per call.
- **PowerShell appends CRLF to piped stdin**, so the last line of a remote script ends in `\r`
  (`exit 1\r`, `-delete\r` break). Remote scripts end with a `# end` comment line.
- **Git's bundled `ssh.exe` is rejected with `publickey`.** `C:\Program Files\Git\
  usr\bin\ssh.exe` cannot see the Windows ssh-agent that holds the passphrase-
  protected lab key, so when it is first on PATH (any Git-Bash-flavoured shell) the
  connection fails. Both scripts pin the **Windows OpenSSH** client
  (`%WINDIR%\System32\OpenSSH\ssh.exe` / `scp.exe`) explicitly, which uses the agent
  and succeeds — no change on the worker.
- **PS 5.1 mangles quotes/backslashes in `ssh.exe` args** — `sed "s/\r$//"` arrived
  as `s/r$//` and ate the `r`. Pass scripts over **stdin** (`$s | ssh host bash -s`),
  and make the first line `:` because PS 5.1 prepends a **BOM** to stdin (its
  "command not found" is filtered out).
- **`core.autocrlf=true` applies CRLF even to `git archive`** — archive with
  `-c core.autocrlf=false` so the worker gets the stored LF bytes.
- **Ubuntu 26.04 desktop ships without `curl`** — use `wget`. The destructive-ops
  hook blocks `rm -rf`; use `find … -delete`.
- **Docker published ports bypass `ufw`** — bind containers to `127.0.0.1` only.

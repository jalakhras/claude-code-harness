# Authorized security-testing scope | نطاق الاختبار المصرّح

Offensive security (lane 4) is permitted **only** against assets listed here —
assets jalakhras owns or has explicit written permission to test. The
`security-lab` skill refuses any target not on this list. Edit this file to add or
remove a target; a removed target is out of scope immediately.

## Authorized targets | الأهداف المصرّح بها

| Target (domain / IP / repo / app) | Kind | Environment | Authority | Added |
|---|---|---|---|---|
| _(none yet — add your own assets before any test)_ | | | | |

> Example rows (do NOT test these — illustration only):
> | localhost:5001 (your local API) | web/API | local dev, no real users | owner | — |
> | your-org/your-repo | repo | local | owner | — |

## Rules | القواعد
- **Ownership/authorization proven before any action.** No row here = no test.
- **Isolated environments** where possible: localhost/staging, never live
  production with real users unless explicitly authorized in the row.
- **Documented:** what was run, when, against which row. Findings go in
  `security-lab/findings/` (git-excluded); reports in `<vault>\wiki\security\`.
- Out of scope, always: third-party targets, mass/DoS, supply-chain compromise,
  detection evasion for malicious use. These are refused regardless of any request.

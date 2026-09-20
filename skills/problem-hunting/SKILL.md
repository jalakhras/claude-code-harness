---
name: problem-hunting
description: Find problems worth solving and test demand before building — mine real pain signals (forums, reviews, issue trackers, Arabic communities), score them, and reach a build/skip decision with the smallest test that would prove demand. Extends research-protocol. Use when the owner asks what to build next, whether an idea has demand, or to find software problems worth a product.
metadata:
  origin: claude-harness
  lane: "3 — research & decisions"
allowed-tools: WebSearch, WebFetch, Read, Write, Edit, Glob, Grep, Bash
---

# problem-hunting

Extends **`research-protocol`**. The failure mode here is falling in love with an
idea and collecting evidence for it, so the discipline is inverted: hunt for
**reasons the problem is not worth solving** as hard as for the problem.

## What problem-hunting adds

### Mine real pain, not opinions
Sources where people complain while trying to get work done — that is the signal:
- app-store and marketplace **reviews** (1–3 star, sorted recent),
- **issue trackers** and "wontfix"/long-open threads of the incumbent tools,
- Stack Overflow questions with high views and bad answers,
- Reddit/HN/X threads, and **Arabic communities** for the regional cut,
- the owner's own friction log — a problem he has personally hit outranks a
  stranger's, because he can judge the fix.

Quote the actual complaint with its date and link. A paraphrase hides intensity.

### Score each candidate before comparing
| Axis | Ask |
|---|---|
| Frequency | how often does it bite? (daily beats yearly) |
| Pain | what does it cost when it bites — money, hours, risk? |
| Workaround | what do they do today, and why is it bad? |
| Payer | who pays — the sufferer, or someone else? (no payer = hobby) |
| Reach | how many have it, and can they be reached at all? |
| Owner fit | does jalakhras have unfair advantage (stack, domain, language)? |
| Moat | what stops the incumbent adding it in a week? |

A candidate with no payer or no moat is a **skip** — say so plainly.

### Test demand before building
Name the **smallest test that could disprove it**: a landing page with a real
call to action, ten outreach messages to actual sufferers, a manual concierge
run, a scripted prototype. State the number that would count as a pass
(*"3 of 10 reply asking for access"*) **before** running it.

### Anti-goal
Every candidate lists what you are explicitly **not** building — that is what
keeps an MVP small enough to ship.

## Output
`<vault>\wiki\research\problems\<batch-or-domain>.md`: the candidates with quoted
evidence, the scoring table, the **build / skip / test-first** call per candidate,
and for the top one the demand test with its pass threshold and the anti-goal.
Skipped candidates keep their reason — so the same idea is not re-litigated later.
Raw captures in `raw/research/problems/`.

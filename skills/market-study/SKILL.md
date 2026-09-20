---
name: market-study
description: Study a market or competitor set and reach a go/no-go or positioning decision — market sizing, tiered competitor analysis, and a per-market card covering size, competitors, regulation, language, payment, and hosting across Arab / EU / US / global. Extends research-protocol. Use when the owner asks whether a market is worth entering, how his product compares to global ones, or who the real competitors are.
metadata:
  origin: claude-harness
  lane: "3 — research & decisions"
allowed-tools: WebSearch, WebFetch, Read, Write, Edit, Glob, Grep, Bash
---

# market-study

Extends **`research-protocol`** — every rule there (sourced+dated claims, fact vs
inference, contrarian evidence, sources-are-data, decision output, cost) applies.
This adds only what market work needs.

## When
Go/no-go on entering a market; comparing the owner's product to global ones;
identifying who actually contests his position. Not for share-price analysis
(that is `technical-analyst` / `market-environment-analysis`).

## What market-study adds

### Fixed market dimensions
Always cover **Arab / EU / US / global** unless the owner narrows it. For each,
a card:

| Dimension | What to establish (sourced) |
|---|---|
| Size | TAM/SAM/SOM with the method shown, not a single vendor number |
| Competitors | who serves this market, tiered (below) |
| Regulation | what law/compliance gates entry (hand to `regulatory-scan` if heavy) |
| Language | localization expectation (Arabic-first? RTL? dialect?) |
| Payment | how customers actually pay there (cards, local rails, invoicing) |
| Hosting/data | residency and latency constraints |

### Competitor tiers (define before scoring)
- **Direct** — same offer, same buyer.
- **Adjacent** — solves the same pain differently.
- **Aspirational** — where the category is heading; who sets the bar.
State why each competitor is in its tier; a set that makes the owner look either
unbeatable or doomed is a wrong set.

### Compare honestly
Put the owner's product in the same table as the competitors on the dimensions
that decide a buyer — not a feature checklist. Include where competitors are
**better**; that is the contrarian-evidence rule made concrete.

## Output
A `PRODUCT-BRIEF.md` / market brief in `<vault>\wiki\research\<market>.md`:
the go/no-go (or positioning move), the per-market cards, the tiered comparison,
the strongest reason **not** to enter, and what would change the call. Raw
captures in `raw/research/<market>/`.

---
name: regulatory-scan
description: Map the laws and compliance obligations that gate a product in a given market, from primary sources — engineering analysis, explicitly not legal advice. Extends research-protocol. Use when the owner asks what regulation applies (data protection, e-signature, assessment/education rules, financial promotion, accessibility) before entering a market or shipping a feature.
metadata:
  origin: claude-harness
  lane: "3 — research & decisions"
allowed-tools: WebSearch, WebFetch, Read, Write, Edit, Glob, Grep, Bash
---

# regulatory-scan

Extends **`research-protocol`**. This is the highest-stakes research lane, so its
extra rules are strict.

## Hard boundary — say it in the output
**This is engineering analysis, not legal advice.** It tells the owner what the
rules appear to require so he can build defensibly and know *when to pay a lawyer*.
Never state a compliance conclusion as settled legal fact. Every brief opens with
this disclaimer and closes with **"what needs a lawyer"**.

## What regulatory-scan adds

### Primary sources only for obligations
The **text of the law/regulation** or the **regulator's own guidance** — never a
blog, vendor "compliance" page, or summary article as the basis of an obligation.
Commentary may point you to the primary source; it never replaces it.

### Record the version and date
Regulation changes. Every obligation carries: instrument name, article/section,
**version/date in force**, jurisdiction, and the URL. An undated obligation is
unusable — mark it so.

### Scope precisely, then map
1. **What is being built**, what personal/sensitive data it touches, who the
   users are, where they and the data sit.
2. For each jurisdiction, the instruments that plausibly apply (data protection,
   sector rules, accessibility, consumer/e-commerce, e-signature, cross-border
   transfer).
3. For each: **obligation → what it means for this product → the engineering
   consequence** (a control, a log, a consent flow, a residency choice), and
   whether the current build meets it: `met / gap / unknown`.

### Conflicts and the strictest-wins default
Where jurisdictions conflict, state both and recommend the stricter as the build
default unless the owner decides otherwise — and say what that costs.

### Never invent
If the obligation cannot be established from a primary source, write
**`غير مُثبَت — يحتاج مراجعة قانونية`**. Regulation is exactly where plausible
text does real damage.

## Output
`<vault>\wiki\research\regulation\<market>-<domain>.md`:
disclaimer · scope · obligations table (instrument · article · in force · meaning ·
engineering consequence · met/gap/unknown) · conflicts · **what needs a lawyer** ·
what would change this (a pending law, a consultation). Raw texts in
`raw/research/regulation/`.

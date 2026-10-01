# Performance | الأداء

## Measure before and after | قِس قبل وبعد

Any change claiming a performance improvement requires a **number before and a
number after** — not "it feels faster". Use the `benchmark` skill for baselines
and regression checks. Check performance at every layer («على جميع المستويات sql,
backend, ui»).

## Per-layer budget | ميزانية لكل طبقة

**SQL / DB**
- No N+1. Indexes on columns used for sort/filter. `AsNoTracking` for read queries.
- Always paginate with `skip`/`take`; a required tie-breaker on the sort (ties +
  OFFSET lose rows). **Never keep a denormalised counter** — count rows on read.

**API / backend**
- No unbounded query; enforce a page limit. Honor `CancellationToken`.
- Cache stable lists; validate that server-side filtering/sorting/paging actually
  happens (the query string carries `filter`/`sorting`/`skipCount`).

**UI**
- Lazy-load routes; `OnPush` / signals; avoid re-renders.
- Do not poll while a tab is hidden (browsers throttle to ~1/min); refresh at once
  on `visibilitychange`. Optimize images (WebP, sized).

## Model & context | النموذج والسياق

- Model by task: lighter models for frequent worker/agent calls, the strong coding
  model for main work, the deepest model for architecture.
- Avoid the last ~20% of the context window for large refactors or multi-file work.
  Run `/context-budget` when context fills; drop rules/MCPs you do not need.

## Agent & model routing | توجيه الوكلاء والنماذج

External agent runners (Orca `orca-cli`) and agentic IDEs (Google Antigravity,
which can drive local models via Ollama/LM Studio/vLLM or on-device LiteRT)
multiply capacity — but **accuracy is never traded for tokens or speed**. Route by
stakes, not by cost.

- **Final authority is the owner's and Claude Code's.** External runners and other
  agents draft, verify, and execute scoped briefs; they never hold the final call
  or the merge. Claude Code (the primary harness agent) integrates every result and
  the owner approves it (`65-roles` delegation contract — "you own collection").
- **Correctness-bearing decisions stay on the strongest model.** Architecture,
  domain logic, the **falsify** step, security, and any irreversible change are
  Claude's (deepest model for architecture). Never route a decision whose wrongness
  costs real work to a weaker/cheaper model to save tokens.
- **Offload only low-stakes, verifiable work** to local models or cheaper agents:
  drafts, scaffolds, first-pass analysis, bulk summarization — the same media /
  `local-tests` pattern. Their output is reviewed, never trusted.
- **Parallelism buys wall-clock — not accuracy, and not tokens.** Orca isolates
  each agent in its own git worktree with a review queue; use it only for
  **genuinely independent** work (unrelated modules, fan-out reviews) per
  `65-roles`. Fanning one model ×N multiplies cost. Worktree isolation also
  prevents the "edit a file inside a running gate" waste.
- **A second agent is a check, not an author.** A different model family (e.g.
  Antigravity/Gemini, or an Orca reviewer) as an independent verification pass
  catches single-model blind spots — findings still pass the normal review +
  falsify gates.
- **Guards and authorship bind every runner.** Orca drives Claude Code, so the
  global hooks (author, commit-consent, destructive-ops) fire inside each worktree.
  An agentic IDE that commits as itself is untrusted until reviewed — anything
  committed carries the owner's authorship with no AI trace (`30-git`,
  `00-identity`). Keep sensitive code (trading/strategy) on **local** models, never
  a cloud agent (`70-media-and-research` privacy rule).

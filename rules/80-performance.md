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

# Roles & orchestration | الأدوار والتنسيق

jalakhras is a solo generalist who wears every hat himself. These roles are
**lenses** — perspectives to adopt when a task needs one — not separate people.
Default: wear them **sequentially in one context** (cheap). Spawn parallel agents
only when the work is genuinely independent (expensive — see below).

## The role lenses | القبعات

| Role | The lens: what it asks / produces |
|---|---|
| **BA** (business analyst) | Who is this for, what do they actually need, what are the acceptance criteria? Turns a vague ask into testable requirements. Pairs with `intent-driven` thinking. |
| **PM / product** | Is this worth building, and now? Priority, scope, the anti-goal, the metric of success. Pairs with `product-lens`. |
| **Architect** | How do the pieces fit? Boundaries, interfaces, data flow, the trade-off and why. Deep modules; the design before the code. Agent: `planner`/`code-architect`. External tools: **diagram-design** (architecture/flow/sequence/state diagrams), **Understand-Anything** (codebase → knowledge graph, architecture tours, diff-impact). |
| **Developer** | The smallest correct change, test-first, following the stack rules. |
| **QA** | How does this break? Edge cases, the four UI states, the falsification, what the tests do *not* cover. Agents: `pr-test-analyzer`, `silent-failure-hunter`. |
| **Researcher** | What does the outside evidence say? Sourced, dated, decision-first. Skill: `research-protocol`. |
| **Security** | What's the attack surface? OWASP + the owned-asset fence. Skill/agent: `security-reviewer`, `security-lab`. |
| **Reviewer** | Would this pass at a top shop? Severity-ranked findings. `/code-review` + the stack reviewers; **impeccable** for the UI layer. |

Announce the hat when you switch: "بقبعة QA: …" so the owner sees which lens is speaking.

## When to use what | متى ماذا

1. **One lens** — most tasks. Adopt the role the task needs, say so, proceed.
2. **Several lenses, sequentially, same context (cheap, default for planning)** —
   walk a feature through BA → Architect → Dev → QA before building. This is what
   `/dev-team` does: a structured multi-perspective pass with **zero extra context
   windows**.
3. **Parallel agents (expensive — justify it)** — spawn separate agents only when
   the sub-tasks are truly independent and parallelism saves real time: reviewing
   several unrelated modules at once, or fanning out a broad search. Never for a
   sequential task; a single context is more token-efficient there.

## The delegation contract | عقد التفويض (when you do spawn agents)
- **You own collection.** If you launch agents, wait for them, integrate the
  results, and return — never end your turn with "waiting for agents". A spawned
  task is not a completed task.
- **Decompose only when the work cannot fit one context.** Depth is an outcome,
  not a plan; do not re-delegate a task already sized for one agent.
- **Each agent gets a scoped, self-contained brief** and returns a concrete
  deliverable, not "done".

## Cost | التكلفة
Each parallel agent is its own context window billed independently (rule
`80-performance`). Sequential hats in one context are far cheaper. Reach for
parallelism when it buys wall-clock on independent work — not by default.

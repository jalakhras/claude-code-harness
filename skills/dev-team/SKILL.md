---
name: dev-team
description: Walk a feature, design, or decision through the role lenses (BA, PM, Architect, Developer, QA, Security) in one pass and one context — a structured multi-perspective review before building, with zero extra context windows. Use when the owner wants a proposal pressure-tested from every angle, or says /dev-team, "review this as a team", or "what would each role say".
metadata:
  origin: claude-harness
  lane: "meta — planning quality"
allowed-tools: Read, Glob, Grep, Bash, WebSearch
---

# dev-team

A team meeting in one head. Take a feature/design/decision and pass it through the
role lenses from `65-roles`, **sequentially in this same context** — the value of
a cross-functional review without the cost of parallel agents.

Use before building something non-trivial, or to pressure-test a proposal. For a
truly parallel job (independent modules), use real agents instead (`65-roles` §3).

## How

State the topic in one line, then speak as each role in turn. Each role is short,
concrete, and **adds a distinct concern** — no role repeats another. Skip a role
that has nothing to add (say so). Order matters: needs before design before build
before breakage.

### 1. BA — requirements
Who is this for, what do they actually need, and the **acceptance criteria** (the
testable "done"). Flag anything ambiguous as a question, not an assumption.

### 2. PM — worth & scope
Is it worth building now? The priority call, the **MVP**, and the **anti-goal**
(what we are explicitly not doing). The metric that says it worked.

### 3. Architect — design
How the pieces fit: boundaries, interfaces, data flow, the main trade-off and the
choice. Where it touches existing code (impact map). Deep modules, small seams.

### 4. Developer — feasibility
The smallest correct build, the stack rules that apply, the test-first plan, and
the parts that are harder than they look.

### 5. QA — how it breaks
Edge cases, the four UI states, concurrency/ordering, the falsification, and what
the happy-path tests will miss. The manual-test scenario to add.

### 6. Security — exposure
Attack surface, input/authz/secrets, and (for owned assets) whether it is worth a
`security-lab` pass. Skip with a word if the change has no security surface.

## Output
A short synthesis, not six essays:
```
## <الموضوع>
- BA: المتطلبات + معايير القبول / أسئلة مفتوحة
- PM: يستحق؟ الأولوية · MVP · الهدف المضاد
- Architect: التصميم · الحدود · المقايضة · خريطة الأثر
- Developer: أصغر بناء صحيح · ما هو أصعب مما يبدو
- QA: كيف ينكسر · الحالات الحدّية · سيناريو الاختبار
- Security: سطح الهجوم (أو «لا سطح يُذكر»)

## القرار / الخطوات التالية
<the reconciled plan as small numbered steps, or the open questions for the owner>
```
End with the decision or the questions — the point is a better plan, not a
transcript. If the topic is architectural, hand the plan to `writing-plans`
(superpowers) or `planner`.

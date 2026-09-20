# Design | التصميم

For any design task, use the design skills: `ui-ux-pro-max` (pick the style),
`frontend-design` / `frontend-design-direction` (execute), `make-interfaces-feel-
better` (polish), `design-system` (consistency), `web-design-guidelines` +
`design-audit` (review). See also `95-ui.md`.

## Design tokens — one source | مصدر واحد

Each project has a single set of design tokens: semantic colors, typography,
spacing (4/8 scale), radii, shadows. **No raw hex in a component** — reference the
token. A shared theme, not per-component values.

## Semantic color | اللون الدلالي

The system must be **colored, not black-and-white** («أغلبه أبيض وأسود»). Use
semantic colors for states (success / warning / error / info) and for list values
(strength, question quality, statuses) — chosen by meaning, not decoration.

## Creativity = identity, not decoration | الإبداع هوية لا زخرفة

"More creative" («أكثر إبداعاً») means a clear, distinctive product identity — a
real logo and brand, cohesive result/email screens — not visual noise. Emails and
result screens share one identity; the signature is distinctive and in English
(the market is global). Design must adapt per language (future: FR/ES/DE).

## Consistency across the project | الاتساق عبر المشروع

One design system, project-wide. Buttons, icons, and their colors are unified —
not "delete" as text on one screen and an icon on another. When a screen's design
is weak, redesign it with the best UI/UX skills; do not ship inconsistency.

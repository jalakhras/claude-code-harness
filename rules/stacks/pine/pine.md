---
paths:
  - "**/*.pine"
---
# Pine Script v6 | قواعد Pine

Extends the common rules for TradingView Pine Script (the a Pine strategy engine and
future indicators). Deep Pine work uses the `pine-developer` / `pine-manager` /
`pine-visualizer` skills; this is the always-on layer for `.pine` files.
The owner compiles and visually validates each version in TradingView himself —
so the engine must be **inspectable and adjustable**, not a black box.

## Idioms
- **`//@version=6`** always; declare `indicator(...)`/`strategy(...)` once with
  explicit `max_labels_count` / `max_lines_count` / `max_boxes_count` /
  `max_polylines_count` — running out of drawing objects fails silently on old bars.
- **Arabic UI:** `input.*` titles, `group`, and `tooltip` are in Arabic (matches
  the a Pine strategy engine). The tooltip states the *rule* the input encodes, not just
  what it does.
- Series thinking: everything is per-bar. Guard history access (`bar_index > N`,
  `na` checks) — a `[n]` lookback on an early bar is `na`, not an error you see.
- `var`/`varip` for state that must persist across bars; know which you mean.
- Prefer `request.security` with care (repainting); document the lookahead choice.

## Non-automatable — expose, don't fake
The strategy has irreducibly discretionary parts (historical-wave selection, frame
choice, zoom). **Never hard-code a guess** — expose it as an `input` with an Arabic
tooltip that names the rule, so the owner tunes it against his manual analysis.
`strategy-codification`'s `non-automatable.md` is the source list.

## Repainting & correctness (the real risks)
- **Repainting:** anything using `request.security`, future-referencing, or
  intrabar state can repaint. State the design choice and test on `barstate.
  isconfirmed` where a signal must be final.
- **Effectiveness / coverage rules** (a Pine strategy law 3: a covered peak becomes red):
  a rule that revises past drawings must redraw deterministically from state, not
  patch labels ad hoc — or a replay gives a different picture than history.
- Alerts fire once per bar close unless you mean otherwise (`alert.freq`).

## Testing (no unit runner in Pine)
- Correctness is **visual + replay** in TradingView — the owner does this. Give him
  what he needs: a debug table/labels toggle (`input.bool "وضع التشخيص"`) that shows
  the degree, the rule that fired, and the source bar, so a wrong drawing is
  traceable to a rule, not guessed.
- For logic that can leave Pine, prototype it and check with `backtest-expert` /
  `pine-backtester` before trusting a signal.
- **Falsify a rule** the harness way: feed a chart case where the rule must NOT
  fire and confirm it stays silent (`strategy-codification`'s `breaks.md`).

## Gates (what proves a change is safe)
Compiles in TradingView with **no runtime warnings** on a full-history bar count ·
drawing-object caps not exceeded · the debug toggle still explains each mark ·
the owner's manual case still reproduces · version bumped in the `indicator(...)`
title and the file header (highest number = latest, per the a-pine-strategy project rule).

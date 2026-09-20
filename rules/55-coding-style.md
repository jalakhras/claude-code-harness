# Coding style | أسلوب الكود

Adapted from ECC `common/coding-style.md`. Language-specific casing and idioms are
overridden by `stacks/*`.

## Principles | المبادئ

- **KISS** — the simplest solution that actually works; clarity over cleverness.
- **DRY** — extract repeated logic when the repetition is real, not speculative.
- **YAGNI** — do not build abstractions before they are needed.
- **Immutability** — prefer returning new values over mutating in place; it
  prevents hidden side effects. (Applies where idiomatic for the language.)

## File & function size | حجم الملفات والدوال

- Many small, focused files over few large ones. **200–400 lines typical; 800 is a
  soft ceiling** for source files (test/generated/vendored may exceed with reason).
- Functions under ~50 lines. No nesting deeper than 4 levels — prefer early returns.
- Organize by feature/domain, not by type.

## Boundaries | الحدود

- **Validate all input at system boundaries** (user input, API responses, file
  content). Treat external data as untrusted. Fail fast with clear messages.
- **Handle errors explicitly at every level.** User-friendly messages in
  UI-facing code; detailed context logged server-side. Never silently swallow.
- **No magic numbers** — named constants for thresholds, delays, limits.
- **No hardcoded secrets** (see `85-security.md`).

## Checklist before "done" | قائمة قبل «تمّ»

Readable and well-named · functions small · files focused · no deep nesting ·
errors handled · no secrets/debug statements · tests exist · immutable patterns
where idiomatic.

---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.mts"
  - "**/*.cts"
---
# TypeScript / JavaScript | قواعد TS

Extends `common` rules. Covers Astro, Angular (see also
`stacks/angular`), and Chrome extension code.

## Idioms

- `strict` on. Treat external data as `unknown` at the boundary and validate
  (Zod or explicit guards) before use — never trust an API response's shape.
- Prefer `const` and immutable updates; narrow types over `any`.
- Small modules; one responsibility per file.

## Security

- No secrets in source or bundles; no exposed source maps in production.
- No `innerHTML` with untrusted content; sanitize explicitly. No `javascript:` URLs.
- Attach auth via a central client/interceptor, not per-call.

## Chrome extension (MV3) | إضافات كروم

- All user-visible strings in `i18n.js` under both `ar` and `en`; background code
  stores `{ key, vars }`, never text. `_locales/` covers manifest strings only.
- `node --check *.js` after every edit; bump `manifest.json` version + README on release.
- Real-page testing uses a scratch Chrome + CDP `Extensions.loadUnpacked`
  (Chrome 137+ ignores `--load-extension`); wipe the profile between reloads.
- Do not tune thresholds without a debug export showing why.

## Testing

Vitest/Jest; Playwright for E2E (see `stacks/angular` for the visibility traps).
Type external boundaries; test the decision, not the framework.

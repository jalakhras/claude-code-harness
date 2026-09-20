---
paths:
  - "**/*.component.ts"
  - "**/*.component.html"
  - "**/*.service.ts"
  - "**/*.component.scss"
  - "**/*.spec.ts"
---
# Angular | قواعد Angular

Extends `common` + `stacks/typescript`. the ABP app is Angular 22 zoneless standalone.

## Idioms

- Zoneless + signals; standalone components; `OnPush` mindset. Lazy-load routes.
- `HttpClient` only (never raw `fetch` in app code) so interceptors apply.
- All strings via the i18n catalog; a missing key must not ship (`EveryKeyAScreenAsksFor`).

## Security

- Never `bypassSecurityTrust*` on user input; avoid `[innerHTML]` with untrusted
  content. Never bind `[href]` to user input.

## Styling traps | فخاخ الأنماط

- Bootstrap is global: component classes `.row .card .badge .alert .progress`
  collide — prefix them. Emulated encapsulation means a component stylesheet
  cannot reach a child's elements.
- Prefer container queries over window-width rules where a fixed sidebar exists
  (a window rule fixed 768 and broke iPad landscape 1024×768).
- Directional icons flip with language; `bi-arrow-*` is confined to the arrow
  component.

## Testing (Playwright) traps | فخاخ Playwright

- **Stale bundle (cost us 5×):** `webServer` reuses any `ng serve` on 4200; a
  server started before an edit keeps serving the last good bundle. Check the
  server start time, or kill 4200 and let Playwright start its own. `tsc --noEmit`
  does not read templates — run `check:templates` before trusting an e2e result.
- Never falsify a template with `@if (false)` (compile error → last good bundle →
  false pass); invert the condition instead.
- Playwright calls an element "visible" if it has a box — assert what a person can
  reach, not what the DOM has. Register general `page.route` first, specific last.
- `getByLabel('Sort')` / `{ name: 'Page 1' }` substring-match — use `exact: true`
  or scope to the component. The `mobile` project (Pixel 7) widens the viewport
  above 412px; diagnose with `scrollWidth` vs `clientWidth`.
- Gates for UI: `check:templates` + `tsc -p tsconfig.app.json` + fresh dev server
  + the spec, then desktop + mobile.

## Writing UI/Playwright tests | كيف تُكتب اختبارات الواجهة
- **Select by role/label/text a user can perceive**, not CSS/DOM structure:
  `getByRole`, `getByLabel`, `getByText` — a CSS-selector test passes on a broken
  UI and breaks on a restyle.
- **Page Object per screen** — one place for that screen's locators and actions;
  specs read as user intent, not selector soup.
- **Assert the four states** every screen has: empty / loading / error / full. A
  test that only covers the happy path is half a test.
- **Accessibility in the e2e**: run `axe` on the page; assert keyboard reach and
  focus order for the primary flow (the product has an Accessibility Profile).
- **Falsify every new e2e** (workflow §5): break the feature, watch the spec fail
  *alone*, restore. In Angular, invert the condition — never `@if (false)` (compile
  error → last good bundle → false pass).
- **Web-first assertions** (`await expect(locator).toBeVisible()`), never a fixed
  `waitForTimeout`; for animation/opacity, poll to the target value.
- **Determinism**: stub the network for `desktop`/`mobile` projects (register
  general `page.route` first, specific last); `live` hits the real API with a
  seeded DB. Keep them separate — the owner runs `live` only when the server is up.

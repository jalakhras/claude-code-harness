# Review & documentation | المراجعة والتوثيق

## After every batch of code | بعد كل كود

Run **`/code-review-expert` and `/code-review`**, and fix what they find before
reporting («وبعد كل كود استخدم /code-review-expert و /code-review»). They earn
their place: they have caught a missing tie-breaker, a range sentence that lied on
an empty last page, and twelve docblocks promising a memory that no longer existed.

For deeper passes use the trimmed agents: `csharp-reviewer`, `typescript-reviewer`,
`database-reviewer`, `security-reviewer`, plus `silent-failure-hunter` and
`click-path-audit` when handlers may cancel each other out.

## Severity | مستويات الخطورة

| Level | Meaning | Action |
|---|---|---|
| CRITICAL | security/data-loss risk | BLOCK — fix before commit |
| HIGH | bug or significant quality issue | fix before commit |
| MEDIUM | maintainability (e.g. unexplained file over 800 lines) | consider |
| LOW | style | optional |

Address CRITICAL and HIGH; fix MEDIUM when possible.

## Mandatory security-review triggers | محفّزات المراجعة الأمنية

Stop and use `security-reviewer` when the change touches authentication/
authorization, user input, database queries, file operations, external API calls,
or cryptography. See `85-security.md`.

## Documentation | التوثيق

Update the relevant docs after every change («لا تنسى تحديث الوثائق»). For
long-lived projects, keep the four doc roles distinct (Constitution / Map / Status
/ History) so they do not rot. Record significant architectural choices as ADRs in
the vault (`<vault>\wiki\<project>\decisions.md`).

## Design work | التصميم

For any UI/design task, use the design skills and commands (`ui-ux-pro-max`,
`frontend-design`, `make-interfaces-feel-better`, `web-design-guidelines`,
`design-system`) — see `90-design.md` and `95-ui.md`.

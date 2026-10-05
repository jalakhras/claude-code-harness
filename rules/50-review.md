# Review & documentation | المراجعة والتوثيق

## After every batch of code | بعد كل كود

Match the review to what the batch touched (owner decision, 2026-10-03).
The two reviewers overlap; running both on every small batch doubles the tokens for
little gain, while dropping one everywhere loses what it alone catches in risky code.

| Batch touches | Run |
|---|---|
| copy, labels, docs, or tests only | `/code-review` |
| ordinary logic (UI or service) | `/code-review-expert` + `/code-review` |
| authentication, authorization/permissions, tokens/secrets, user input, security settings | both + `security-reviewer` |
| database queries, migrations, EF/ORM mappings | both + `database-reviewer` |

Fix what they find before reporting, and say in the report which reviews ran and why
(one line). The pair earns its place on real logic: it has caught a missing
tie-breaker, a range sentence that lied on an empty last page, and twelve docblocks
promising a memory that no longer existed («وبعد كل كود استخدم /code-review-expert و
/code-review», 2026-09 — now tiered as above).

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

# Security | الأمن

Covers defensive secure coding and the authorized offensive-security fence.

## Pre-commit checklist | قبل الإيداع

- [ ] No hardcoded secrets (keys, passwords, tokens, connection strings).
- [ ] All user input validated; parameterized queries (no string-concat SQL).
- [ ] XSS prevention (no unsafe `innerHTML`/`bypassSecurityTrust*` on user data).
- [ ] CSRF protection; authentication/authorization verified.
- [ ] Rate limiting on endpoints; sessions expire.
- [ ] Error messages don't leak secrets, stack traces, SQL, or paths.

## No system-structure leak | لا كشف بنية النظام

Never show the user the internal structure of the system — required-permission
names, entity names, internal error detail («لا يجب كشف بنية النظام للمستخدم»).
No sensitive data in URLs or console (ids, answers, questions).

## Authorization pairs | أزواج الصلاحيات

Every service guarded by `[Authorize]` needs a matching UI guard, and a
refused/allowed test pair whenever a guarded method is touched. An `[Authorize]`
attribute binds to whatever declaration follows it — never insert code between it
and its method (a real incident opened a review queue to the wrong permission).

## Secrets | الأسرار

Never hardcode. Use environment variables / user-secrets locally, a secret manager
in production. Validate required secrets are present at startup. Rotate anything
exposed. `security-scan` (AgentShield) audits the Claude config itself
(CLAUDE.md, settings, hooks, MCP).

## Response protocol | بروتوكول الاستجابة

On a security issue: **stop**, use `security-reviewer`, fix CRITICAL first, rotate
exposed secrets, sweep the codebase for the same pattern.

## Offensive security — owned assets only | السياج الأخلاقي

Lane 4 (pentesting) is permitted **only on assets jalakhras owns or has explicit
written permission to test.** Before any attack:
1. **Prove ownership/authorization** — the target (domain/IP/repo) is the owner's
   and is listed in `security-lab/scope.md`.
2. **Isolate** where possible — localhost/staging, not live production with real users.
3. **Document** what was run and when; store findings in `security-lab/findings/`
   (git-excluded) and reports in `<vault>\wiki\security\<target>.md`.

**Refuse** any target outside the scope list, and any request for generic
offensive techniques without an owned target — mass DoS, third-party targeting,
supply-chain compromise, or detection evasion for malicious purposes.

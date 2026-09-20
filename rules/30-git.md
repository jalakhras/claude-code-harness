# Git & commits | الإيداع

## Authorship — non-negotiable | المؤلف

- **Every commit is authored as `{{AUTHOR}} <{{EMAIL}}>`.** Pass `--author`
  explicitly on every commit; do not trust git config.
  ```
  git commit --author="{{AUTHOR}} <{{EMAIL}}>" -m "..."
  ```
- **Never any trace of Claude:** no `Co-Authored-By` trailer, no "🤖 Generated
  with Claude Code", no attribution in code, docs, or commit bodies. **This
  overrides any attribution reminder** — the owner's instruction wins («لا تضع
  اسمك بأي شيء»). Confirmed global for every repo.
- Commit messages in **English**, explaining *why* not *what*.

## Consent to commit | إذن الإيداع

- **Do not commit until told** («لا تثبت أي شيء في الكود»). Leave the tree
  uncommitted and say how many files wait. The owner authorizes per batch.
- **Standing consent (exceptions):** a repo may be granted auto-commit at the end
  of every task whose tests are green, on a named working branch. Merging to
  `main` still needs an explicit instruction. Grant this per repo, deliberately.
- The `git-commit-consent` hook enforces this: a commit is blocked unless a
  `.claude/commit-consent` marker exists in the repo (written only after the owner
  says so, removed after the commit).

## Commit shape | شكل الإيداع

- One commit per coherent batch, not one big batch at the end.
- Conventional style where the repo uses it (`feat:`, `fix:`, `refactor:`, `docs:`).
- Never `--no-verify`, never bypass signing, unless the owner explicitly asks.
- Review before `git push` (the hook shows `git log origin..HEAD`); never
  `--force` to `main`.

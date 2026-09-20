---
paths:
  - "**/*.cs"
  - "**/*.csproj"
  - "**/appsettings*.json"
---
# C# / .NET / ABP | قواعد C#

Extends `common` rules for C# on ABP / .NET / EF Core.

## Idioms

- `sealed record` for DTOs and value objects; strongly-typed Options over raw config.
- Depend on interfaces at boundaries; register DI lifetimes intentionally
  (singleton stateless, scoped per-request, transient light workers).
- Repository/AppService per ABP conventions; a decision is a domain function all
  callers use (see `40-testing.md`).

## Security

- Parameterized queries only (EF Core / Dapper); validate sort fields before
  dynamic query composition. Validate DTOs at the application boundary
  (data annotations / FluentValidation / guard clauses).
- Framework auth handlers, not custom token parsing; enforce policies at the
  handler boundary. Never log tokens/PII. Safe client messages; detailed logs
  server-side. Keep `appsettings.*.json` free of real credentials.

## EF Core traps | فخاخ EF

- `dotnet ef migrations add` uses `--startup-project ...HttpApi.Host` and **never
  `--no-build`** (it scaffolds an empty/ wrong migration from a stale assembly).
- Never falsify a migration by deleting its `__EFMigrationsHistory` row (SQL 2705,
  DB stuck).
- `dotnet build` of the solution fails with MSB3027 file locks while the host
  runs — build test projects individually.
- ABP 10.6 `AbpEfCoreNavigationHelper` marks a principal modified for any FK
  pointing at it; use the `QuietPrincipalNavigationHelper` backport.
- An `[Authorize]` attribute binds to whatever declaration follows it — never
  insert a class/member between the attribute and its method.

## Testing

xUnit + FluentAssertions/Shouldly. Unit (Domain/Application.Tests) + integration
(EntityFrameworkCore.Tests). The shared in-memory SQLite connection means a second
unit of work must be non-transactional on both sides. Rebuild before
`dotnet test --no-build` after restoring a falsified `.cs`.

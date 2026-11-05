# Project notes (not part of upstream)

- Source: https://github.com/cloudflare/security-audit-skill (MIT), skill `security-audit`
- Commit: c1c8a8c1471069fb0e188eeaff69b8e8db6564a8 (committed 2026-09-14), installed 2026-11-04 by manual copy.
- Upstream files are unmodified, except for one added line at the top of SKILL.md.

## References intentionally omitted

- `MEMORY-SAFETY-AND-BINARY.md`: this project has no native or binary code (Python, Kotlin).
- `CLIENT-SIDE.md`: there is no web client (the client is a native Android app).
- `PROTOCOLS-RPC-AND-MESSAGING.md`: there is no RPC, queue or broker layer (plain REST).
- Upstream tests, README and repo tooling are not needed at audit time.

Links to these files inside the kept files are expected to be dead. Skip them.

## Target surfaces

FastAPI REST API (`POST /api/conversation`, sessions), LangChain agent with tools over Postgres (prompt injection, tool abuse, number guard), PostgreSQL and Docker Compose configuration, the OpenRouter key and its USD 10 budget (spend/availability), the data ingestion pipeline (PDF/OCR/JSON), and the native Android app (manifest, network config, local storage, debug screen).

## Defaults for this project

- Output directory (decided 2026-11-04, user delegated the choice): raw run artifacts go to `docs/security/runs/run-<N>/` (next unused N). `docs/security/runs/` is in `.gitignore`, so the whole output directory is ignored by version control, as SKILL.md requires. After each run, a reviewed summary is written to `docs/security/REPORT.md` (committed): scope, confirmed findings and their fixes, hardening notes, needs_validation triage. It carries no exploit payloads beyond what the tests already contain.
- No OS sandbox is available: never execute target code (no builds, tests, servers, emulators, docker). Source inspection only. Leads that need execution stay `needs_validation`.
- Never call OpenRouter or any live endpoint during the audit (spends the budget).

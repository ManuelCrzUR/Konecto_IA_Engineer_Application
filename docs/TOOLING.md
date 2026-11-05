# AI tooling used in this project

Everything below is committed (`.claude/`, `.mcp.json`, `skills-lock.json`) so reviewers can reproduce the setup.
No secrets are stored in any of these files. Installation date: 2026-11-03.

| Tool | Source | Version / commit | Installed | Used for |
|---|---|---|---|---|
| LangChain skills (6 kept: `langchain-fundamentals`, `langchain-middleware`, `langchain-dependencies`, `ecosystem-primer`, `swarm`; pruned from the 22 upstream) | `langchain-ai/langchain-skills` via `npx skills add` | no commit recorded; per-skill `computedHash` in `skills-lock.json` | 2026-11-03 | Building the LangChain agent, tools and tests (backend `agent/`); `swarm` for the extractor benchmark and parallel eval runs |
| `supabase-postgres-best-practices` skill | `supabase/agent-skills` via `npx skills add` | hash in `skills-lock.json` | 2026-11-03 | Schema design, typed columns, indexes, idempotent upserts (`db/`) |
| `android-skills` plugin | `android/skills` marketplace, project scope (`.claude/settings.json`) | marketplace HEAD `6daa53ef27fa2aa87827d183a85c06cedceca833` at install time | 2026-11-03 | Official Android guidance for the Compose app (`mobile/`) |
| `android-development` skill | `github.com/dpconde/claude-android-skill` (copied, no `.git`) | `edfca5e36ceb7532708c28fd2fd5215a9f01d105` | 2026-11-03 | Architecture/MVVM/Compose conventions for the Android app |
| MCP `mobile` | `@mobilenext/mobile-mcp` | pinned `1.0.16` | 2026-11-03 | Drive an emulator/device to test the app (`.mcp.json`) |
| MCP `docs-langchain` | `https://docs.langchain.com/mcp` (HTTP) | n/a (remote) | 2026-11-03 | Up-to-date LangChain docs lookup |
| MCP `reference-langchain` | `https://reference.langchain.com/mcp` (HTTP) | n/a (remote) | 2026-11-03 | LangChain API reference lookup |
| `security-audit` skill (Cloudflare, MIT) | `github.com/cloudflare/security-audit-skill` (manual copy, no `.git`) | `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8` | 2026-11-04 | Sprint 6 security audit of the API, agent, Postgres/Docker config and Android app. Kept: workflow files, 7 relevant attack-class references, `report-schema.json`, the 2 zero-dependency validators, `LICENSE`. Omitted: memory-safety, client-side and RPC/messaging references, tests, README. See `.claude/skills/security-audit/PROJECT-NOTES.md` |

## Reviewed, NOT installed

| Candidate | Repo @ commit | Summary | Flags |
|---|---|---|---|
| `fastapi-expert` | `jeffallan/claude-skills` @ `078a25cc` | Async FastAPI, Pydantic v2, SQLAlchemy, JWT/OAuth2 guidance | Markdown only; placeholder secrets in examples |
| UX Heuristics | `wondelai/skills` @ `d8d5d75f` | Nielsen/Krug usability audit framework | Markdown only; affiliate links to books |
| evals-skills | `hamelsmu/evals-skills` @ `22418da2` | 7 skills for error analysis, LLM-judge design/calibration, RAG evals | Markdown only; optional `pip install judgy` in an example |

## Security review notes

- All third-party content was treated as data. No skill file was found asking to ignore rules, exfiltrate data or request credentials.
- Mentions of API keys in skills (`LANGSMITH_API_KEY`, etc.) are setup documentation with placeholders.
- Skills that ship executable files: `swarm` (TypeScript), `android-development` (`generate_feature.py`). Grep found no network/subprocess calls in them; they are only run if explicitly invoked.
- `security-audit` (2026-11-04): Markdown plus two local Node scripts (`validate-*.cjs`, only `fs`/`path`/`util`, no network or subprocess calls; read before copying). No install hooks. No OS sandbox is available, so the audit is source-only and never executes project code or calls OpenRouter.
- Pruned on 2026-11-03 (out of scope: the agent uses `create_agent` with its own history in Postgres, no LangGraph graph, no RAG, Python backend): `deep-agents-*` (3), `deepagents-*-quickstart` (2), `langchain-python-quickstart`, `langchain-typescript-quickstart`, `langgraph-*` (8, incl. quickstarts), `managed-deep-agents`, `langchain-rag`, `eval-engineering`. `swarm` is kept conditionally and can be removed once the extractor benchmark is done.

## Manual steps (not done by the agent)

1. Context7: with Node >= 22.13 run `npx ctx7 setup --claude` (browser login). Keep the API key out of the repo; if it goes in `.mcp.json`, use an environment variable.
2. Android Studio (preview build if the CLI's `android studio` commands are wanted).
3. Android CLI 1.0: install per d.android.com/tools/agents and run `android init`.
4. Restart Claude Code and approve the project MCP servers on first use.

# AI tooling used in this project

Everything below is committed (`.claude/`, `.mcp.json`, `skills-lock.json`) so reviewers can reproduce the setup.
No secrets are stored in any of these files. Installation date: 2026-11-03.

The "Used for" column describes only what the repo or the docs show. Where a tool is configured but its use is not recorded, the table says so.

| Tool | Source | Version / commit | Installed | Used for |
|---|---|---|---|---|
| LangChain skills (5 kept: `langchain-fundamentals`, `langchain-middleware`, `langchain-dependencies`, `ecosystem-primer`, `swarm`; pruned from the 22 upstream) | `langchain-ai/langchain-skills` via `npx skills add` | no commit recorded; per-skill `computedHash` in `skills-lock.json` | 2026-11-03 | `langchain-fundamentals`: the agent is built with `create_agent` (`backend/app/agent/agent.py`). `langchain-middleware`: `TraceRecorder(AgentMiddleware)` in the same file. `langchain-dependencies`: the pins in `backend/pyproject.toml`. `ecosystem-primer`: the framework choice in D-08 (`create_agent` over LangGraph and Deep Agents). `swarm`: not used. The eval runner is `backend/eval/run.py` and has its own `ThreadPoolExecutor`. The skill stays only because it is part of the vendored LangChain skill set |
| `supabase-postgres-best-practices` skill | `supabase/agent-skills` via `npx skills add` | hash in `skills-lock.json` | 2026-11-03 | Schema and query practices in `backend/app/db/` (typed columns, CHECK constraints, `ON CONFLICT` upsert, parameterized SQL, D-03, D-04). The docs do not record an explicit invocation |
| `android-skills` plugin | `android/skills` marketplace, project scope (`.claude/settings.json`) | marketplace HEAD `6daa53ef27fa2aa87827d183a85c06cedceca833` at install time | 2026-11-03 | Enabled for the Compose app (`mobile/android`). The individual plugin skills are listed in the next table |
| `android-development` skill | `github.com/dpconde/claude-android-skill` (copied, no `.git`) | `edfca5e36ceb7532708c28fd2fd5215a9f01d105` | 2026-11-03 | Feature-package layout and MVVM/Compose conventions for the Android app (`ARCHITECTURE.md` §5) |
| MCP `mobile` | `@mobilenext/mobile-mcp` | pinned `1.0.16` | 2026-11-03 | Configured in `.mcp.json` to drive an emulator or device. Used for the E2E checks and screenshots of Gates 5 and 5.5 |
| MCP `docs-langchain` | `https://docs.langchain.com/mcp` (HTTP) | n/a (remote) | 2026-11-03 | Configured in `.mcp.json` for LangChain docs lookup. No recorded use in the docs |
| MCP `reference-langchain` | `https://reference.langchain.com/mcp` (HTTP) | n/a (remote) | 2026-11-03 | Configured in `.mcp.json` for LangChain API reference lookup. No recorded use in the docs |
| `security-audit` skill (Cloudflare, MIT) | `github.com/cloudflare/security-audit-skill` (manual copy, no `.git`) | `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8` | 2026-11-04 | Sprint 6 security audit of the API, agent, Postgres/Docker config and Android app (two runs, committed report in `docs/security/REPORT.md`; raw runs in `docs/security/runs/` are gitignored). Kept: workflow files, 7 relevant attack-class references, `report-schema.json`, the 2 zero-dependency validators, `LICENSE`. Omitted: memory-safety, client-side and RPC/messaging references, tests, README. See `.claude/skills/security-audit/PROJECT-NOTES.md` |

### Plugin skills, built-ins and their recorded use

These are not installed in the repo. They are available in the Claude Code environment. Use was recorded in the development sessions: each subagent prompt named the skill to invoke first, and the gates invoked the built-ins directly.

| Item | Kind | Use in this project |
|---|---|---|
| `android-development` | installed skill | Every Android subagent in Sprints 5 and 5.5 (screens, theme, splash, Axel avatar, data layer) |
| `edge-to-edge` | `android-skills` plugin | Sprint 5.5: splash and the inset/IME audit; result: `enableEdgeToEdge()` with theme-aware bar styles and the shared `AxelHeader` that pads for the status bar |
| `jetpack-compose-performance` | `android-skills` plugin | Sprint 5.5: Axel avatar animations (values read in draw/graphicsLayer, no per-frame recomposition) and the chat `LazyColumn` audit (stable keys, `contentType`) |
| `navigation-event` | `android-skills` plugin | Sprint 5.5: predictive back for the NavHost transitions (`android:enableOnBackInvokedCallback="true"`); Navigation Compose animates the pop with the gesture, so no `navigationevent` dependency was needed. Search mode uses `BackHandler` to clear the query |
| `testing-setup` | `android-skills` plugin | Sprint 5.5: instrumented tests for theme, search, suggestions, CSA chip and splash (27 instrumented tests) within the existing JUnit4 + Compose UI test setup |
| `supabase-postgres-best-practices` | installed skill | Sprints 1, 2, 4 (schema, upsert, indexes) and the conversation search SQL (D-37) |
| `security-audit` (Cloudflare) | installed skill | Sprint 6: audit run-1 and run-2 (`docs/security/REPORT.md`) |
| `code-review` | built-in | Gates 2, 3 (D-31), 5 (D-36) and 5.5 |
| `simplify` | built-in | Gate 5.5 (four parallel reviewers; shared header and theme tokens, persona palette default, search SQL cleanup) |
| `security-review` | built-in | Attempted at Gate 4 and could not run: the repo had no remote (`origin/HEAD`); replaced by a manual review (D-34) and, in Sprint 6, by the `security-audit` skill |
| `run` | built-in | Gate demos: backend stack, CLI, eval and the Android app on the emulator |
| MCP `mobile` | MCP server | Driving the emulator for E2E checks and screenshots (Gates 5 and 5.5) |

### Sprints 8 and 9: skills per task

Source: the "Skills per task" tables and the wave logs in `docs/plans/SPRINT-8.md` and `docs/plans/SPRINT-9.md`. The status column is the plan's status. Rows marked "planned" have not been done yet.

| Sprint and wave | Task | Skill or built-in | What the plan records |
|---|---|---|---|
| 8, wave 1 | OCR fix (table T3) | `anthropic-skills:pdf` | Real vision run and OCR fix (D-49) |
| 8, wave 1 | History window, small talk, follow-up referent | `langchain-fundamentals`, `langchain-middleware` | History window (D-45) and referent (D-47) |
| 8, wave 1 | Schema, per-session lock, auth tables | `supabase-postgres-best-practices` | Lock (D-46) and auth tables |
| 8, wave 2 | Login backend | `security-audit`, `supabase-postgres-best-practices` | Login (D-43) |
| 8, wave 4 | Android: login screen and tests | `android-development`, `testing-setup` | Login (D-43) |
| 8, wave 4 | Android: voice input permission | `android-permissions-security` | Microphone (`RECORD_AUDIO`) for voice (D-48) |
| 8, wave 4 | Android: touch targets | `adaptive` | 48 dp touch targets |
| 8, wave 5 | Gate | `simplify`, `code-review` (built-ins), `security-audit` | `/simplify` and `/code-review`; scoped audit of authentication and per-user isolation |
| 9, wave 1 | 1A number guard (field binding) | `langchain-fundamentals` | D-51; black-box tests written by a Haiku subagent from the decision text |
| 9, wave 1 | 1B OCR split | `anthropic-skills:pdf` | `ocr.py` split into `ocr_boxes`, `ocr_layout` and `ocr_cells`; no logic change |
| 9, wave 1 | 1C login limit | `security-audit`, `supabase-postgres-best-practices` | Login attempt limit (D-52) |
| 9, wave 1 | 1D eval cases | `langchain-fundamentals` | `tools_any` expectation and field-binding cases (52 cases in total) |
| 9, wave 3 | Tablet screenshots | `android-development` (adb on the Lenovo Tab M11) | Done: sign in, voice dictation and answer, Debug; unused images removed |
| 9, voice V2-A | Backend: `POST /api/transcribe`, OpenRouter client, per-user limiter, `python-multipart` (D-53) | `security-audit` | Built; 22 route and client tests |
| 9, voice V2-B | Transcript normalizer (`backend/app/speech/normalize.py`, D-53) | `langchain-fundamentals`, plus black-box tests by a Haiku subagent | Built; 128 normalizer tests, 25 of them black-box |
| 9, voice V2-C | Android: recording, cloud transcription and fallback (D-53) | `android-development`, `android-permissions-security` | Built; 153 JVM unit tests |
| 9, extra | Login animation (`login/WelcomeSpin.kt`) | `android-development`, `jetpack-compose-performance` | Done: unit tests, lint, `LoginScreenTest` 3/3 on the emulator |
| 9, wave 4 | Gate | `/code-review` high (built-in) over the whole Sprint 9 diff; fixes by subagents with `langchain-fundamentals`, `security-audit` and `android-development` | Done: 10 issues found and fixed (normalizer false joins, overwritten ingestion tests restored, guard binding, login lockout and atomicity, upload size before parsing, timeouts, recorder race). `/simplify` not run separately: the review covered the same diff |

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
- Pruned on 2026-11-03 (out of scope: the agent uses `create_agent` with its own history in Postgres, no LangGraph graph, no RAG, Python backend): `deep-agents-*` (3), `deepagents-*-quickstart` (2), `langchain-python-quickstart`, `langchain-typescript-quickstart`, `langgraph-*` (8, incl. quickstarts), `managed-deep-agents`, `langchain-rag`, `eval-engineering`. `swarm` was kept for a possible eval fan-out; it was never used (the eval runner has its own `ThreadPoolExecutor`) and stays only as part of the vendored set.

## Manual steps (not done by the agent)

1. Context7: with Node >= 22.13 run `npx ctx7 setup --claude` (browser login). Keep the API key out of the repo; if it goes in `.mcp.json`, use an environment variable.
2. Android Studio (preview build if the CLI's `android studio` commands are wanted).
3. Android CLI 1.0: install per d.android.com/tools/agents and run `android init`.
4. Restart Claude Code and approve the project MCP servers on first use.

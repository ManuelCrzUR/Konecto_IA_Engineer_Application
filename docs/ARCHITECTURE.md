# Architecture: Series 76 Technical Assistant

This is the durable design document. It replaces `docs/ARCHITECTURE_V1.md` as the source of truth. The decisions behind it, with their trade-offs, are in `docs/DECISIONS.md`. The product brief and the working rules are in `CLAUDE.md`.

## 1. Overview

```
 Android app ──HTTP──► FastAPI (api/) ──► agent/ ──► tools ──► db/actuators_repo ──► Postgres
   Chat / Conversations / Debug            │                                          ▲
                                            └─► db/sessions_repo (sessions, messages) ─┤
 PDF ► ingestion/ (OCR + flags + escalation) ► actuators.json ► bootstrap.ensure_data() ┘
```

Dependencies point only downward: `api → agent → db/domain`; `bootstrap → ingestion + db`; `ingestion → domain`; `db → domain`. Nothing imports upward. The entry points (`cli.py`, `ingest.py`, `api/main.py`) contain no logic.

## 2. Data: self-healing chain

```
 ensure_data() (runs at API start, in the CLI and in ingest.py)
  1. Does COUNT(*) in Postgres equal the row count of the JSON, and is the JSON valid?  → done
  2. If not: does actuators.json exist and pass validate()?                              → upsert to Postgres
  3. If not: PDF → OCR → flags → escalation → validate() → write JSON → upsert
  4. If validate() fails: abort with a clear message; do not load doubtful data
```

- "Has data" means an exact row count, not "not empty". This detects partial loads.
- The upsert is idempotent (`ON CONFLICT (part_number) DO UPDATE`): running it again neither duplicates nor breaks anything.
- The JSON is never overwritten without `--force` (CLAUDE.md §9). The normal path (committed JSON) needs no internet and no key.
- OpenRouter is used only in step 3, and only for flagged tables. The current extractor is RapidOCR, offline, on 2× crops. A cell is suspicious if its confidence is below 0.9, if it has a leading zero, or if a validator fails. Those whole tables go to a vision model (Sonnet 5.5). Without a key, the run fails and lists the suspicious cells.
- Real escalation run (Sprint 8, D-49): Verified on 2026-11-06 (Sprint 8): offline OCR reads all 68 rows at 99.75% cell accuracy and flags 8 cells in 4 tables; vision (`anthropic/claude-sonnet-5.5`) re-read those 4 tables in 4 calls for USD 0.029, and the output was byte-identical to the committed `actuators.json` (0 cells differ from the golden file). Costs are logged in `docs/spend-log.md`. Still pending: testing the flag rule on other PDFs.

### Data model

One row per (table, part number). Columns are typed and nullable. The field names are the flat schema of the benchmark, with the names below. The benchmark itself lives outside this repo; the golden copy is `backend/tests/fixtures/golden_draft.json` (D-16).

```python
class Actuator(BaseModel):
    table_id: Literal["T1_wp_110v_1ph", "T2_wp_220v_1ph", "T3_wp_220v_3ph",
                      "T4_xp_24v_onoff", "T5_xp_24vdc_mod", "T6_xp_110v_1ph", "T7_xp_220v_1ph"]
    part_number: str            # unique; as printed, without "*", e.g. 761A00-11300000/A
    csa_certified: bool         # False only when the printed part number carries "*"
    enclosure: Literal["weatherproof", "explosionproof"]   # from the section title
    certifications: str         # e.g. "CSA, CE, & UKCA" or "CSA"
    voltage: str                # as printed: "110V", "220V", "24V AC/DC", "24V DC"
    current_type: Literal["AC", "DC", "AC/DC"]
    phase: Literal[1, 3] | None
    service: Literal["on_off_and_modulating", "on_off", "modulating", "unspecified"]
    # numeric and nullable (null = column absent in this table, or printed N/A)
    onoff_torque_in_lbs, onoff_torque_nm, onoff_duty_cycle_pct, cycles_per_hour: float | None
    mod_torque_in_lbs, mod_torque_nm, mod_duty_cycle_pct, starts_per_hour: float | None
    output_torque_in_lbs, output_torque_nm, duty_cycle_pct: float | None   # single-value tables (T3)
    speed_sec_60hz, speed_sec_50hz, speed_sec: float | None
    fla_60hz_a, fla_50hz_a, fla_a: float | None
    lra_60hz_a, lra_50hz_a, lra_a: float | None
    motor_power_w: float | None
    # bookkeeping
    row_index: int | None       # 1-based order within the table
    has_data: bool              # False for the 4 N/A rows (761A, 761B, 762A, 762B in T3)
    table_notes: str | None     # tolerances, IEC 60034-1, hazardous-area classification
    unparsed: dict[str, str]    # field -> raw text that could not be parsed (from the benchmark schema)
```

Field families (which tables fill them): on/off torque, duty and cycles/h in T1, T2, T4, T6, T7; modulating torque, duty and starts/h in T1, T2, T5, T6, T7; single output torque and duty in T3; speed without Hz in T4 and T5 (`speed_sec`, `fla_a`, `lra_a`); speed, FLA and LRA at 60 and 50 Hz in T1, T2, T3, T6, T7.

**Three-phase decision (values as printed).** T3 prints one torque and one duty cycle for the whole table. They are stored only in `output_torque_*` and `duty_cycle_pct`, exactly as printed. They are not copied into the on/off or modulating columns, so no value is duplicated or inferred. Search resolves the torque as follows:

- When the service is `unspecified`: `COALESCE(onoff_torque, mod_torque, output_torque)`.
- When the service is `on_off` or `modulating`: `COALESCE(family torque, output_torque)`.

This keeps the rule "values as printed" and still lets one filter cover every table.

### Schema

The schema is `db/schema.sql`: typed columns, CHECK constraints (enclosure, service, duty 0 to 100), a UNIQUE constraint on `part_number`, and indexes for the filters. Full description in DECISIONS (D-04, D-05, D-06).

Conversations (same database, same `pgdata` volume):
- `sessions(id uuid, user_id null, title, created_at, updated_at)`
- `messages(id, session_id fk, role, content, products jsonb, trace jsonb, created_at)`

`user_id` is nullable: it is the hook for login. The title is built from the first ~50 characters of the first query, without calling an LLM.

## 3. Agent and number rules

- `agent/agent.py`: `run_agent(query, history=[])` built with LangChain's `create_agent()` (skill `langchain-fundamentals`). There is no checkpointer: we store the history ourselves in `messages` and pass it as a list.
- Tools (parameterized SQL; the LLM never writes SQL):
  - `get_actuator(part_number)`: normalizes the input; returns found, found without data (N/A), not found with suggestions, or partial match with candidates.
  - `search_actuators(requirements)`: torque with unit Nm or in-lbs, voltage, phase, enclosure, service, speed and duty; sorted by the tightest match. If nothing matches, it says which constraint blocked the search and gives the closest available value.
  - `describe_catalog()`: used for ambiguous questions.
- Multi-turn follow-up ("and how much power does it draw?"): when the history is built, a context line with the part numbers from the previous turn's `products` is added. The prompt requires the model to **call the tool again** for any number, because the LLM does not remember figures.
- Tool errors (`agent/agent.py`, `_tool_error`): argument errors (`ValueError`, `ToolException`) go back to the model with their message, so it can fix the call. Any other exception becomes `{"error": "internal_tool_error"}` in the tool message and in the stored trace; the real exception is logged on the server only (D-39).
- `agent/response.py` builds `products[]` from the tool outputs (code, not LLM). Number guard v2 (D-44; extraction in `agent/numbers.py`): every number in the text, digits or number words (English and Spanish, two to twenty), must come from the tool results, the current query, or the user's earlier turns (D-26, D-40). A figure after a part number in the same sentence or table row must be a value of that product; with a single-product follow-up the figures bind to that referent (`agent/referent.py`, D-47). Free without a source: list ordinals, the 90° stroke, counts of the lists a tool returned, the three-digit model size of a returned part number, and the family name "Series/Serie/Série 76" (D-38). If a number is not verified, a deterministic template answer is used and noted in `trace`.
- Persona (`apply_persona()` in `agent/response.py`, D-39): after the number guard, the model's own name, derived from its model id, is replaced with "Axel". If anything was replaced, a `persona_guard` entry is added to `trace`, so the change is never silent. The prompt also defines the Axel identity and the small-talk rule.
- Models are set by environment variable and by task: `AGENT_MODEL` (cheap while iterating, good for the final run) and `EXTRACT_LLM_MODEL` (OCR escalation, Sonnet 5.5). Development eval runs use OpenRouter's free `stealth/crouton-alpha` model (D-29); the Google AI Studio plan was dropped. The OpenRouter key is used only with explicit permission. No LLM translation of titles and no embeddings (no pgvector).
- Language: the answer is in the user's language; numbers and part numbers are kept as they are.

## 4. API (FastAPI)

- `POST /api/conversation` returns `{session_id, answer, products[], debug}`. Each item in `products[]` is `{part_number, enclosure, voltage, phase, service, fields:{...values with units...}, csa_certified, notes[]}`. The app shows them as comparable cards (one column per product). `debug` is a list of `{tool, params, result}`. It is **always present in the response**; the user-facing app does not show it.
- `GET /api/sessions?q=&limit=` (`id, user_id, title, created_at, updated_at`; with `q`, only matching sessions, each with `match {where, snippet}`, D-37) and `GET /api/sessions/{id}/messages` (includes `products` and `trace`). The search is `db/sessions_search.py` (case-insensitive `ILIKE` over titles and message contents, one query, `LIKE` wildcards escaped); the snippet is built by the pure function `db/snippet.py`. The route is in `api/routes_sessions.py`.
- An unknown `session_id` returns **404** with a clear message. Sessions are never created by accident. With no `session_id`, a session is created and returned.
- Login (D-43): `POST /api/auth/login` returns an opaque token (7 days); `POST /api/auth/logout`, `GET /api/auth/me`. `deps.get_current_user` reads `Authorization: Bearer`, looks up the SHA-256 of the token in `auth_tokens` (short pooled borrow) and answers 401 `unauthorized` otherwise; every `/api` route except login depends on it, `/health` is public. `users` holds argon2id hashes (`app/auth/`); three test users are seeded at startup (`app/auth/seed.py`, `SEED_TEST_USERS`). Every `sessions_repo` call receives `user.id`, so another user's session answers 404. For role `user` the API returns `debug`/`trace` empty; only `developer` receives the tool trace.
- Voice hook: **transcription on the device** (Android `SpeechRecognizer`). The text goes to the same endpoint. No budget cost and no backend change.
- Errors: a uniform JSON body `{error, detail}` (`api/errors.py`). A timeout or a dead LLM returns a generic 503, without internal detail and without losing the user's message, which is already saved (D-34).

## 5. Android app (`mobile/android`)

One Gradle module with packages by feature (KISS; the `android-development` skill and the `android-skills` plugin apply): `splash/`, `conversations/` (list and search results), `chat/`, `debug/`, `data/` (Retrofit + kotlinx.serialization, one `ApiClient`, `ThemePreferences`), `ui/` (`theme/`, `axel/` character, `ProductCard`, `ComparisonTable`, `KeyFigures`). MVVM: `ViewModel` + `StateFlow`; Navigation Compose; manual DI.

- Loading and error states on every screen (backend down, timeout).
- Backend URL in `BuildConfig.API_BASE_URL`: default `http://localhost:8000/`, overridable with `api.baseUrl` in `local.properties`. The emulator or a USB phone reaches it through `adb reverse` (`make android-reverse`, D-35). The emulator alias `10.0.2.2` is not used.
- Debug: opened with a hidden gesture (5 taps on the chat title within 3 seconds, `chat/TapCounter.kt`). It shows the `debug` of each response. Documented in the README.
- The chat never shows tool names or traces.
- Redesign ("Axel", Sprint 5.5): dark, light or system theme, chosen from the header menu and stored with DataStore (`data/ThemePreferences.kt`); a splash screen; the Axel character and launcher icon; conversation search, which calls `GET /api/sessions?q=` and shows the matching snippet.
- Design references: `mobile/android/DESIGN.md` is the contract (themes, motion, states); `docs/design/` holds the visual reference in dark and light.
- Tests: JVM unit tests in `app/src/test`, Compose UI tests in `app/src/androidTest` (run on the emulator).

## 6. Backend modules (≤ ~150 lines each, tested on their own)

```
backend/
├── pyproject.toml
├── app/
│   ├── domain/{models.py,conversation.py,search.py}   # Actuator (single contract), Product, ToolTrace; conversation and search contracts
│   ├── ingestion/{ocr,flags,escalate,normalize,validate,pipeline,store_json,crops,table_meta}.py
│   ├── db/{schema.sql,connection.py,actuators_repo.py,search_sql.py,sessions_repo.py,sessions_search.py,snippet.py}
│   ├── bootstrap.py                # ensure_data()
│   ├── llm.py                      # get_llm(task) (D-19)
│   ├── agent/{tools,prompts,agent,response}.py
│   └── api/{main.py,schemas.py,deps.py,errors.py,routes_conversation.py,routes_sessions.py}
├── Dockerfile   pyproject.toml   cli.py   ingest.py
├── data/{raw/series_76_electric_data.pdf, processed/actuators.json}
├── eval/   tests/   docker/initdb/
mobile/android/
docs/{ARCHITECTURE.md, DECISIONS.md, TOOLING.md, security/REPORT.md}
docker-compose.yml  Makefile  .env.example  README.md
```

No ORM (`psycopg` with parameterized SQL). No `DataSource` or `Extractor` interfaces, and no `EXTRACTORS=...` setting: there is one extractor. One `pyproject.toml`, managed with `uv` (D-12).

## 7. Infrastructure

- `docker-compose.yml`: `db` (postgres:16, `pgdata` volume, `pg_isready` healthcheck) and `api` (`depends_on: service_healthy`; at start it runs `ensure_data()` and then uvicorn).
- `backend/Dockerfile`: `python:3.12-slim`. `rapidocr-onnxruntime` ships the ONNX models, so OCR works offline. It uses the headless OpenCV build, so no GUI libraries are installed (D-33).
- `db` publishes Postgres and `api` publishes the API only on `127.0.0.1` by default (`DB_BIND`, `API_BIND`; D-34). Physical phones need `API_BIND=0.0.0.0`.
- `.env.example`: `DB_PORT`, `API_PORT`, `API_BIND`, `DB_BIND`, `DATABASE_URL`, `TEST_DATABASE_URL`, `LLM_BASE_URL`, `LLM_API_KEY`, `AGENT_MODEL`, `EXTRACT_LLM_MODEL`, `STARTUP_ESCALATION`, `AGENT_MAX_TOKENS`, `EXTRACT_MAX_TOKENS`, `VISION_MAX_CALLS`, `HISTORY_TURNS`. No secrets.
- `Makefile` (shortcuts only): `up` (waits for a healthy API), `down`, `reset` (deletes the volume and reloads), `logs`, `db`, `ingest` (`ARGS=--force`), `ingest-pdf` (PDF rebuild in Docker into `backend/data/rebuilt/`, D-49), `test`, `eval`, `chat` (`ARGS=--debug`), `android-reverse` (`adb reverse` for the app, D-35), `recovery` (self-healing check on the real stack). `make help` lists them.
- Recovery documented in the README: database deleted → `make up`; JSON deleted → `make up` (rebuilt from Postgres when it holds the full catalog, otherwise re-extracted from the PDF, D-49); everything broken → `make reset`.

## 8. Testing and evaluation

- Unit tests per module, without a real LLM: `validate`, `flags`, `normalize`, repositories (test Postgres), tools, `response` (number guard), and the API with a simulated agent.
- Self-recovery test (main acceptance criterion): (a) `docker compose down -v && make up` → 68 rows; (b) delete `actuators.json` → it is regenerated and validated; (c) delete rows in Postgres → the count is corrected; (d) corrupt JSON → detected and re-extracted; (e) restart the API → conversations still there.
- `eval/`: 45 cases in `eval/cases.yaml`, by category: lookup 4, recommend 5, ambiguous 3, impossible 3, invalid_pn 3, na 2, out_of_subset 3, multi_turn 5, small_talk 5 (Sprint 8), and injection 12 (prompt-injection and persona cases, 38/38 with the development model, `docs/security/REPORT.md`). Deterministic assertions on the tool called, its status, the part numbers in `products`, the exact numbers in the answer, `answer_includes` (required phrases, used for the persona cases), and whether the number guard fired. Cheap model while iterating; the good model only in the final run (Sprint 7).
- Final test from scratch on a clean machine, following only the README (mandatory requirement).

## 9. Build order and parallel tracks

- **Phase 0 (sequential)**: `domain/models.py`, `schema.sql`, signatures of `actuators_repo`, `sessions_repo` and the tools, the `ConversationResponse` schema, `pyproject.toml`, compose, `CLAUDE.md`.
- **Tracks** (one folder each): A `ingestion/` + `bootstrap.py`; B `db/`; C `agent/tools.py`; D `agent/` (LLM, agent, response, eval); then E `api/`; F `mobile/android` (can start with a fake server that follows the contract in §4).
- **Phase 2 (sequential)**: integrate, run `eval/` on real data, README, clean-machine test.
- If there is time left: login (endpoint + `users` + dependency) and voice in the app.

The active delivery plan is §11. This section describes the dependency structure behind it.

## 10. Testing strategy

- **Micro-task** = 1 module + 1 test file, at most ~150 lines. Small tasks keep a subagent fast and keep any error contained.
- **Builder subagents** (Sonnet or Haiku) each invoke the skill named for their task first, then implement one module against its contract (signatures and docstring), touching only their own files.
- **Black-box test-writer subagents** write the tests for critical modules (normalize, validate, repositories, tools, response, API) from the contract alone, without seeing the implementation. This stops the builder from testing what it wrote.
- **Waves**: tasks with no dependencies between them run in parallel, each in its own git worktree. The lead (Opus) fixes the contracts for each wave and merges the results.
- **Verifier checklist** (Haiku), run at every gate:
  1. `uv run pytest -q --cov` passes, with coverage ≥ 80% on new code.
  2. `ruff check` and `mypy` report no errors.
  3. Signatures match the contract; layer rules hold (grep for imports that point upward).
  4. CLAUDE.md §9: no keys or `.env` in the repo; no f-string SQL (`execute(f"`); `actuators.json` unchanged.
  5. No test calls a real LLM (fake or mock models only).
  6. One entry in `docs/DECISIONS.md` for each decision made in the sprint.
- **Test database**: `series76_test` on the same Postgres container. The `pg` fixture truncates tables between tests. Tests never touch the development database.
- **`slow` marker**: tests that run real OCR on the PDF are marked `slow`. They are skipped by default and run with `pytest -m slow`.
- **Human gate**: each sprint ends with the Verifier's report and the developer's approval. The next sprint does not start until then. Commits happen only when the developer authorizes them.

## 11. Delivery plan

Eight sprints, in order (plus 5.5, the UI redesign). Each one ends at a human gate.

1. **Foundations and contracts**: project setup, `Actuator` model, schema, Postgres in compose, test fixtures, data seed, and the signature stubs for every module.
2. **Data (ingestion and database)**: crops, normalization, validation, JSON store, OCR and flags, escalation, pipeline and `ensure_data()`, repositories and the ingestion CLI.
3. **Tools, LLM and agent**: `get_actuator`, `search_actuators`, `describe_catalog`, LLM selection, prompts, response builder with number guard, `run_agent`, `cli.py`, and the evaluation set and runner.
4. **API, persistence and Docker**: FastAPI routes and error format, conversation and session persistence, Dockerfile, the `api` service with the startup sequence, and recovery tests.
5. **Android app**: Gradle project, API client, product cards and comparison table, Conversations, Chat and Debug screens, and an end-to-end run on the emulator.
5.5. **UI redesign ("Axel")**: dark, light and system themes, splash, the Axel character and launcher icon, conversation search (`GET /api/sessions?q=`), transitions. Visual reference in `docs/design/`, contract in `mobile/android/DESIGN.md`.
6. **Security**: a multi-phase audit with Cloudflare's `security-audit` skill (prompt injection, agent and tool abuse, API exposure, operator spend, mobile, supply chain), adversarial evaluation cases, remediation and a re-audit. Two runs; no confirmed vulnerability, three leads that need a deployment fact. The committed report is `docs/security/REPORT.md` (raw runs in `docs/security/runs/` are gitignored). Decisions: D-39 (persona, generic tool errors) and D-40 (accepted number-guard risk while single-user).
7. **Integration and delivery**: final evaluation run with the good model, code review, README, decisions and tooling docs, clean-machine test, and a checklist of the brief.

8. **Evaluation fixes and optional features**: an independent evaluation of the Sprint 7 delivery scored it about 81/100 and listed concrete risks. Sprint 8 closes them (OCR in Docker with vision as fallback, number guard v2, history window, per-session lock, follow-up referent, docs mismatches, conversational small talk) and adds the optional login and voice conversation. Plan and status per wave: `docs/plans/SPRINT-8.md`. Decisions D-43 to D-49.

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
- Pending for the extractor: a real OpenRouter call for escalation (today it is simulated; ask the developer before spending, CLAUDE.md §9), and testing the flag rule on other PDFs.

### Data model

One row per (table, part number). Columns are typed and nullable. The field names are the flat schema of the benchmark (`bench/schema.py`), with the names below.

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
- `agent/response.py` builds `products[]` from the tool outputs (code, not LLM). Guard: every number in the text must appear in the tool results. If one does not, a deterministic template answer is used and noted in `trace`.
- Models are set by environment variable and by task: `AGENT_MODEL` (cheap while iterating, good for the final run) and `EXTRACT_LLM_MODEL` (OCR escalation, Sonnet 5.5). Development uses Google AI Studio through an OpenAI-compatible endpoint (`LLM_BASE_URL`). The OpenRouter key is used only with explicit permission. No LLM translation of titles and no embeddings (no pgvector).
- Language: the answer is in the user's language; numbers and part numbers are kept as they are.

## 4. API (FastAPI)

- `POST /api/conversation` returns `{session_id, answer, products[], debug}`. Each item in `products[]` is `{part_number, enclosure, voltage, phase, service, fields:{...values with units...}, csa_certified, notes[]}`. The app shows them as comparable cards (one column per product). `debug` is a list of `{tool, params, result}`. It is **always present in the response**; the user-facing app does not show it.
- `GET /api/sessions` (id, title, date) and `GET /api/sessions/{id}/messages` (includes `products` and `debug`).
- An unknown `session_id` returns **404** with a clear message. Sessions are never created by accident. With no `session_id`, a session is created and returned.
- Login hook: a `get_current_user()` dependency that returns `None` today. The `sessions_repo` queries already accept `user_id`. Enabling login means implementing `POST /api/auth/login` and changing that dependency. The `users` table is created only if login is implemented.
- Voice hook: **transcription on the device** (Android `SpeechRecognizer`). The text goes to the same endpoint. No budget cost and no backend change.
- Errors: a uniform JSON body `{error, detail}`. A timeout or a dead LLM returns 503, without losing the user's message, which is already saved.

## 5. Android app (`mobile/android`)

One Gradle module with packages by feature (KISS; the `android-development` skill and the `android-skills` plugin apply): `conversations/`, `chat/`, `debug/`, `data/` (Retrofit + kotlinx.serialization, one `ApiClient`), `ui/` (theme, `ProductCard`, `ComparisonTable`). MVVM: `ViewModel` + `StateFlow`; Navigation Compose; manual DI.

- Loading and error states on all 3 screens (backend down, timeout).
- Backend URL in `BuildConfig`, read from `local.properties` (emulator: `http://10.0.2.2:8000`).
- Debug: opened with a hidden gesture (5 taps on the chat title). It shows the `debug` of each response. Documented in the README.
- The chat never shows tool names or traces.

## 6. Backend modules (≤ ~150 lines each, tested on their own)

```
backend/
├── pyproject.toml
├── app/
│   ├── domain/models.py            # Actuator (single contract), Product, ToolTrace
│   ├── ingestion/{ocr,flags,escalate,normalize,validate,pipeline,store_json}.py
│   ├── db/{schema.sql,connection.py,actuators_repo.py,sessions_repo.py}
│   ├── bootstrap.py                # ensure_data()
│   ├── agent/{tools,llm,prompts,agent,response}.py
│   └── api/{main.py,schemas.py,deps.py,routes_conversation.py,routes_sessions.py}
├── cli.py   ingest.py
├── data/{raw/series_76_electric_data.pdf, processed/actuators.json}
├── bench/   eval/   tests/
mobile/android/
docs/{ARCHITECTURE.md, DECISIONS.md, TOOLING.md}
docker-compose.yml  Dockerfile  Makefile  .env.example  README.md
```

No ORM (`psycopg` with parameterized SQL). No `DataSource` or `Extractor` interfaces, and no `EXTRACTORS=...` setting: there is one extractor. One `pyproject.toml`, installed with `pip install -e .`.

## 7. Infrastructure

- `docker-compose.yml`: `db` (postgres:16, `pgdata` volume, `pg_isready` healthcheck) and `api` (`depends_on: service_healthy`; at start it runs `ensure_data()` and then uvicorn).
- `Dockerfile`: python slim. `rapidocr-onnxruntime` ships the ONNX models, so OCR works offline.
- `.env.example`: `DATABASE_URL`, `LLM_BASE_URL`, `LLM_API_KEY`, `AGENT_MODEL`, `EXTRACT_LLM_MODEL`. No secrets.
- `Makefile` (shortcuts only): `up`, `reset` (deletes the volume and reloads), `ingest-force`, `test`, `chat`, `eval`.
- Recovery documented in the README: database deleted → `make up`; JSON deleted → `make up` (re-extracts); everything broken → `make reset`.

## 8. Testing and evaluation

- Unit tests per module, without a real LLM: `validate`, `flags`, `normalize`, repositories (test Postgres), tools, `response` (number guard), and the API with a simulated agent.
- Self-recovery test (main acceptance criterion): (a) `docker compose down -v && make up` → 68 rows; (b) delete `actuators.json` → it is regenerated and validated; (c) delete rows in Postgres → the count is corrected; (d) corrupt JSON → detected and re-extracted; (e) restart the API → conversations still there.
- `eval/`: 20–30 questions (point lookup, recommendation, invalid part number, N/A, impossible requirement, ambiguity, data outside the subset, multi-turn follow-up). Deterministic assertions on the tool called and on the numbers in `products`. Cheap model while iterating; the good model only in the final run.
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

Six sprints, in order. Each one ends at a human gate.

1. **Foundations and contracts**: project setup, `Actuator` model, schema, Postgres in compose, test fixtures, data seed, and the signature stubs for every module.
2. **Data (ingestion and database)**: crops, normalization, validation, JSON store, OCR and flags, escalation, pipeline and `ensure_data()`, repositories and the ingestion CLI.
3. **Tools, LLM and agent**: `get_actuator`, `search_actuators`, `describe_catalog`, LLM selection, prompts, response builder with number guard, `run_agent`, `cli.py`, and the evaluation set and runner.
4. **API, persistence and Docker**: FastAPI routes and error format, conversation and session persistence, Dockerfile, the `api` service with the startup sequence, and recovery tests.
5. **Android app**: Gradle project, API client, product cards and comparison table, Conversations, Chat and Debug screens, and an end-to-end run on the emulator.
6. **Integration and delivery**: final evaluation run with the good model, code and security review, README, decisions and tooling docs, clean-machine test, and a checklist of the brief.

Optional work (login and voice) is done only if there is time left, after sprint 6.

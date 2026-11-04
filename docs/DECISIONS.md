# Decisions

Each entry records one decision, the alternatives considered, its trade-off, and its status. The architecture it refers to is in `docs/ARCHITECTURE.md`.

## D-01 Hybrid extractor: RapidOCR offline, with flagged tables escalated to vision

**Decision.** The default extractor is RapidOCR (E), run offline on 2× crops of each table. A cell is flagged when its confidence is below 0.9, when its raw text starts with a zero followed by a digit (`^0\d`), or when a validator fails. Any table with at least one flagged cell is sent in full to a vision model (Sonnet 5.5, via `EXTRACT_LLM_MODEL`). The other tables stay offline.

**Alternatives.**
- Pure vision per table (B, Sonnet on crops): 100% cell accuracy in two runs, and a third run was identical. It needs a key and about 80k subagent tokens per run. This was the benchmark's first recommendation. It is kept as the escalation path.
- RapidOCR alone (E): 99.45% (5 wrong cells). It is offline and deterministic, but digits are dropped (960→96, 90→6, 99→66). The validators catch only 1 of those 5.
- Full-page vision (A): 99.1% to 99.3%. It shifts rows in the dense tables (764A receives the values of 764B), and the validators do not detect it.
- Classic OCR (Tesseract, img2table): 40% to 55% cell accuracy. Rejected.

**Trade-off.** Most of the data loads with no network and no key, and the result is reproducible. The cost is a second code path (flags and escalation) to test and explain. The flag rule was designed while looking at the 5 errors in the same document, so it may overfit this PDF. On the benchmark, hybrid reaches 100%, with 14 of 869 cells flagged (1.6%), 5 of 5 errors caught, 9 false positives, and 4 of 7 tables escalated (48 of 68 rows).

**Status.** Accepted. The escalation is still simulated: it reuses the output of the vision run on the same PDF. A real OpenRouter call needs the developer's permission before it spends money. The flag rule still has to be tested on other PDFs.

## D-02 No `DataSource` or `Extractor` interfaces

**Decision.** There is one extractor and one loading path: the JSON cascade and the PDF extraction are plain functions in `ingestion/` and `bootstrap.py`. There is no abstract interface and no `EXTRACTORS=...` environment variable.

**Alternatives.** Abstract `DataSource.load()` and `Extractor.extract()` interfaces, with the extractor chosen by an environment variable, as first drafted in CLAUDE.md §5.

**Trade-off.** Less code and fewer concepts to explain, and nothing to configure. The cost is that adding a second extractor later means refactoring the caller. That is acceptable: no second extractor is planned.

**Status.** Accepted. CLAUDE.md §5 was updated to match.

## D-03 No ORM: `psycopg` with parameterized SQL

**Decision.** Repositories use `psycopg` with parameterized SQL. The LLM never writes SQL; the tools call fixed queries.

**Alternatives.** SQLAlchemy (ORM or Core), or SQLModel.

**Trade-off.** The schema and the queries are visible in one place, which is easier to review and to defend. The cost is writing SQL by hand and mapping rows to models ourselves. The data model is small (one main table and two for conversations), so this is simple.

**Status.** Accepted.

## D-04 Typed columns, not a JSON blob

**Decision.** Each field of an actuator is its own typed, nullable column (torque, voltage, phase, enclosure, service and so on). `products` and `trace` are the only `jsonb` columns, and they are for conversation history, not for product data.

**Alternatives.** One `jsonb` column with the whole spec per row.

**Trade-off.** Filters like "torque ≥ X Nm, 220V, single phase" are direct SQL with indexes, and the database rejects bad values through CHECK constraints. The cost is a wider table and a schema change whenever a new field appears.

**Status.** Accepted.

## D-05 Flat `Actuator` schema, reused from the benchmark, with the three-phase value kept as printed

**Decision.** The `Actuator` model uses the flat field names of the benchmark (`bench/schema.py`): one row per (table, part number), with the groups on/off, modulating, single output, speed, FLA and LRA. The three-phase table (T3) prints one torque and one duty cycle for the whole table. Those values go only into `output_torque_*` and `duty_cycle_pct`, exactly as printed. They are not copied into the on/off or modulating columns. Search resolves torque as `COALESCE(onoff_torque, mod_torque, output_torque)` when the service is unspecified, and as `COALESCE(family torque, output_torque)` when the service is given.

**Alternatives.**
- Copy the single torque and duty into the on/off and modulating columns, and mark it in the notes (the first proposal in the V1 plan). This makes filters simpler, but it duplicates a value that was not printed in those columns.
- Separate tables per family (one for on/off, one for modulating). This is more normalized but needs joins for every filter.

**Trade-off.** No value is duplicated or inferred, which matches "values as printed". The cost is that every torque filter needs a `COALESCE`, and that rule must be tested.

**Status.** Accepted. The `unparsed` field from the benchmark schema is also kept, to record cells that could not be parsed.

## D-06 Exact row count to decide whether data is present

**Decision.** `ensure_data()` treats the database as loaded only when `COUNT(*)` equals the row count of the valid JSON (68). A non-empty table is not enough. The upsert is `ON CONFLICT (part_number) DO UPDATE`, so repeating it is safe.

**Alternatives.** Check whether the table is non-empty, or load only when empty.

**Trade-off.** A partial load (for example, an interrupted run) is detected and repaired on the next start. The cost is a count query on every start, which is negligible for 68 rows.

**Status.** Accepted.

## D-07 Our own history in Postgres, not a LangGraph checkpointer

**Decision.** Conversation history lives in our `sessions` and `messages` tables. The agent receives it as a list: `run_agent(query, history=[])`. There is no checkpointer.

**Alternatives.** The LangGraph checkpointer, which stores graph state automatically.

**Trade-off.** The history is visible in our schema, which the API and the Debug screen need anyway, and it survives restarts without another dependency. The cost is that we write the history logic ourselves.

**Status.** Accepted. This is also the reason LangGraph is not used directly (see D-08).

## D-08 LangChain `create_agent`, not LangGraph or Deep Agents

**Decision.** The agent is built with LangChain's `create_agent()`, with a fixed set of three tools.

**Alternatives.** LangGraph (a custom graph), or Deep Agents (planning and subagents).

**Trade-off.** It is a single-purpose agent with a fixed set of tools and no need for planning or multiple agents, so the simpler API is enough. The cost is less control over the flow than a custom graph would give. This choice can be revisited if the agent needs more steps.

**Status.** Accepted.

## D-09 404 for an unknown `session_id`

**Decision.** A request with a `session_id` that does not exist returns 404 with a clear message. A request without `session_id` creates a session and returns its id.

**Alternatives.** Create a new session silently when the id is unknown.

**Trade-off.** No conversations are created by accident, and a typo in the id is reported. The cost is that the client must handle the 404.

**Status.** Accepted. Recorded here in response to the open question in CLAUDE.md §10.

## D-10 Voice: transcription on the device (hook only)

**Decision.** If voice is implemented, the Android app transcribes speech on the device (`SpeechRecognizer`) and sends the text to the same endpoint. The backend does not change.

**Alternatives.** Send audio to the backend and transcribe there (for example, with a cloud speech model).

**Trade-off.** No cost against the OpenRouter budget and no backend change. The cost is that transcription quality depends on the device and its language support.

**Status.** Accepted as a hook only. Voice is optional and not implemented.

## D-11 `user_id` nullable (hook for login)

**Decision.** `sessions.user_id` is nullable. A `get_current_user()` dependency returns `None` for now. Enabling login means adding `POST /api/auth/login`, a `users` table, and changing that dependency.

**Alternatives.** Implement login now, or add the `users` table now.

**Trade-off.** The schema and the routes do not change when login arrives, and login is not built before it is needed. The cost is that a dependency must be changed later and tested then.

**Status.** Accepted as a hook only. Login is optional and not implemented.

## D-12 uv and Python 3.12

**Decision.** The project uses `uv` with Python 3.12 (`.python-version`).

**Alternatives.** The system Python, or a plain `venv` with `pip`.

**Trade-off.** The system Python is 3.9, which is too old for LangChain v1. `uv` gives a reproducible environment with one command and a lock file. The cost is a dependency on `uv` for anyone reproducing the project, which the README covers.

**Status.** Accepted.

## D-13 Android app in Kotlin and Jetpack Compose

**Decision.** The mobile app is native Android, written in Kotlin with Jetpack Compose.

**Alternatives.** iOS with Swift and SwiftUI.

**Trade-off.** Android can be built and tested without a Mac, and the Android tooling and skills available to this project cover it. The cost is that iOS is not covered.

**Status.** Accepted. This closes the open question in CLAUDE.md §10.

## D-14 Tools tested against a seeded test database, not a fake repository

**Decision.** Tools take a `conn_factory`. Their tests run against the `series76_test` Postgres seeded with the 68 real rows.

**Alternatives.** A repository Protocol plus an in-memory fake.

**Trade-off.** No fake to keep in sync with the SQL, and tests exercise the real filters. The cost is that tool tests need Docker running. They skip with a clear message when it is not.

**Status.** Accepted (Sprint 1).

## D-15 Shared contracts live in `domain/`

**Decision.** `domain/search.py` holds `SearchFilters`, `ActuatorLookup`, `SearchResult`, `NoMatchReport` and `CatalogSummary`. `domain/conversation.py` holds `HistoryTurn`, `AgentResult`, `SessionInfo` and `StoredMessage`. `tests/test_contracts.py` freezes the public signatures.

**Alternatives.** Define the types inside each layer (repo, tools, API).

**Trade-off.** Dependencies point only downward: `db`, `agent` and `api` all import `domain`, never each other. Parallel subagents implement against frozen signatures. The cost is one extra small module per concern.

**Status.** Accepted (Sprint 1).

## D-16 Part number pattern and golden fixture inside the repo

**Decision.** The part number regex is `^76\d[A-Z]\d{2}-[0-9A-Z]{8}/A$`. The suffix must be alphanumeric because the 3-phase suffix is `11330C00`. The golden file is copied to `backend/tests/fixtures/golden_draft.json`, and no code or test points outside the repo.

**Alternatives.** A digits-only suffix. Reading the golden from the benchmark folder.

**Trade-off.** The regex is a little looser, but cross-checking the suffix against the section title still catches mismatches (Sprint 2 `normalize`). The in-repo fixture makes tests pass on a clean machine.

**Status.** Accepted (Sprint 1).

## D-17 Pair checks emit one issue per cell

**Decision.** `Issue.field` is always a single real field name. Pair checks (`torque_ratio`, `fla_le_lra`, `speed_60_le_50`) emit one issue for each cell of the pair.

**Alternatives.** One issue with a combined field such as `"onoff_torque_in_lbs/onoff_torque_nm"`.

**Trade-off.** The flag rule ("validator error in that field") looks up issues by field name. With the combined name it would miss them, and the known OCR error `90 -> 6 Nm` would not be flagged for escalation. The cost is two issue lines per broken pair. Found by the black-box test-writer (task 2.5), not by the builder's own tests.

**Status.** Accepted (Sprint 2).

## D-18 OCR text is never repaired; doubtful cells are flagged instead

**Decision.** `ocr.py` passes every raw cell to the strict `normalize.parse_number` unchanged. The benchmark's repairs (`O` -> `0`, guessing `.` as a thousands separator) are removed. A cell that does not parse keeps a `None` value and gets `parse_error`. `flags.py` then marks it `unparsable`, and its whole table is re-read by vision. A part number that fails the suffix check, for example `11330C0O`, is recorded as a flagged `part_number` cell and its row is skipped.

**Alternatives.** Keep the benchmark repairs. They gave 99.45% of cells right offline.

**Trade-off.** A repair is a guess, and a guessed value could reach Postgres looking correct. Without repairs, raw OCR accuracy drops to 96.15%. But no wrong value is loaded: the 28 rejected cells are empty and flagged, and 99.4% of the cells that received a value are correct. The escalated tables are the same as in the benchmark (T1, T2, T3 and T7), so there is no extra cost on this PDF.

**Status.** Accepted (Sprint 2).

## D-19 `get_llm()` lives at `app/llm.py`

**Decision.** The only factory for chat models is `app/llm.py`, with one task per model (`agent` -> `AGENT_MODEL`, `extract` -> `EXTRACT_LLM_MODEL`). Both `agent/` and `ingestion/escalate.py` import it.

**Alternatives.** `app/agent/llm.py`, as in the original architecture.

**Trade-off.** The vision escalation also needs an LLM, and `ingestion/` must not import `agent/`. A shared root module keeps the layer rules and keeps per-task model configuration in one place. The tree changes slightly.

**Status.** Accepted (Sprint 2).

## D-20 Dot-thousands OCR reads (`9.700`) are doubtful

**Decision.** In `ocr.py`, a raw cell matching `^\d{1,3}\.\d{3}$` is treated as unparsable and flagged. It is never read as 9.7.

**Alternatives.** Accept it as a decimal (the plain `parse_number` behaviour) or repair it to 9700.

**Trade-off.** The PDF prints thousands with commas and has no values with three decimals, so this shape is almost always the OCR misreading a comma. Accepting it silently corrupted 8 cells on the first run, for example T2 764B torque `9,700`/`1,100` read as `9.700`/`1.100`. The in-lbs/Nm ratio stayed plausible, so the validator missed them. Repairing it would be a guess (D-18). The rule is OCR-specific: `normalize.parse_number` itself stays generic.

**Status.** Accepted (Sprint 2). Found by the OCR builder's safety test `test_every_wrong_cell_is_flagged`.

## D-21 `has_data` is a generated column

**Decision.** `actuators.has_data` is `GENERATED ALWAYS AS (num_nonnulls(<21 measurement columns>) > 0) STORED`. The loader never writes it. On the pydantic side, `Actuator` accepts the computed `has_data` on input and ignores it, so `model_validate(x.model_dump())` round-trips.

**Alternatives.** A plain column written by the loader.

**Trade-off.** It can never drift from the data: a partial UPDATE recomputes it, and search hides `has_data = false` rows from numeric filters, so drift would hide real products. Existing local tables must be dropped once to migrate (data is rebuildable).

**Status.** Accepted (Gate 2, from code review).

## D-22 Torque and duty must be met by the same operating mode

**Decision.** With no `service` filter, a row matches only if one family (on/off, modulating or 3-phase output) satisfies every numeric family constraint at once: torque and duty cycle together. Tightest-fit ordering and the "closest value" in no-match diagnoses follow the same rule.

**Alternatives.** An independent OR per constraint (the first implementation).

**Trade-off.** With the independent OR, torque could come from on/off service and duty from modulating service on the same actuator. That would recommend a product no single mode can deliver. The SQL is a little longer (OR over families of AND over constraints).

**Status.** Accepted (Gate 2, from code review).

## D-23 Nothing the OCR missed can load as null

**Decision.** Every expected cell of every OCR row produces an `OcrCell`. A cell neither OCR pass read gets `parse_error="missing"` and is flagged. Tables with table-level validator errors (`row_count`, `unique_pn`), which map to no cell, are escalated too. Vision answers must contain every column of the table as text; non-text values and missing or extra keys raise `EscalationError`.

**Alternatives.** Omit unread cells (they became silent nulls). Escalate only flagged cells.

**Trade-off.** It closes the last gaps where a printed value could turn into a null, or a structurally broken table could fail instead of being re-read. More cells are flagged (78), but the escalated tables are still T1, T2, T3 and T7.

**Status.** Accepted (Gate 2, from code review).

## D-24 Self-healing never destroys the verified JSON

**Decision.** In `ensure_data`:
- A corrupt `actuators.json` is moved aside to `actuators.json.corrupt-<UTC timestamp>` only after a successful re-extraction. It is never overwritten.
- If the JSON is missing but Postgres holds the full, valid catalog, the JSON is rebuilt from Postgres, with no OCR and no LLM.
- `ingest.py --from-pdf` replaces the rows in one transaction (delete, then upsert), so dropped part numbers do not linger.

**Alternatives.** Overwrite with `force=True`. Always re-extract from the PDF.

**Trade-off.** It respects CLAUDE.md §9 (never overwrite silently) and avoids paid model calls on every start. The cost is more cascade branches, each covered by a test.

**Status.** Accepted (Gate 2, from code review).

## D-25 Ambiguous lookups return candidate details, not bare part numbers

**Decision.** `ActuatorLookup.candidates` is a list of `Candidate` (part number, enclosure, voltage, phase, service, has_data). Base `764A00` returns 3 candidates (110V 1ph, 220V 1ph, 220V 3ph).

**Alternatives.** A list of part number strings, as in the Sprint 1 contract.

**Trade-off.** With bare strings, the LLM would have to decode the voltage suffix (`11300000` = 110V) itself. That is knowledge from memory, which the project forbids. The details come from the section titles, so the model can ask "110V or 220V?" correctly. The tool output is slightly larger.

**Status.** Accepted (Sprint 3).

## D-26 Number guard: what counts as a verified number

**Decision.** `response.build_result` extracts every number in the answer (part numbers removed first) and accepts it only if one of its readings appears in:
- the trace: tool results and params, including numbers inside dict keys (`fla_50hz_a` gives 50);
- the user's query;
- `ALWAYS_ALLOWED`: 0 to 10 and 90.

`1,330` is read as both 1330 and 1.33; `2,3` is read as 2.3 (Spanish decimal). If any number fails, the answer is replaced by a deterministic template built from the trace, `guard_triggered` is set, and a `number_guard` entry with the original answer goes into the trace.

**Alternatives.** No guard (trust the prompt). Ask the LLM to self-check. Use a structured-output answer with numbers as references.

**Trade-off.** It is cheap, deterministic and testable, and it turns "the LLM never invents numbers" into a code guarantee. The guard is lenient by design: a correct number used in the wrong place, such as quoting an FLA as the torque, passes, and small integers always pass. Black-box tests showed why keys must count: without them, a correct "FLA at 50 Hz" answer was rejected. The first real eval run (24/26) showed that the family name "Series 76" also has to be stripped like part numbers; after that fix it scored 26/26.

**Status.** Accepted (Sprint 3).

## D-27 Follow-up context goes in the user message, and units are never converted

**Decision.** `build_messages` produces exactly one SystemMessage, first. The part numbers from the previous turn are prefixed to the final HumanMessage as `[Context: ...]`. The prompt forbids unit conversion: a requirement in ft-lbs, kW or similar is answered by asking for Nm or in-lbs.

**Alternatives.** A second SystemMessage mid-conversation. Letting the LLM convert units.

**Trade-off.** Some OpenAI-compatible providers (Gemini included) reject or merge system messages that are not first. Converting units is computing, which CLAUDE.md §9 forbids. The cost is one extra question to the user.

**Status.** Accepted (Sprint 3).

## D-28 Tool errors go back to the model; LLM errors become AgentError

**Decision.** The `TraceRecorder` middleware records every tool call: name, args, the parsed dict result and duration. A tool exception becomes an error ToolMessage and a `{"error": ...}` trace entry, so the model can recover. Exceptions from the LLM call become `AgentError`, which the API will map to 503. Hitting the recursion limit (12) returns a fixed "could not complete" answer through the guard.

**Alternatives.** Let every exception propagate. Use LangChain's built-in tool error handling.

**Trade-off.** The trace for the Debug screen and the error policy live in one small middleware, which is tested with a fake chat model.

**Status.** Accepted (Sprint 3).

## D-29 How the agent evaluation is run, and what it costs

**Decision.** During development the agent evaluation (`uv run python -m eval.run`, 26 cases in `eval/cases.yaml`) runs against OpenRouter with `AGENT_MODEL=stealth/crouton-alpha` and `LLM_BASE_URL` empty, so it defaults to `https://openrouter.ai/api/v1`. That model is a free "stealth" model.

How the run works:
- A single case runs first as a smoke test (`--only lookup-01`), then the full set (`--workers 3`).
- Each case calls the real `run_agent` against the dev Postgres, which `ensure_data()` loads with the 68 rows and with escalation off.
- The checks are deterministic: tools called, tool `status`, part numbers in `products`, exact numbers in the answer, `out_of_catalog`, and the number guard not triggered.
- The report is written to `eval/report.md`.
- The unit tests never call a real LLM; they use fake chat models.

**Cost check (2026-11-04).** The OpenRouter models endpoint lists `stealth/crouton-alpha` at prompt `0` / completion `0` USD per token. After two full runs (26 cases each), `GET /api/v1/key` showed `usage: 0` and `limit_remaining: 10` of the USD 10 budget. The developer approved using the key for this model (CLAUDE.md §9).

**Results.** The first run scored 24/26. Both failures were false positives of the number guard caused by "Series 76" (see D-26). After the fix, the second run scored 26/26.

**Alternatives.** Google AI Studio's free tier, the original plan for Gate 3: free, but with tighter rate limits and a different key. A paid model on OpenRouter would spend the budget, which is reserved for the final run.

**Trade-off.** It is free and uses the same endpoint and code path as production. Stealth models are temporary: one can disappear or start charging. Before each run, check the pricing and the key usage, and switch `AGENT_MODEL` if the model changes. The final run with the chosen model (Sprint 6) must be reported separately, with its cost.

**Status.** Accepted (Sprint 3, Gate 3).

## D-30 Tool output uses the printed spelling of numbers; multilingual scope

**Decision.**
1. Tools pass their dumped results through `tools.as_printed`, which turns whole-number floats into ints (750.0 -> 750). Postgres `numeric` reads back as float, and the LLM copied the ".0" into answers ("750.0 Nm") although the PDF prints "750". The prompt names the speed unit as printed in the tables, "seconds per 90°".
2. Language: understanding the question and writing the answer depend on the LLM. The prompt says "answer in the user's language". Tools are language-neutral: they take structured filters and return numbers. The only code with language support is the guard's fallback template, which covers Spanish and English (`detect_lang`); any other language gets the English template.

**Alternatives.** (1) Format numbers in the prompt, or let the LLM tidy them; changing the DB column types. (2) Templates for more languages, or LLM-written fallbacks.

**Trade-off.** (1) The value is identical; only its spelling changes, so it is not a conversion. The guard already accepts both spellings. (2) Konecto evaluates in English and the target users speak Spanish. More templates add code for a path that is rare (the guard fires only on unverified numbers), and an LLM-written fallback would defeat its purpose.

**Status.** Accepted (Sprint 3, from reading the eval transcripts; eval still 26/26).

## D-31 Gate 3 code-review fixes

**Decision.** Code review found ten issues. The fixes:
- **Invented part numbers.** The guard now also checks part numbers. Each part number in the answer must equal, or be a prefix of, a part number found in the trace or the query (`unverified_part_numbers`). Before, a made-up "769A00-11300000/A" passed, because part-number tokens were only stripped before the number check.
- **Mention filter.** A full part number (with or without "/A") now takes priority over its 6-char base. Naming "761A00-11300000/A" no longer pulls in its 220V siblings.
- **Duplicate products.** When the same part number appears twice, the entry with more notes wins. That is the get_actuator entry, which carries the table notes, such as the hazardous-area class. The first entry's position is kept.
- **Parallel tool calls.** `TraceRecorder` stores (tool_call id, trace) pairs in one list. Two parallel lists could misalign under concurrent tool threads.
- **Error mapping.** `run_agent` maps only provider failures (`openai.APIError`, `httpx.HTTPError`, `TimeoutError`, `ConnectionError`) to `AgentError`. Our own bugs propagate, so the API answers 500 for them instead of a misleading 503.
- **Recursion limit.** Raised from 12 to 25, about 12 sequential tool calls, so a follow-up that re-checks 5 products still fits.
- **Dashless partial part numbers.** `normalize_part_number` inserts the dash in partials such as "761A001130", so the prefix search finds them.
- **Shared constants.** `CSA_NOTE` lives only in tools. Suggestions read all rows with `limit=count` instead of a hardcoded 1000.
- **Module size.** `eval/run.py` was split: `eval/cases.py` holds the case models and checks, and `run.py` holds the runner, report and CLI.

**Not changed (accepted risk).** Numbers in the user's query and in tool params still count as verified. Without that, an answer that repeats the user's own requirement ("your 200 Nm") would be rejected. A new prompt rule covers the remaining risk: verify any figure the user states with a tool, correct it with the tool's value, and mention only part numbers returned by a tool. The guard stays lenient by design (D-26).

**Trade-off.** Each fix has a regression test. `response.py` (about 190 lines of code plus a 55-line spec docstring) and `tools.py` (about 170 plus 50) are above the ~150 target. They hold one responsibility each, so splitting them further would only scatter the contract.

**Status.** Accepted (Gate 3). 1066 tests green; real eval 26/26 after the fixes.

## D-32 API: autocommit pool, short DB borrows, injected agent, no paid calls at startup

**Decision.**
- **Pool.** One `psycopg_pool.ConnectionPool` per app (max 10) with `autocommit=True`. The user's message is committed before the agent runs, so a 503 never loses it. `add_message` still wraps its insert and the session bump in `conn.transaction()`.
- **Connection borrowing.** `POST /api/conversation` borrows a connection only around the DB steps (load or create the session, history, save the user message; then save the answer). It holds none while the LLM runs, because the agent's tools draw from the same pool. A test with a pool of one connection proves this.
- **Sync endpoints.** Endpoints are sync `def`; FastAPI runs them in its threadpool, because `run_agent` is synchronous.
- **Injected agent.** The agent is a dependency (`get_agent`), so tests override it with a fake and never call an LLM.
- **Startup.** The lifespan runs `apply_schema` + `ensure_data()`. Vision escalation is OFF unless `STARTUP_ESCALATION=on`: the API never spends money on its own (CLAUDE.md §9).
- **Corrupt JSON.** A corrupt `actuators.json` is now rebuilt from a full, valid Postgres, like the missing case in D-24. The bad file is moved aside first and restored if the write fails.
- **Errors.** Every error body is `{error, detail}`:

  | Cause | Status | `error` |
  |---|---|---|
  | Unknown session | 404 | `session_not_found` |
  | Invalid request | 422 | `validation_error` |
  | `AgentError` | 503 | `llm_unavailable` |
  | Missing LLM config | 503 | `llm_not_configured` |
  | DB down | 503 | `database_unavailable` |
  | Anything else | 500 | `internal_error` |

  The 500 response is generic; the traceback is only logged.

**Alternatives.**
- Async endpoints with an async pool.
- One connection held per request.
- A transaction around the whole turn, which would lose the user message on a 503.
- Escalation on at startup.

**Trade-off.** Two short borrows per turn instead of one long one. Concurrent requests on the same session could interleave their history, which is acceptable for a single-user mobile app. A clean clone with no LLM key still starts: health, sessions and data all work, and only conversation turns return 503 `llm_not_configured`.

**Status.** Accepted (Sprint 4).

## D-33 One OpenCV build (headless) and a 1.4 GB image

**Decision.** `pyproject.toml` has a uv `override-dependencies` entry that drops `opencv-python`, the GUI build pulled in by `rapidocr-onnxruntime`. Only `opencv-python-headless` (same version and same `cv2` API) is installed. The Docker image (`python:3.12-slim` + uv 0.8.22, non-root, `uv sync --frozen --no-dev`) needs no apt packages.

**Alternatives.** Keep both and install `libgl1`, `libxcb1` and `libglib2.0-0` in the image (1.98 GB). Drop our own headless dependency.

**Trade-off.** Both wheels write the same `cv2` folder, so whichever is installed last wins. Removing one broke `import cv2` locally until the headless wheel was reinstalled, which shows how fragile that was. The GUI build also needs X11/GL libraries a server does not use. With one build the image went from 1.98 GB to 1.4 GB, under the 1.5 GB target. The full suite including the slow tests (real OCR on the PDF against the golden file, cell by cell) passes 1136/1136 after the change. The override is a uv-specific mechanism, documented in a comment next to it.

**Status.** Accepted (Sprint 4).

## D-34 Gate 4 security review: localhost binding, generic 503, accepted risks

**Decision.** A manual review of the Sprint 4 API led to these fixes and these accepted risks.

Fixes:
- **Port binding.** compose publishes the API and Postgres on `127.0.0.1` only (`API_BIND` and `DB_BIND`, both default `127.0.0.1`). Before, both listened on every interface, so anyone on the same network could read every conversation and reach Postgres with the default password. The Android emulator still works through `10.0.2.2`, which maps to the host's loopback. A physical phone needs `API_BIND=0.0.0.0`.
- **Generic 503.** `llm_unavailable` now returns a generic detail. The provider's error text, which can contain upstream details, is only logged.

Already in place:
- parameterized SQL only, and the LLM never writes SQL;
- read-only tools;
- a generic 500;
- a non-root container, with `.env` excluded from the image;
- input bounded to 2000 characters;
- the agent's step limit.

**Accepted risks.**
- **No authentication.** `GET /api/sessions` lists every conversation. This is single-user by design; the login hook is D-10.
- **No rate limiting.**
- **Prompt injection can only steer the wording.** The guard blocks unverified numbers and part numbers, and the tools cannot write.
- **The `debug` trace is always in the response.** It holds catalog data and the guard's original answer, which is by design for the Debug screen.

**Alternatives.** API key or token auth now. A reverse proxy with rate limits.

**Trade-off.** Binding to localhost removes the real exposure at no cost to the emulator workflow. Auth and rate limits add work the assessment does not require, and they are listed as optional.

**Status.** Accepted (Gate 4). `/security-review` could not run because the repo has no remote (`origin/HEAD`), so the review was done by hand on the Sprint 4 diff.

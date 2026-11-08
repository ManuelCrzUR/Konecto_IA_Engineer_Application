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

**Status.** Accepted. The escalation was verified with a real vision run on this PDF (D-49).

**Known limitation (decided, not pending).** The flag rule was tuned on this PDF only, because the brief asks for this PDF. On another catalog, doubtful cells would still escalate to vision and validation would abort on mismatches, but the rule was not tested on other PDFs.

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

**Status.** Accepted as a hook only in Sprint 1. Superseded: voice is implemented in Sprint 8, see D-48.

## D-11 `user_id` nullable (hook for login)

**Decision.** `sessions.user_id` is nullable. A `get_current_user()` dependency returns `None` for now. Enabling login means adding `POST /api/auth/login`, a `users` table, and changing that dependency.

**Alternatives.** Implement login now, or add the `users` table now.

**Trade-off.** The schema and the routes do not change when login arrives, and login is not built before it is needed. The cost is that a dependency must be changed later and tested then.

**Status.** Accepted as a hook only in Sprint 1. Superseded: login is implemented in Sprint 8, see D-43.

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

Sprint 8: the benchmark copies were removed as dead code; the cells fixture moved to backend/tests/fixtures/cells.json.

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

Numbers and part numbers typed by the user in earlier turns of the session also count as verified (found by the developer: 'what did I say last?' quoting '24V' was rejected); earlier assistant figures still do not.

`1,330` is read as both 1330 and 1.33; `2,3` is read as 2.3 (Spanish decimal). If any number fails, the answer is replaced by a deterministic template built from the trace, `guard_triggered` is set, and a `number_guard` entry with the original answer goes into the trace.

**Alternatives.** No guard (trust the prompt). Ask the LLM to self-check. Use a structured-output answer with numbers as references.

**Trade-off.** It is cheap, deterministic and testable, and it turns "the LLM never invents numbers" into a code guarantee. The guard is lenient by design: a correct number used in the wrong place, such as quoting an FLA as the torque, passes, and small integers always pass (superseded by D-44, which removed the always-allowed integers). Black-box tests showed why keys must count: without them, a correct "FLA at 50 Hz" answer was rejected. The first real eval run (24/26) showed that the family name "Series 76" also has to be stripped like part numbers; after that fix it scored 26/26.

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

**Trade-off.** It is free and uses the same endpoint and code path as production. Stealth models are temporary: one can disappear or start charging. Before each run, check the pricing and the key usage, and switch `AGENT_MODEL` if the model changes. The final run with the chosen model (Sprint 7) must be reported separately, with its cost.

**Status.** Accepted (Sprint 3, Gate 3).

## D-30 Tool output uses the printed spelling of numbers; multilingual scope

**Decision.**
1. Tools pass their dumped results through `tools.as_printed`, which turns whole-number floats into ints (750.0 -> 750). The same rule applies to `Product.fields` when it is serialized to JSON (a `field_serializer` with `when_used="json"`), so the API response and stored messages show `750` too. Python-mode dumps and `Actuator`, and therefore `actuators.json`, keep floats. Postgres `numeric` reads back as float, and the LLM copied the ".0" into answers ("750.0 Nm") although the PDF prints "750". The prompt names the speed unit as printed in the tables, "seconds per 90°".
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
- **Retry continuity.** Responses from `POST /api/conversation` carry `X-Session-Id`, including 503s after the session exists, so a client retry continues the same session instead of creating a duplicate. A retried question is stored again: accepted, it is the user's real retry. Error bodies stay `{error, detail}`.
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

## D-35 The Android app reaches the backend through `adb reverse`, not `10.0.2.2`

**Decision.** The app's default base URL is `http://localhost:<API_PORT>/`. `make android-reverse` (`adb reverse tcp:<port> tcp:<port>`) maps the device's localhost to the Mac's. The URL is configurable in `mobile/android/local.properties` (`api.baseUrl`).

**Alternatives.** `http://10.0.2.2:<port>` (the emulator's alias for the host loopback). `API_BIND=0.0.0.0` with the Mac's LAN IP.

**Trade-off.** The first real run on the emulator showed what goes wrong with `10.0.2.2` on this Mac:
- The emulator reached a plain server on the Mac's 127.0.0.1.
- It never reached the API, because Colima publishes container ports through its own ssh forwarder. Requests never arrived: the API log was empty and the app timed out.

`adb reverse` goes through the adb server on the Mac, so it behaves like a local `curl`. It works with Docker Desktop, Colima and USB phones, and keeps the API bound to localhost (D-34). The cost is one command per emulator boot, documented in the README and wrapped in `make android-reverse`. A phone over Wi-Fi still needs `API_BIND=0.0.0.0` and the Mac's LAN IP.

**Status.** Accepted (Sprint 5).

## D-36 Gate 5: Android client hardening from code review and E2E

**Decision.** `code-review` and the emulator E2E found these problems in the app. Each fix has a regression test.

- **Unexpected responses no longer crash the app.** A non-JSON or schema-mismatched body is now a `bad_response` failure. Before, a `SerializationException` escaped the ViewModel scope.
- **Retry continues the same session.** The backend adds `X-Session-Id` to every `/api/conversation` response, including 503s (D-32). The app adopts that id on a failed send, so Retry no longer creates a duplicate session.
- **Retry is offered only for transient failures.** Those are network errors, timeouts and 5xx. A 4xx shows its message and returns the text to the draft. The input is capped at the backend's 2000 characters.
- **A failed send keeps the typed text.** The contract already required this, and the first version cleared the field.
- **Chat state is protected.**
  - Sending is blocked while the history loads, so a late load cannot overwrite new bubbles.
  - The session id is kept in `SavedStateHandle`, so it survives process death.
- **The Conversations list refreshes on every resume**, unless a load is already running, and the pull-to-refresh indicator always resets. Before, a new chat was missing from the list after going back.
- **Smaller fixes.**
  - Debug refresh cancels the previous request.
  - The comparison table's divider renders.
  - The field ordering lives in one helper (`orderedKeys`), with `remember`.
  - HTTP logging is at BASIC level and only in debug builds.

**Alternatives.** An idempotency key per message, which needs a schema change. Disabling Retry entirely.

**Trade-off.** Retrying a question stores it again in the history. That is the user's real retry, and the agent still answers once per attempt. The remaining lint warnings (no app icon, no data-extraction rules) are cosmetic or not applicable: `allowBackup=false` and the app stores nothing locally. The icon was a polish item of the old delivery plan's Sprint 6 (now Sprint 7), and it was done early, in Sprint 5.5.

**Status.** Accepted (Gate 5). 63 unit tests and 15 instrumented tests green on API 37; backend 1298 tests green.

## D-37 Conversation search with ILIKE and a code-built snippet

**Decision.** `GET /api/sessions?q=&limit=` searches the title and the message contents of the user's sessions. Without `q`, or with a blank `q`, it is the plain listing and every item has `match: null`.

- **Matching.** Case-insensitive substring (`ILIKE`) over `sessions.title` and `messages.content`. One query: a `LEFT JOIN LATERAL` picks the first matching message of each session (oldest first), so there is no N+1. Scoping by `user_id` and the order (`updated_at DESC, id`) are the same as the plain listing.
- **Escaping.** The user text is bound as a parameter, never interpolated. In Python, `\`, `%` and `_` are prefixed with a backslash, and the SQL says `ESCAPE '\'`. So `100%` finds "100%" and not "1000", and `_` is not a wildcard.
- **Result.** Each item is a `SessionOut` plus `match = {where, snippet}`. `where` is "title" if the title matches, else "message". The snippet is the title, or about 80 characters around the first match, built by a pure function (`db/snippet.py`). Its cut edges move outward to whitespace, so a number or part number is never split, and "…" marks a cut edge.

**Alternatives.** `pg_trgm` with a GIN index, or full-text search (`tsvector`). Full-text search stems words and ignores punctuation, which is wrong for part numbers like `764A00-11300000/A` and for numbers. Trigram needs an extension and an index.

**Trade-off.** `ILIKE '%x%'` cannot use a B-tree index, so it is a sequential scan of `messages`. For a single-user history of hundreds or a few thousand messages this takes milliseconds. If the history grows, add `pg_trgm` and a GIN index on `messages.content` without changing the API.

**Status.** Accepted (Sprint 5.5).

## D-38 Number guard: product names are not figures (Gate 5.5)

**Context.** Two false positives showed up in real use on the device, and both replaced a correct answer with the template "I could not verify an answer from the data":
- A Spanish greeting said "actuadores eléctricos **Serie 76**". The guard only stripped the English "Series 76", so it flagged `76`.
- A comparison said "the **764** is the larger frame". The model size (the first three digits of a part number) was flagged as an unverified number.

**Decision.**
- The family-name pattern accepts `Series`, `Serie` and `Série` 76, in any case.
- In `allowed_numbers`, the three-digit model size of every part number that appears in the tool trace counts as verified. A size that no tool returned (for example "the 765" when only 763 was looked up) is still flagged.

**Alternatives.** Whitelisting 761–767 always. That would let the model mention a model size it never looked up, which breaks the rule that the answer only uses figures from the tools.

**Trade-off.** If a real figure equals a model size that the tools also returned (a hypothetical 764 W motor next to a 764A00 part number), the guard would accept it. No catalog value is in the 761–767 range, and the value would still be exact. The 26 eval cases still pass (26/26) after the change.

## D-39 Axel persona, small-talk rule and generic tool errors

**Context.** Two Sprint 6 observations. (1) In eval case injection-03 the model introduced itself as "Crouton Alpha": the prompt gave it a name but did not forbid naming the underlying model, so the provider leaked to users. Greetings and "what can you do?" had no defined behavior either, which made answers drift between tool calls and long lectures. (2) The security audit (run 1, hardening notes) found that `TraceRecorder` stored `str(exc)` of any tool exception in the trace, which is persisted and returned in `debug`; a database error could expose a host name or SQL text.

**Decision.**
- `SYSTEM_PROMPT` has an "Identity and small talk" section: the assistant is Axel; asked about its model, company or provider it says it is Axel, the Series 76 actuator assistant, and never names the model. Greetings, thanks and questions about itself get one or two short sentences in the user's language plus two or three example abilities, with no figures. Off-topic requests are declined briefly and redirected. The section has no digits, so the prompt digit test still holds.
- Tool exceptions: `ValueError` (which includes pydantic `ValidationError`) and `ToolException` keep their message, so the model can fix its call. Anything else (psycopg, OSError, bugs) becomes `{"error": "internal_tool_error", "detail": "The catalog lookup failed. Try again."}` in both the ToolMessage and the stored trace; the real exception goes to logging with the traceback on the server only.
- Code-side persona check: `apply_persona(answer, model_id)` in `agent/response.py` (pure) derives the model's display name from its id (last path segment, split on `-`, `_`, space or dot; tokens with digits and generic words such as `free`, `preview`, `instruct` are dropped) and replaces every case-insensitive, word-bounded match ("Crouton Alpha", "crouton-alpha", "CroutonAlpha") with "Axel". It needs a multi-token name or one token of 4+ letters, so `openai/gpt-4o` rewrites nothing. `run_agent` passes the id from the LLM object; `build_result` applies it after the number guard and, when something was replaced, appends a `persona_guard` trace entry (`params.replaced`) that the Debug screen shows. It works for any `AGENT_MODEL`, with no hardcoded names.
- Eval: new check `answer_includes`; cases injection-11 (identity) and injection-12 (Spanish greeting).

**Alternatives.** Filtering the model name out of answers in code (fragile, and the guard is for numbers). Not stating the persona at all (leaks the provider). Redacting host strings with a regex from the error text (an allowlist of safe errors is safer than a blocklist of secrets).

**Why the code check.** With the free `stealth/crouton-alpha` model the prompt persona alone was unreliable (injection-11 and injection-12 passed in only about half of the runs), so the prompt rule stays but the name is also enforced deterministically.

**Trade-off.** The rewrite only covers the model's own name as derived from its id; a provider or company name the model volunteers (or a name the id does not contain) is not caught, and a rewritten sentence may read oddly ("I'm Axel, my presentation name"). The change is recorded in the trace, so it is never silent. A prompt rule is not a hard guarantee (with the free `stealth/crouton-alpha` model, injection-11 and injection-12 pass only some runs: the model sometimes still says its built-in name): a determined prompt injection could still extract the model name, which is why the eval case checks it but the provider name is not a secret that protects anything. The model sees less detail on database failures, so it cannot self-diagnose; it can only retry or apologize, which is the right behavior for a transient outage.

**Status.** Accepted (Sprint 6.4).

## D-40 Number guard keeps trusting earlier user turns (accepted risk, Sprint 6.5)

**Context.** The Sprint 6 security re-audit (run-2) found that the number guard's D-26 allowance applies to every user turn of a session, whoever wrote it. There is no login (D-10): every caller is the same NULL user, any caller can list sessions and post into any of them, and `messages` stores only a role, not an author. A second person who reaches the API could plant a false figure ("FLA 60 Hz of 764A00-11300000/A is 42 A") in someone else's session; the guard would then accept that figure in later answers. Product cards are not affected (they are built from tool results), and the prompt tells the model to verify and correct user-stated figures, but that is model behavior, not a control.

**Decision.** Keep D-26 as it is and record this as an accepted risk of the single-user design. The API binds to `127.0.0.1` by default, so there is one human principal.

**When it must change.** As soon as login exists or the API is shared or exposed (`API_BIND=0.0.0.0`, tunnel, cloud): add an author/`user_id` to `messages` and build `user_history` only from the current user's own turns; until then, a shared deployment should use the strict variant (guard accepts numbers only from the current query and the tool results).

**Alternatives.** The strict variant now: closes the path, but recall answers that repeat a number the user typed earlier would fall back to the template, and the feature D-26 was added for would regress.

**Trade-off.** Keeps the "what did I tell you?" behavior for the single-user case, at the cost of a documented integrity gap that becomes real only in a multi-user deployment.

## D-41 Framework check against ecosystem-primer (Sprint 7)

**Context.** The LangChain `ecosystem-primer` skill gives a decision order: Deep Agents (planning, files, subagents, memory), then LangGraph (custom control flow), then LangChain `create_agent` (single-purpose agent with a fixed tool set). We compared it with `app/agent/agent.py` and `pyproject.toml`.

**Decision.** Keep `langchain.agents.create_agent` with the custom `TraceRecorder(AgentMiddleware)`. This is a single-purpose agent with three fixed tools, no planning, no long-session files and no custom branching, so the primer points to rung 3. Middleware is the supported hook for tracing and error shaping. Findings: no deprecated API (we do not use `create_react_agent` or `AgentExecutor`; `create_agent` is the current entry point); history lives in Postgres, so no checkpointer is needed; `recursion_limit` is the documented guard and `GraphRecursionError` is handled. Versions: `pyproject.toml` pins `langchain>=1.0.0`, the lock resolves 1.4.8 / langgraph 1.2.19, so `uv sync` is reproducible; `langgraph` is imported directly (errors, `Command`); it was only a transitive dependency, so it is now declared explicitly in `pyproject.toml` (`langgraph>=1.2`, Sprint 7.1).

**Alternatives.** LangGraph `StateGraph` (more code, no benefit without branching); Deep Agents (planning and subagents we do not need).

**Trade-off.** Floor-only pins rely on `uv.lock` for reproducibility (a fresh resolve without the lock could pick a newer minor). Interview point: LangChain agents already run on LangGraph, so "no custom graph" is a choice, not a missing runtime.

**Status.** Accepted (Sprint 7.5).

## D-42 Final agent model: openai/gpt-6-luna (Sprint 7)

**Context.** We ran the 38-case eval (`backend/eval`) against 6 tool-capable models on OpenRouter:

| Model | Passed | Time | Cost (USD) |
|---|---|---|---|
| openai/gpt-6-luna | 38/38 | 71 s | 0.011 |
| deepseek-v4.1-flash | 36/38 | 48 s | 0.017 |
| claude-haiku-5.5 | 34/38 | 75 s | 0.024 |
| gemini-2.5-flash-lite | 34/38 | 33 s | 0.002 |
| glm-5.3-flash | 30/38 | 246 s | 0.029 |
| qwen3.8-flash | 27/38 | 413 s | 0.037 |

The development model `stealth/crouton-alpha` (free) also scored 38/38 but is temporary.

**Decision.** `AGENT_MODEL=openai/gpt-6-luna` is the documented default in `.env.example`. The official `backend/eval/report.md` was produced with it: 38/38 (100%), every category 100% (lookup 4/4, recommend 5/5, invalid_pn 3/3, na 2/2, impossible 3/3, ambiguous 3/3, out_of_subset 3/3, multi_turn 3/3, injection 12/12), 71 s wall time with 2 workers, real cost USD 0.0055 (key usage 0.122308 -> 0.127760). `EXTRACT_LLM_MODEL` stays as documented: vision escalation is not exercised by the eval.

**Alternatives.** `stealth/crouton-alpha` (free, same score, but temporary and may vanish); `gemini-2.5-flash-lite` (cheapest and fastest, but 34/38); `deepseek-v4.1-flash` (36/38, faster, costlier per run).

**Trade-off.** The best score at a negligible cost against the USD 10 budget, at the price of depending on a paid model and a single benchmark run (LLM output is not fully deterministic, so a rerun may differ by a case). Models are swappable through the environment variable.

**Status.** Accepted (Sprint 7.1). Sprint 8 rerun on the 49-case set with the final code: 48/49 (98%), USD 0.008 (`docs/spend-log.md`).

## D-43 Login: opaque bearer tokens in Postgres, role-based trace (Sprint 8)

**Context.** Login is optional in the brief. If implemented: email and password, hashed passwords, a token sent as `Authorization: Bearer`, and each user sees only their own conversations. The independent evaluation also flagged that the Debug screen was protected only by a hidden gesture.

**Decision.** `users` (argon2id hashes via `pwdlib`, role `user` or `developer`) and `auth_tokens` (only the SHA-256 of a random 256-bit token, 7-day expiry). `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`. Every other `/api` route requires a valid token (401 otherwise); `/health` stays public. Another user's session answers 404, as an unknown id does (no existence leak). For role `user` the backend returns `debug`/`trace` empty; only `developer` receives the tool trace. Three test users are seeded at startup (`SEED_TEST_USERS=off` disables it). The single OpenRouter key stays on the server and is shared by all users.

**Alternatives.** JWT (stateless, but needs a signing secret and cannot be revoked without a deny list); sessions in memory (lost on restart); optional token with a single-user fallback (two modes to test and explain).

**Trade-off.** One indexed lookup per request, in exchange for instant logout and no secret to manage. Sessions created before login (`user_id` NULL) become invisible to everyone.

**Status.** Accepted (Sprint 8, wave 2). Supersedes the hook in D-11. Verified on the Docker stack: 401 with `WWW-Authenticate: Bearer` without a token, the same 401 body for a wrong password and an unknown email, logout revokes the token, passwords stored as `$argon2id$`. Wave 5 (code review): after process death Android restores the screen without the splash, so the interceptor reads the stored token from DataStore on first use (`SessionStore.token()`) instead of sending requests without one; sign-out clears the local session first and then revokes the token with an explicit header, so it never waits on the network; expired tokens are deleted when a new one is issued; seeding hashes only missing users (argon2 is slow on purpose).

**Android client (Sprint 8, wave 4).** The app stores the token in the `auth` DataStore (`data/SessionStore.kt`) and sends it as `Authorization: Bearer` through an OkHttp interceptor (`data/AuthInterceptor.kt`). Any 401 outside the login call clears the session and returns to Login.

## D-44 Number guard v2: no always-allowed integers, numbers bound to their product (Sprint 8)

**Context.** The evaluation showed that D-26's guard accepted any integer from 0 to 10 and 90 (so an invented "FLA 9 A" passed), accepted a real number attributed to the wrong product, and ignored numbers written as words ("seven seconds").

**Decision.** Remove `ALWAYS_ALLOWED`. Allow only list ordinals ("1." at the start of a line) and "90°" as the stroke. A number near a part number in the answer must come from that product's tool result. Number words (English and Spanish, 0 to 20) are checked like digits. Small talk with no tool call must contain no figures. Implemented with two refinements: "one", "once", "un", "una" and "uno" are not number words (they are mostly articles or adverbs), and a count of what a tool returned ("I found 2 options" when the search returned 2) is verified, since it comes from the data.

**Alternatives.** Ask the model for structured references (`{part_number, field}`) and render numbers in code (stronger, but a bigger change to the agent output).

**Trade-off.** Fewer silent errors, at the cost of more template answers if the model writes harmless numbers; the eval measures this.

**Status.** Accepted (Sprint 8, wave 1). Wave 5 (code review): counts of what the tools returned ("3 options", "of the two") are valid in any sentence, also right after a part number; before, the per-product binding rejected them and a correct answer fell back to the template.

## D-45 History window (Sprint 8)

**Decision.** The agent receives only the last `HISTORY_TURNS` messages (env, default 10). The product context line (D-26) still scans the whole stored history, so "and its power?" keeps working after the window moves. Everything stays stored in Postgres.

**Alternatives.** An LLM summary of older turns (costs tokens and adds an unverified text); no limit (cost and latency grow without bound).

**Trade-off.** Constant cost per turn; the model forgets details older than the window, but products are re-queried through tools anyway.

**Status.** Accepted (Sprint 8, wave 1).

## D-46 One turn at a time per session (Sprint 8)

**Decision.** `sessions.busy_since` is set with one conditional `UPDATE` before the agent runs and cleared in `finally`. A second concurrent turn on the same session gets 409 `turn_in_progress`. A lock older than 2 minutes is stale and can be taken. Writing the assistant message is retried once.

**Alternatives.** `pg_advisory_lock` (needs a connection held during the LLM call, which D-32 avoids); a queue.

**Trade-off.** No interleaved histories and no held connections, at the price of a 409 the app must show ("still answering").

**Status.** Accepted (Sprint 8, wave 1). Wave 5 (code review): the lock carries its own timestamp as an owner token. A turn that ran past the 2-minute stale window can no longer release a lock a newer turn took after it, and a failed unlock is logged instead of replacing the real outcome (an answer already saved, or the agent's own error). The pool also checks each connection before handing it out (`ConnectionPool.check_connection`), so a connection dropped during a long LLM turn is replaced for every repository call, not only the answer write.

## D-47 Follow-up referent resolved in code (Sprint 8)

**Decision.** `resolve_referent(query, history)` returns the part number when the query names none and the last answer showed exactly one product. The context line then names it as the referent, and the number guard binds the answer's figures to it. With several products shown, the agent asks which one.

**Alternatives.** Rely only on the model calling `get_actuator` again (D-26 prompt rule, the previous behaviour).

**Trade-off.** Deterministic follow-ups for the common case; a small heuristic to maintain.

**Status.** Accepted (Sprint 8, wave 1). Wave 5 (code review): a partial or model-only mention ("765A", "the 767") counts as naming a product, so it is never bound to the one shown before; the "which product do you mean" template is used only when the turn did not call `describe_catalog` or `search_actuators` (then the question was about something else).

## D-48 Voice conversation on the device: speech-to-text and text-to-speech (Sprint 8)

**Decision.** The app transcribes with Android `SpeechRecognizer` (partial results appear in the text field) and sends text to the same endpoint. When a message was spoken, the answer text (not the product tables) is read aloud with Android `TextToSpeech`; a speaker button stops or repeats it. The backend does not change.

**Alternatives.** Send audio to the backend and transcribe with a model through OpenRouter (spends the shared budget and adds a multipart endpoint); text-only answers.

**Trade-off.** Zero cost and offline when the device has the language pack; quality depends on the device's speech engine.

**Status.** Accepted (Sprint 8, wave 4). Supersedes the hook in D-10. Built: a mic button in the chat input (partial results typed into the field), runtime `RECORD_AUDIO` with explanations for denied and permanently denied, a speaker button on each assistant message, and the language picked from the text (`voice/SpeechLanguage.kt`). It works offline when the device has the offline language pack; otherwise the recognizer may need the network.

**Status update (Sprint 9).** Speech-to-text is superseded by D-53 (OpenRouter transcription first, this on-device recognizer as fallback); text-to-speech stays as decided here.

## D-49 OCR in Docker, vision as the fallback (Sprint 8)

**Context.** The evaluation found that re-extracting from the PDF without vision failed (T3 read 9 rows of 11, 78 flagged cells) and that the real vision call had never run.

**Decision.** The image runs the offline RapidOCR extraction; only flagged tables escalate to vision (`EXTRACT_LLM_MODEL`). `STARTUP_ESCALATION=auto` (default) escalates only when a key is configured; without a key a rebuild fails with a clear message. `make ingest-pdf` runs that extraction inside the container. The committed `actuators.json` stays the reproducible path without a key, and it is replaced by the real pipeline output only if that output matches the golden file.

**Alternatives.** Vision for every table (100% in the benchmark, but a paid call on every rebuild); OCR only (offline, not 100%).

**Trade-off.** Offline and deterministic for clean tables, paying only for doubtful ones.

**Status.** Accepted (Sprint 8, wave 1). Result: Verified on 2026-11-06 (Sprint 8): offline OCR reads all 68 rows at 99.75% cell accuracy and flags 8 cells in 4 tables; vision (`anthropic/claude-sonnet-5.5`) re-read those 4 tables in 4 calls for about USD 0.12 (about USD 0.03 per call; OpenRouter books costs late, see the notes in `docs/spend-log.md`), and the output was byte-identical to the committed `actuators.json` (0 cells differ from the golden file). Costs are logged in `docs/spend-log.md`. Two fixes were needed on the way: the OCR dropped two T3 rows (letter O read for zero in the part-number suffix) and flagged the merged N/A block, and the Docker image lacked `poppler-utils` (`pdfimages`), so PDF re-extraction had never worked inside the container.

## D-50 Agent output cap, empty answers and computed comparisons (Sprint 8, wave 3)

**Context.** The first eval rehearsal after wave 1 scored 39/49: 17 of 71 turns came back empty. The cause was the new `AGENT_MAX_TOKENS=1024` spend cap: reasoning models spend part of the cap thinking and can run out before answering. The paid eval also showed the model writing a computed difference ("1250 Nm more") in a comparison, and answering a multi-product follow-up from memory.

**Decision.**
- `AGENT_MAX_TOKENS` defaults to 4096 (worst case about USD 0.002 per call with the default model).
- An empty model answer never reaches the user: `build_result` uses the deterministic template and records `empty_answer_guard` in the trace.
- The prompt forbids differences, ratios, percentages and totals between products: each value is given as printed and the higher one is named in words. The number guard already rejected such figures.
- When the guard fires with no tool data and the previous answer showed several products, the template asks which product is meant (D-47) instead of "could not verify".
- Small talk calls no tools.

**Alternatives.** Keep 1024 and disable reasoning per request (provider-specific); let the model compute differences and verify them in code (a new class of computed numbers to check).

**Trade-off.** A higher per-call ceiling, still bounded, in exchange for no empty answers; comparisons read slightly less fluent ("the 765A00 is higher") but every figure stays printed data.

**Status.** Accepted (Sprint 8, wave 3).

## D-51 Number guard binds a figure to its field, not only to its product (Sprint 9)

**Context.** D-44 binds each figure to the product named before it in the same sentence, but not to the field. "764A00: FLA 9 A" passes when 9 is any value of that product (for example a speed of 9 s). The README listed this as a known limit, and the self-evaluation after Sprint 8 scored number fidelity 3.5/4 for it.

**Decision.** When a figure is bound to a product (a preceding part number in the same sentence or line, or the referent of D-47) and a unit follows it directly, the figure must be a value of that product's fields with that unit. `Nm` maps to `*_nm`, `in-lbs` to `*_in_lbs`, `A` to `fla_*` and `lra_*`, `W` to `motor_power_w`, `%` to the duty cycle, `s` or `seconds` to the speeds, and `cycles/h` or `starts/h` to the counts (English and Spanish unit words). Table notes stay valid for every unit, because they hold the tolerances (±10%, ±5%). A figure without a unit, or with a unit outside this map (Hz, V), keeps the D-44 product rule. Unbound figures keep the global rule. Numbers the user typed and counts of tool results still pass as before.

**Alternatives.** Bind by field name in the text ("FLA", "torque"), which is harder in two languages and with paraphrases. A second LLM pass to verify, which costs money and is not deterministic.

**Trade-off.** It catches a value copied from the wrong column of the right product, at the price of more template answers if the model writes a unit the map does not expect. The final eval measures that rate.

**Status.** Accepted (Sprint 9, wave 0).

**Addendum (Sprint 9 gate).** Binding no longer stops at the sentence that names the part number: when a figure's own sentence or line names no part number and the whole answer mentions exactly one distinct traced product, the figure is bound to that product ("The 764A00 is a good fit. Its FLA is 30 A." now fails, because 30 is its speed). With two or more distinct products in the answer such a figure keeps the global rule, because guessing which one "Its" means would flag correct answers. The exemption for counts of tool results now applies only to figures without a unit from the map: "764A00: FLA 1 A" fails even when 1 is the product count. A figure the user typed still passes even with a unit (for example "gives 100 Nm" after "I need 100 Nm"), accepted trust (D-40) because the same sentence often restates the requirement. Unit detection also accepts markdown emphasis around the figure or unit ("**30** A", "30 **A**"), narrow no-break and thin spaces.

## D-52 Login attempt limit and no user id in the session list (Sprint 9)

**Context.** The Sprint 8 auth audit accepted two risks: no rate limiting on `POST /api/auth/login`, and the test users' documented passwords. `GET /api/sessions` also returns `user_id`, which the app never reads.

**Decision.** At most 5 login attempts per email (lowercased) and client address (the direct peer address; `X-Forwarded-For` is not trusted) in a sliding 5-minute window. The attempt is counted atomically before any hashing, so parallel requests cannot all pass the check. The 6th attempt answers 429 `too_many_attempts` with `Retry-After`, without checking the password, and a success clears the counter. The limit applies to unknown emails too, so the answer never reveals whether an account exists. The counter lives in process memory (one API process). `user_id` is removed from the session list and message payloads.

**Alternatives.** A per-IP limit (it breaks behind a shared NAT and still allows slow guessing on one account), a counter in Postgres or Redis (needed only with several API processes), or account lockout keyed by email alone (it lets anyone who knows an email lock that user out; keying by email and address means an attacker elsewhere cannot).

**Trade-off.** Simple, and it blocks online guessing against one account from one address. Users behind a shared NAT share one counter per email, and an attacker can still guess slowly from many addresses, which the documented test passwords make moot for a demo. The counter resets when the API restarts and is not shared between processes; both are documented.

**Status.** Accepted (Sprint 9, wave 0). Revised in the Sprint 9 gate (key by email and client address, atomic sliding window).

## D-53 Voice input through OpenRouter transcription, Android recognizer as fallback (Sprint 9)

**Context.** D-48 put speech-to-text on the device (`SpeechRecognizer`). The tablet demo showed its weak spot: "764A00-11300000/A" was heard as "76 4a 00113 0000 raya a" (wrong digits and the word "raya"). The tool's not-found suggestions recovered the conversation, but dictating part numbers is the core use of voice here. OpenRouter now exposes a transcription endpoint (`POST /api/v1/audio/transcriptions`) with many speech-to-text models priced per second of audio (USD 0.0000033 to 0.0001 per second on 2026-11-07, so a 5-second question costs USD 0.00002 to 0.0005).

**Decision.**
- The app records the question (AAC in an `.m4a` container, at most 30 s) and sends it to a new backend route `POST /api/transcribe` (Bearer token required, multipart field `audio`, optional `language` `es`/`en`). The backend calls OpenRouter with the server key and `TRANSCRIBE_MODEL` (env var; the model is chosen by the wave V1 experiment and recorded here). The key never ships in the app.
- The backend normalizes the transcript with deterministic rules before returning it: spoken separators ("guion", "raya", "dash" to `-`; "barra", "slash" to `/`) and digit or letter groups of a part number joined ("76 4a 00" to `764A00`). It never invents or snaps a part number to the catalog: a misheard digit still reaches `get_actuator`, whose not-found suggestions handle it.
- Response: `{text, raw_text, model, seconds}`. Errors use the uniform body: 503 `transcription_not_configured` (no key or no `TRANSCRIBE_MODEL`), 503 `transcription_unavailable` (OpenRouter error or timeout), 413 `audio_too_large`, 415 `unsupported_audio`, 429 `too_many_transcriptions` (per-user limit in memory, like D-52).
- Fallback: the app uses the Android recognizer of D-48 when the route answers 503, times out (15 s), or the device is offline. The app waits 15 s; the backend gives the provider 12 s, so the server answers 503 `transcription_unavailable` first. A small ASGI middleware (`app/api/body_limit.py`) rejects `POST /api/transcribe` before the body is read: no Content-Length 411 `length_required`, over 2 MB + 64 KB 413 `audio_too_large` (also while streaming), so an unauthenticated huge upload is never received. The user sees one line ("Using the device recognizer") and keeps talking; nothing else changes. Text-to-speech stays on the device (D-48).
- Spend: every paid test runs inside `app.spend.budgeted`; the experiment and the demo have their own caps.

**Alternatives.** Keep only the Android recognizer (free, partial results while speaking, but no control over accuracy). Whisper on the device with whisper.cpp (free and offline, but a 75-150 MB model in the APK and slow on a tablet). Whisper in the backend container (no per-call cost, but a much larger image and CPU load). An audio-capable chat model with the catalog in the prompt (biasing, but per-token cost and no dedicated endpoint contract).

**Trade-off.** Better and controllable accuracy and the same text path for every device, for a few hundredths of a cent per question, a network round trip and no partial text while speaking. Without a key or network, voice still works through the fallback.

**Model choice (wave V1).** Seven synthetic clips (macOS voices, Spanish and English, part numbers inside questions) through five models, `backend/scripts/stt_bench/REPORT.md`, USD 0.0092 in total. After normalization, `google/gemini-3.5-transcribe` and `openai/whisper-large-v3-turbo` both recovered 5 of 7 part numbers; Gemini wrote the cleanest text (the only exact `764A00-11300000/A`, `/A` instead of "barra oblicua") at about 2.5 s and USD 0.0007 per 5-second question, while Whisper turbo needed more normalization at USD 0.00002. No model wrote part numbers as printed without normalization. The user chose `google/gemini-3.5-transcribe` for transcript quality; the cost difference is negligible against the budget. The synthetic voice read "764X30" as "764 by 30", so the normalizer also maps "by", "por", "equis" or "x" between a model number and two digits to `X`.

**Status.** Accepted (Sprint 9, waves V0 and V1).

## D-54 Spoken answers through OpenRouter text-to-speech, Android TextToSpeech as fallback (Sprint 10)

**Context.** D-48 reads answers aloud with the device `TextToSpeech`, a system voice that sounds dated. OpenRouter exposes `POST /api/v1/audio/speech` (OpenAI-compatible: `model`, `input`, `voice`, `response_format` mp3 or pcm) with 38 speech models on 2026-11-07. Candidates: `google/gemini-3.8-flash-tts` (30 voices, priced per token: USD 0.0000005 per input token and 0.000009 per audio output token; PCM output only) and ElevenLabs (`elevenlabs/eleven-flash-v2.5` and `eleven-turbo-v2.5` at USD 0.00004 per character, `eleven-multilingual-v2` at USD 0.00008 per character; 21 voices; MP3). The user prefers ElevenLabs if the cost difference is small and it is viable.

**Decision.**
- New route `POST /api/speech` (Bearer token): JSON `{text, language?}` with `text` 1 to 1,500 characters (the app sends the same speakable text it gives the device engine: answer text only, no tables). The backend calls OpenRouter with `SPEECH_MODEL` and `SPEECH_VOICE` (env vars) and returns the audio bytes: `audio/mpeg` as received, or PCM wrapped in a WAV header (`audio/wav`) for models that return only PCM. Response headers: `X-Speech-Model`, `X-Speech-Voice`.
- Errors use the uniform body: 503 `speech_not_configured` (no key or no model), 503 `speech_unavailable` (network error, timeout, dropped connection, provider 5xx or no free slot; the app treats it as sticky), 422 `speech_rejected` (other provider 4xx or empty audio; not sticky, the app falls back for that message only), 413 `text_too_long`, 422 validation, 429 `too_many_speech_requests` (per user, 120 per 10 minutes because the app sends one request per sentence, in memory like D-52; also the provider's own 429, with its Retry-After). Limits on the provider call: at most `SPEECH_MAX_CONCURRENCY` (default 8) calls at once (no free slot answers 503 at once) and a 7 s per-operation timeout with a 9 s overall deadline. Nothing is stored on the server.
- App: `CloudSpeaker` plays the returned audio (MediaPlayer) and caches it per message, so the speaker button replays without a second paid call. `FallbackSpeaker` uses the device `TextToSpeech` (D-48) when the route answers 5xx, takes over 8 s, the device is offline, or the text is longer than 1,500 characters; after a failure it stays on the device voice for 5 minutes. Stop and replay work the same on both paths.
- Choice rule (wave S1 experiment, recorded below): ElevenLabs is chosen if it costs at most 3 times Gemini 3.8 Flash TTS and under USD 0.02 for a typical answer, starts in under 3 s, reads Spanish numbers and part numbers correctly, and the user prefers it by ear; otherwise `google/gemini-3.8-flash-tts`.

**Alternatives.** Keep only the device voice (free, offline, dated). Better device voices only (install neural voices; still system voices, device-dependent). Stream audio chunks to start sooner (lower latency, more moving parts on both sides).

**Trade-off.** A modern voice for a fraction of a cent per answer, at the price of 1 to 3 s before the voice starts and a network dependency. Without a key or network, answers are still read aloud by the device.

**Experiment and choice (wave S1, two rounds, `backend/scripts/tts_bench/`, USD 0.141 in total).** Round 1 (4 texts, 2 Spanish and 2 English): Gemini 3.8 Flash TTS (Kore) 7.2 s to first byte, USD 0.010 per 300 characters; ElevenLabs Flash v2.5 (sarah) 0.8 s, USD 0.012; ElevenLabs Multilingual v2 (sarah) 1.3 s, USD 0.024. Round 2 (Spanish only): Gemini Flash Lite (Kore) 5.3 s; Gemini Flash split by sentence 4.7 s to the first sentence; ElevenLabs Flash with `language_code: es`, voices laura and sarah, 0.8 to 1.0 s. The user listened to every file on the tablet: Gemini Kore is the clearly preferred voice, and no ElevenLabs voice sounded right in Spanish, even with the language forced. Decision by the user, overriding the 3 s rule: `google/gemini-3.8-flash-lite-tts` with voice `Kore` (the fastest Kore, cheaper than Flash). Gemini needs about 4.5 s to start even for one short sentence (a fixed start-up time), so latency is handled in the experience:
- spoken questions are answered in sync: the answer bubble and the voice appear together once the first sentence's audio is ready; meanwhile the indicator shows the phases (Transcribing, Thinking, Checking the catalog, Organizing the answer, Generating voice) in the question's language;
- sentences are synthesized in parallel (at most 4 in flight) and played in order without gaps, so only the first sentence's start-up time is felt;
- if the first audio is not ready in 10 s, or the cloud voice fails, the text appears and the device voice reads it;
- typed questions show the text at once and are not read aloud automatically;
- `POST /api/conversation` returns `language` ("es"/"en", computed by code with `detect_lang` from the answer text the user will hear; from the query only if the answer has no letters), which the app sends to `/api/speech`; ElevenLabs receives it as `language_code` if it is configured instead.

**Gate addendum (Sprint 10, wave S4).** A `/code-review high` of the Sprint 10 diff found 10 issues, all fixed with tests: the speaker button now shows Preparing until the first audio plays; cache writes are atomic (temp file, then rename) and cache I/O errors never crash the app; the 12 s reveal backstop starts when the speaker starts preparing (a 30 s safety backstop covers the case where no speaker starts), and every reveal clears the pending auto-speak; speaker scopes are cancelled on release; `language` comes from the answer text; provider 429 maps to 429 and other provider 4xx or empty audio to 422 `speech_rejected` (both non-sticky in the app), network, timeout and 5xx to 503 (sticky); dropped connections map to 503, not 500; at most 8 concurrent provider calls (`SPEECH_MAX_CONCURRENCY`) and a 9 s overall read deadline; one shared sliding-window limiter and one bounded POST helper for transcription and speech.

**Status.** Accepted (Sprint 10, wave S1; user's choice of voice).

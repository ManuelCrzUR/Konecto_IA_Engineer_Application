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

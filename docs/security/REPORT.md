# Security report

Reviewed summary of the Sprint 6 security work: two runs of Cloudflare's `security-audit` skill (vendored in `.claude/skills/security-audit`) and 12 prompt-injection cases in the agent eval (`backend/eval/cases.yaml`, category `injection`; 38/38 passing with the development model). Raw run artifacts (ledgers, `findings.json`, agent results) stay in `docs/security/runs/`, which is gitignored as the skill requires.

**Result: 0 confirmed vulnerabilities; 3 leads that need a deployment fact to settle (see below). Decisions: D-39 (persona, generic tool errors), D-40 (accepted guard risk while single-user).**

## Security audit report — run-2 (Sprint 6.5, scoped re-audit)

### 1. Run
- **Tool:** Cloudflare `security-audit` skill, full-audit workflow, **`quick` profile, scoped run**. Additive to run-1: it reads run-1's ledger and findings.
- **Scope:** the Sprint 6.4 changes (`backend/app/agent/agent.py`, `prompts.py`, `response.py`, `backend/eval/`), the two units run-1 deferred (cross-caller memory poisoning; operator tools), and re-verification of run-1's two `needs_validation` leads. The 7 run-1 units whose relevant source did not change are recorded `out_of_scope` (`prior_covered_same_source`). **Partial pass by design.**
- **Source ref:** `HEAD 21571e4`, dirty worktree (Sprint 5.5 snapshot plus Sprint 6.2–6.4 changes).
- **Budget:** 12 planned, **11 spent** (4 reconnaissance, 3 hunters, 3 verifiers, 1 coverage critic).
- **Execution:** source-only. No OS-enforced sandbox was available, so no target code was executed.
- **Prior run used:** `docs/security/runs/run-1/` (ledger and findings). Both prior leads were carried and re-verified by fresh verifiers against current source (line corrections only).

### 2. Posture summary
Still **no confirmed vulnerability**. The Sprint 6.4 hardening holds: database, pool and OS error text no longer reaches the model, the trace or the client (only argument-validation messages, which contain the caller's own input, are kept); the persona check can only replace the model's own alphabetic name with "Axel", runs after the number guard and cannot change digits or part numbers; the operator tools take input only from the operator and go through the same guard as the API. One new lead concerns the number guard in a multi-user deployment.

### 3. Confirmed findings
None.

### 4. Needs validation
| Lead | Trace | Exact blocker | Bounded local next step | Owner-observed check |
|---|---|---|---|---|
| **New.** The number guard trusts user turns written by any caller of a shared session, so a foreign caller can plant a figure the guard then accepts (`guard-user-history-cross-caller-figure-poisoning`) | `routes_sessions.py:36` (list) → `routes_conversation.py:76`/`:83`/`:85` (post into any session, no author filter) → `agent.py:160` (`user_history` = all user turns) → `response.py:174`, `:201` (allowed set) → `response.py:284` | The model must repeat the planted figure (outside source); more than one human must reach the API (default `127.0.0.1`, single user by D-10); accepted risk under D-26 | Stub LLM that repeats a planted figure after one tool call: assert the guard does not trigger with the figure in another turn's history, and does trigger without it; product cards keep the table value | Confirm whether the API is ever shared or exposed. **Decision D-40:** accepted risk while single-user; when login or exposure arrives, record message authors and count only the current user's turns (or use the strict variant) |
| **Carried.** Anonymous `POST /api/conversation` can drain the paid budget: no rate, concurrency or spend limit (`resource-anonymous-paid-llm-spend-no-rate-limit`) | `routes_conversation.py:65` → `:87` → `agent.py:171` (`RECURSION_LIMIT` at `:67`) → `llm.py:55` | Reachability depends on `API_BIND`; key limits and price outside source; no sandbox | Fake model counting model calls per POST | Check `API_BIND`, key credit and rate limits, model price |
| **Carried.** Unbounded session history is resent on every paid model call (`resource-unbounded-history-resent-to-paid-llm`) | `routes_conversation.py:64` → `:83` → `sessions_repo.py:115` → `prompts.py:108` → `agent.py:171` | Model context and price outside source; reachability depends on `API_BIND`; no sandbox | Fake model recording prompt size over N turns | Check model context and price, key limit, exposure |

Details in `NEEDS-VALIDATION.md`.

### 5. Hardening notes (not findings)
- **Addressed in Sprint 6.4 (D-39):** run-1's "tool exception text reaches clients".
- **Persona is branding, not a disclosure control:** the guard's `original_answer` (pre-persona text) and `persona_guard.params.replaced` in the debug trace still contain the real model name. A model naming itself with a variant not in its id is not rewritten.
- **Persona robustness:** add a regression test that the persona never changes digits or part numbers, and a minimum total token length for multi-token patterns; the pattern is recompiled per request (cheap).
- **Operator tools:** `eval --out` overwrites without a check; provider error text is written into the git-tracked `eval/report.md`; `--workers` has no cap and there is no cost confirmation before a full paid run; `cli.py` catches only `OperationalError` (a malformed `DATABASE_URL` could echo a conninfo fragment); running the CLI or eval can trigger `ensure_data` side effects (guarded, but worth a README note).
- **Multi-user readiness:** when login is added, add an author/`user_id` to `messages`, filter `user_history` by it, and add the user predicate to `list_messages`/`add_message`.

### 6. Coverage
- Ledger: **14 units — 4 covered, 3 candidate, 7 out_of_scope (covered in run-1, unchanged source), 0 deferred, 0 blocked.**
- **Final critic:** no missing units and no reassignments (`stop: true`). The hunter-reported "read side of all sessions under `API_BIND=0.0.0.0`" was judged covered by run-1's access-control and API-authentication units (D-10).
- Combined with run-1, every unit seeded so far has a terminal state. This is still a quick-profile review without local execution, so no claim of complete coverage is made.

## Security audit report — run-1 (Sprint 6.1)

### 1. Run
- **Tool:** Cloudflare `security-audit` skill (vendored at `.claude/skills/security-audit`, upstream commit `c1c8a8c`), full-audit workflow.
- **Profile:** `quick` — one hunter wave and one final coverage critic; one fresh verifier per candidate performs both candidate validation and final record verification. **This is a partial pass by design**; a follow-up run (Sprint 6.5) is additive and picks up the deferred units below.
- **Scope:** `backend/`, `docker-compose.yml`, `backend/Dockerfile`, `.env.example`, `mobile/android/`. Out of scope: `docs/design/`, `backend/data/raw/` (source PDF), `bench/`, developer tooling (`.mcp.json`, `.claude/`).
- **Source ref:** `HEAD 21571e4` with a dirty worktree; the reviewed state is the Sprint 5.5 snapshot `refs/snapshots/sprint-5.5` plus the 6.2 eval-case additions.
- **Budget:** 14 agent invocations planned; **12 spent** (4 reconnaissance, 5 hunters, 1 coverage critic, 2 verifiers).
- **Execution:** sandboxed-source-and-local-only policy. **No OS-enforced sandbox was available, so no target code was executed.** Every check is source-only; anything that needs execution is reported as `needs_validation`.
- **Prior runs:** none (first run).

### 2. Posture summary
No confirmed vulnerability. The code enforces its core invariants from source: the LLM never writes SQL (three read-only tools, `psycopg.sql.Identifier` whitelists, bound parameters, escaped LIKE patterns), product data shown to the user is built by code from tool results, the number guard replaces answers with unverified figures, errors returned to clients are generic, the container runs as a non-root user, both ports bind to `127.0.0.1` by default, and the Android app has one launcher activity, no deep links, no WebView and no stored secrets. The open risk is **operator spend**: the API has no authentication by design (D-10) and no rate or cost bound, so anyone who can reach the port can spend the OpenRouter key. With the default localhost bind that is only the operator.

### 3. Confirmed findings
None.

### 4. Needs validation
| Lead | Trace | Exact blocker | Bounded local next step | Owner-observed check |
|---|---|---|---|---|
| Anonymous `POST /api/conversation` can drain the paid OpenRouter budget: no rate, concurrency or spend limit (`resource-anonymous-paid-llm-spend-no-rate-limit`) | `routes_conversation.py:65` → `:87` → `agent.py:152` (`RECURSION_LIMIT=25`, ~13 model calls) → `llm.py:55` (`max_retries=2`, no `max_tokens`) | Reachability by a non-operator depends on `API_BIND` (default `127.0.0.1`); key credit limit and model price are outside source; no sandbox | Fake chat model that always calls a tool; count model invocations per POST via TestClient; check that a client disconnect does not cancel the handler | Check effective `API_BIND`, the OpenRouter key credit and rate limits, and the `AGENT_MODEL` price |
| Unbounded session history is resent on every paid model call (`resource-unbounded-history-resent-to-paid-llm`) | `routes_conversation.py:65` → `:83` → `sessions_repo.py:115` (no `LIMIT`) → `prompts.py:94` → `agent.py:152` | Model context window, price and key limit are outside source; non-operator reachability depends on `API_BIND`; no sandbox | Fake chat model recording prompt size; seed N turns; assert linear growth and no truncation | Check model context and price, key limit, and exposure; if exposed, add a per-session turn or token cap with a clear 4xx |

The two leads are independent missing controls (request-rate/spend bound vs. aggregate history bound); they share the paid-LLM sink and the no-auth precondition. Details in `NEEDS-VALIDATION.md`.

### 5. Hardening notes (not findings)
- **Tool exception text reaches clients.** `TraceRecorder` stores `str(exc)` of a tool exception in the trace, which is persisted and returned in `debug`; a database error could disclose host or SQL text. Return a generic tool error and log the detail. *Addressed in Sprint 6.4 (D-39).*
- **Debug trace is always returned** (tool params/results and the guard's `original_answer`) by `POST /api/conversation` and `GET /api/sessions/{id}/messages`, unpaginated. Consider a debug flag, truncation and pagination.
- **Number guard limits.** It verifies a flat set of numbers, so a real value attributed to the wrong field passes; numbers written as words are not seen; part numbers are checked as prefixes. The D-26 allowance (numbers from the user's earlier turns) is self-impact only today, but becomes cross-caller with shared sessions (see deferred unit below).
- **Spend and size bounds:** add a rate/concurrency limiter or API token on `POST /api/conversation` if the API is ever exposed, set `max_tokens`, cap history sent to the model, consider fewer retries, and make abandoned requests stop.
- **`list_messages`/`add_message` have no owner filter**; safe today because every caller runs `get_session` first. Add the user predicate before login is introduced.
- **Deployment:** default DB password `series76` is used when unset; no `read_only`/`cap_drop`/`no-new-privileges` in compose; base images use floating tags (pin by digest); Gradle has no dependency verification metadata or wrapper checksum; `/docs` and `/openapi.json` are enabled.
- **Operator spend by default:** `ingest.py` runs the paid vision escalation unless `--no-escalation` is passed (the API defaults to off); consider opt-in.
- **Catalog integrity:** a hand-edited `actuators.json` with plausible values passes validation; only the operator or the container user can write it.
- **Android:** navigation routes interpolate server ids unencoded; release build is unsigned and not minified; debug builds log request URLs (search terms) at BASIC level; the cleartext allowlist (`localhost`, `10.0.2.2`) means the documented Wi-Fi flow needs a config change, which should stay debug-only.

**Positive patterns:** parameterized SQL everywhere, whitelisted identifiers, Literal-typed tool schemas, code-built product cards, generic error bodies, redacted DB URL in startup errors, atomic JSON writes that never overwrite, `uv.lock` with hashes and `--frozen`, `.env` excluded from the image, non-root container, localhost binds, `allowBackup=false`, no exported components beyond the launcher.

### 6. Coverage
- Ledger: **14 units — 10 covered, 2 candidate, 2 deferred, 0 blocked.**
- **Final critic result:** two accepted missing units, recorded as `deferred` (`quick_profile_final_critic`):
  1. **Cross-caller memory poisoning:** any caller can list sessions and append turns to another caller's session; with D-26, planted numbers would then pass the guard for a later reader. Starting paths: `routes_sessions.py`, `sessions_repo.py`, `routes_conversation.py`, `response.py`, `prompts.py`.
  2. **Operator tools:** `cli.py`, `eval/run.py`, `eval/cases.py`, `scripts/build_seed.py`.
- **Excluded companion files** (not installed): memory safety and binary, client-side web, RPC and messaging — no such code in the target. Excluded classes inside selected files are recorded per unit with reasons (no MCP, no browser sessions or identity provider, no CI, no WebView, no export/backup, no cloud IAM).
- No claim of complete coverage is made.

## Appendix: open leads in detail


#### Number guard trusts user turns written by any caller of a shared session, so a foreign caller can plant a figure the guard then accepts

- **Fingerprint:** `guard-user-history-cross-caller-figure-poisoning`
- **Claimed root cause:** allowed_numbers (response.py:174) and unverified_part_numbers (response.py:201) take numbers from the user turns of the whole session. messages stores only a role (schema.sql:87), the history load in post_conversation (routes_conversation.py:83) has no author filter, and no authentication exists (deps.py:46). The D-26 exception, meant for the same author's earlier turns, extends to turns written by other callers.
- **Trace:**
  - entrypoint: `backend/app/api/routes_sessions.py:36` (list_sessions) — Caller B lists all sessions and their UUIDs. get_current_user() is None for everyone, so USER_MATCH matches every session.
  - propagation: `backend/app/api/routes_conversation.py:76` (post_conversation) — B posts {session_id: A's id, query: a false FLA figure for a real part number}. get_session passes, history is loaded with no author filter (line 83), and the poisoned turn is saved as role=user (line 85).
  - propagation: `backend/app/agent/agent.py:160` (run_agent) — On the next turn user_history joins every role=user turn, B's included, and prompts.build_messages sends them to the model as HumanMessages.
  - propagation: `backend/app/agent/response.py:174` (allowed_numbers) — tokens include extract_numbers(user_history), so the planted figure joins the allowed set. unverified_part_numbers (line 201) does the same for part numbers.
  - sink: `backend/app/agent/response.py:284` (build_result) — If the model repeats the planted figure, unverified_numbers returns nothing, the template fallback is skipped, and the free-text answer states a figure that does not match the tables. The assistant message is persisted with it for every reader of the session.
- **Evidence:**
  - `backend/app/db/sessions_repo.py:26` — USER_MATCH = user_id IS NOT DISTINCT FROM %s; with a None user it matches every session.
  - `backend/app/api/deps.py:46` — get_current_user() returns None unconditionally, so there is no per-caller principal.
  - `backend/app/db/schema.sql:87` — messages.role is only 'user' or 'assistant'; there is no author column.
  - `backend/app/agent/response.py:201` — known part numbers include _pn_tokens(user_history), with no attribution.
  - `backend/app/agent/prompts.py:67` — Prompt rule telling the model to verify user-stated figures with a tool and correct them. It is the only other layer and depends on model behavior.
  - `docs/DECISIONS.md:347` — The lenient guard for user-stated numbers is documented as accepted risk. D-10 and the single-user note at line 413 document the missing login.
- **Blockers:**
  - The model must repeat the planted figure in its free text instead of correcting it from a tool result. This depends on model behavior and is outside source.
  - More than one human principal must reach the same API (API_BIND=0.0.0.0 or a shared host). Default deployment is 127.0.0.1 single-user by design (D-10), so a cross-boundary actor is outside source.
  - The project treats this as accepted risk (D-26, DECISIONS.md:347). Whether it is a vulnerability depends on the intended trust model, which source does not settle.
- **Bounded local next step:** No real LLM calls. With a stubbed chat model and a test Postgres (or a monkeypatched sessions_repo), post a poisoned user turn into a session with session_id from list_sessions as a second caller. Then call run_agent with that history and a stub LLM whose final message repeats the planted figure after one get_actuator call. Assert guard_triggered is False and the answer contains the false figure, while products still carry the table value. Add a control where the figure is not in history and assert guard_triggered is True.
- **Owner-observed deployment check:** Confirm the intended trust model: whether the API is ever bound beyond loopback with several human users. Without login (D-10) the finding is a documented limitation; with login, add an author column and restrict user_history to the current principal's turns.

#### Anonymous POST /api/conversation can drain the operator's paid OpenRouter budget with no rate, concurrency or spend limit

- **Fingerprint:** `resource-anonymous-paid-llm-spend-no-rate-limit`
- **Claimed root cause:** No input-to-cost bound at the caller-to-operator-spend boundary. The only gate is a 2000-char query cap. There is no rate limit, per-caller or global budget, max_tokens, concurrency cap, or cancellation on client disconnect, and get_current_user() returns None so no per-principal quota is possible.
- **Trace:**
  - entrypoint: `backend/app/api/routes_conversation.py:65` (post_conversation) — Unauthenticated sync endpoint (get_current_user returns None). Accepts any query up to 2000 chars and a new or existing session.
  - propagation: `backend/app/api/routes_conversation.py:87` (post_conversation) — Calls agent(body.query, history, ...) on every request after releasing the DB connection. No rate, concurrency or budget check precedes it.
  - propagation: `backend/app/agent/agent.py:171` (run_agent) — agent.invoke with recursion_limit=RECURSION_LIMIT (25, line 67; config at line 173). This allows about 12-13 model calls per request. GraphRecursionError only returns a fixed LOOP_ANSWER. No max_tokens and no spend tracking.
  - sink: `backend/app/llm.py:55` (get_llm) — ChatOpenAI(timeout=60, max_retries=2) (lines 55-62) bills the operator's LLM_API_KEY per attempt on OpenRouter. No per-caller accounting.
- **Evidence:**
  - `backend/app/agent/agent.py:67` — RECURSION_LIMIT = 25 is the only per-request step bound.
  - `backend/app/llm.py:61` — max_retries=2 multiplies paid attempts. No max_tokens is set.
  - `backend/app/api/main.py:102` — App factory (lines 102-105) installs only error handlers and the two routers. There is no rate-limit, concurrency or auth middleware, and no grep hit for slowapi, limiter, Semaphore or max_tokens under backend/app (re-checked in run-2).
  - `backend/app/api/deps.py:46` — get_current_user returns None, so there is no principal to attribute quota to.
  - `docker-compose.yml:44` — API port published on ${API_BIND:-127.0.0.1}. The comment at line 43 documents API_BIND=0.0.0.0 as exposing the API on the LAN with no auth.
  - `docs/DECISIONS.md:414` — Known limitation recorded: 'No rate limiting.' Line 413 records no authentication; lines 418-420 record that the localhost bind removes the real exposure.
- **Blockers:**
  - Whether any non-operator can reach the API port depends on the deployed API_BIND (default 127.0.0.1, localhost only; 0.0.0.0 exposes the LAN) and on any proxy in front of it. This is outside the repository.
  - The OpenRouter per-key credit limit and rate limits, and the AGENT_MODEL per-token price, are not visible in source. They decide the real dollar impact per request.
  - No OS-enforced sandbox was available, so a mocked-LLM test counting model calls per request and checking cancellation on disconnect could not be run.
- **Bounded local next step:** In a sandbox with no network and no key, build a fake chat model that always requests a tool call. Call run_agent through a FastAPI TestClient and count model invocations per POST to confirm the roughly 12-13 call bound. With a fake model that sleeps, confirm that a client disconnect does not cancel the handler.
- **Owner-observed deployment check:** Owner checks the effective API_BIND and port exposure of the running compose stack. Owner also checks the OpenRouter key's configured credit limit and per-key rate limit, and the AGENT_MODEL per-token price, to size worst-case spend per request. Owner then decides whether a LAN-exposed deployment needs a rate limit or API token. Do not send audit traffic to the deployment.

#### Unbounded session history is resent in full on every paid model call, so cost per request grows with session length

- **Fingerprint:** `resource-unbounded-history-resent-to-paid-llm`
- **Claimed root cause:** No aggregate bound (turn count, token budget, truncation or compaction) on conversation history that is replayed to the paid LLM. Only a per-message cap of 2000 chars on the user query exists.
- **Trace:**
  - entrypoint: `backend/app/api/routes_conversation.py:64` (post_conversation) — Unauthenticated POST /api/conversation (route decorator at line 64, def at 65). Each call persists a user message (at most 2000 chars) at line 85 and an assistant message afterwards (line 89), with no per-session message cap. Any known session UUID can be reused.
  - propagation: `backend/app/api/routes_conversation.py:83` (post_conversation) — history = to_history(sessions_repo.list_messages(conn, session.id)) loads the whole session. to_history (line 52) only maps rows to HistoryTurn.
  - propagation: `backend/app/db/sessions_repo.py:115` (list_messages) — SELECT of all message columns for the session with ORDER BY created_at, id and no LIMIT (function at line 111). Rows include products and trace jsonb and are validated into pydantic objects.
  - propagation: `backend/app/agent/prompts.py:108` (build_messages) — for turn in history or []: every turn becomes a HumanMessage or AIMessage (function at line 106). No truncation, windowing or token budget.
  - sink: `backend/app/agent/agent.py:171` (run_agent) — agent.invoke receives the full message list from prompts.build_messages (line 169). It is resent on every model call of the tool loop (RECURSION_LIMIT=25, about 13 calls) and billed per input token. Provider context errors become AgentError (503) and the stored history is not trimmed.
- **Evidence:**
  - `backend/app/domain/models.py:213` — ConversationRequest.query has max_length=2000, the only size limit on the path. It is per message, not aggregate.
  - `backend/app/db/sessions_repo.py:87` — add_message stores content, products and trace jsonb with no size or count limit.
  - `backend/app/agent/agent.py:67` — RECURSION_LIMIT=25 bounds model calls per request, not the size of the history sent on each call.
  - `backend/app/api/routes_sessions.py:57` — GET /sessions/{id}/messages returns list_messages in full, with no pagination.
  - `docker-compose.yml:44` — API port is published on ${API_BIND:-127.0.0.1}. The adjacent comment at line 43 documents API_BIND=0.0.0.0 (LAN exposure) with no auth (D-10). Default is localhost-only.
- **Blockers:**
  - Model context window, per-token price and OpenRouter key credit limit (set by operator env AGENT_MODEL and the key) are not in the repository. They decide whether and when growth becomes dollar loss or provider rejection.
  - A non-operator principal can reach the API only if the operator sets API_BIND=0.0.0.0 or fronts it with a proxy or network. The default 127.0.0.1 mode has the operator as the only principal, who is also the budget owner. No source-defined lower-trust principal distinct from the operator is established.
  - No OS-enforced sandbox is available, so no bounded local execution was done. All checks were source-only.
- **Bounded local next step:** With a fake chat model that records the length of the message list and a test DB, seed a session with N turns and assert the prompt size passed to the model grows linearly with N with no truncation. Confirm list_messages has no LIMIT. Run it only inside an approved sandbox, with no real LLM calls.
- **Owner-observed deployment check:** Owner checks the AGENT_MODEL context length and price, the OpenRouter key limit, and whether API_BIND or a fronting proxy exposes the API beyond localhost. If it is exposed, add a per-session turn or token cap with history windowing, and return a clear 4xx instead of a permanent 503 when the cap is reached.

## Sprint 8: focused audit of login and per-user isolation (2026-11-06)

Scope: `backend/app/auth/`, `backend/app/api/{deps,routes_auth,routes_conversation,routes_sessions,errors,main}.py`, `backend/app/db/{schema.sql,sessions_repo.py}`, and the Android auth client (`SessionStore`, `AuthInterceptor`, `AuthRepository`, manifest, network config). Method: code reading plus live requests against the local stack with the seeded test users only (no paid conversation turns).

Result: **no Critical, High or Medium findings.**

Verified: argon2id hashes (pwdlib defaults); unknown email and wrong password give the same 401 body and the same timing (dummy hash); tokens are `secrets.token_urlsafe(32)` (256 bits) stored only as SHA-256, expiry enforced in SQL, logout revokes that token only; malformed `Authorization` headers all return 401 with `WWW-Authenticate: Bearer`; every `/api` route except login requires the token, and auth runs before body validation and before the agent (a rejected request costs nothing); another user's or a missing session id returns the same 404; search is scoped to the user with escaped `LIKE`; the trace is blanked for the `user` role in both the conversation response and the messages listing; all SQL is parameterized; error bodies carry no stack traces; no CORS (native app); API and DB bind to `127.0.0.1`. Android: `allowBackup=false`, cleartext only to `localhost`/`10.0.2.2`, HTTP logging at BASIC (no headers) and only in debug builds.

Fixed after the audit (Low): expired tokens are now deleted when a new one is issued.

Accepted risks (documented in the README): no rate limiting or lockout; seeded test users with documented passwords (`SEED_TEST_USERS=off` for anything beyond a demo); token stored unencrypted in DataStore on the device; `/docs` and `/openapi.json` public; `user_id` (the caller's own id) is still part of `SessionOut`; the release APK is signed with the debug key for local installs.

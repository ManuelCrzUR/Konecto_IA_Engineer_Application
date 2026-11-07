# Sprint 8: evaluation fixes, login and voice

Planning record for Sprint 8. Status per wave is updated as the work lands.

## Why this sprint exists

After Sprint 7 we ran an independent evaluation of the delivery: five parallel reviewers worked on clean clones (reproducibility, data and ingestion, agent and tools, Android app, API and deliverables), with no OpenRouter key and about 90 adversarial tool inputs. It is kept privately and summarized here. Result: it passes the reproducibility gate, about 81/100. Risks it found:

1. `ingest.py --from-pdf` cannot rebuild the data without vision: OCR reads 9 of 11 rows in table T3 and flags 78 cells. The real vision path had never run.
2. Docs and code disagree: the README calls a failing command an offline re-extraction; the README says `debug` where the messages endpoint returns `trace`; `ARCHITECTURE.md` claimed a `/api/sessions` shape it does not return.
3. The number guard always accepts integers 0 to 10 and 90, does not bind a number to its product, and ignores numbers written as words.
4. The whole history is resent on every turn.
5. Follow-ups depend on the model calling the tool again.
6. No per-session concurrency control; the answer is lost if its write fails.
7. Debug is protected only by a hidden gesture.
8. Dead code in the benchmark copies folder (`app/ingestion/_reference/`, removed in wave 1); little accessibility in the app.
9. Optional features (login, voice) scored 0.

We also found, by using the app, that small talk felt robotic: the agent re-introduced itself on every greeting.

## How it is run

- Waves of small tasks (one module plus its test), each done by a Sonnet (code) or Haiku (docs, black-box tests, verification) subagent that first invokes the skill the task needs. Opus writes the contracts, integrates and decides.
- At the end of each wave: full test suite, a plain-language summary for the developer, a suggested commit, and a stop until the developer approves. One commit per wave.
- Steps that spend the OpenRouter key are marked $ and need explicit approval. The key expires on 2026-11-09, so those steps go first.
- Controlled spend (task 1.0, approved caps): every paid step runs inside `app.spend.budgeted(step, max_usd)`, which reads the key usage before and after (never printing the key), refuses to start when the key cannot be read or has less than the cap left, and appends the real cost to `docs/spend-log.md`. Every paid step climbs the same ladder: free rehearsal with a fake LLM, cost estimate, one real call, full run, logged cost. Caps: vision run USD 0.50, final eval USD 0.10, demo USD 0.10, whole sprint USD 1.00. The demo runs on the emulator (no tablet available).

## Waves

| Wave | Content | Decisions | Status |
|---|---|---|---|
| 0 | Contracts: auth module stubs, schema (`users`, `auth_tokens`, `sessions.busy_since`, FK), decisions, this plan | D-43 to D-49 | Done |
| 1 | Spend control (1.0), OCR fix (T3) and real hybrid run ($), OCR in Docker with vision fallback, docs fixes, `_reference/` cleanup, history window, number guard v2, follow-up referent, natural small talk, per-session lock | D-44 to D-47, D-49 | Done |
| 2 | Login backend: argon2 hashes, opaque tokens, 401 on every `/api` route, per-user isolation, trace only for `developer`, seeded test users | D-43 | Done |
| 3 | Real eval with the final model ($), new cases (number words, wrong-product numbers, follow-ups with 1 and 3 products, 30-turn session, small talk) | D-50 | Done |
| 4 | Android: login screen and token, Debug only for `developer`, voice input (`SpeechRecognizer`), voice output (`TextToSpeech`), accessibility | D-48 | Done |
| 5 | Gate: full suites, brief checklist, `/simplify`, `/code-review`, scoped security audit of auth, real demo ($), README, clean-clone test | — | Pending |

## Skills per task

| Task | Skill |
|---|---|
| OCR fix | `pdf` |
| History window, small talk, referent | `langchain-fundamentals`, `langchain-middleware` |
| Schema, lock, auth tables | `supabase-postgres-best-practices` |
| Login backend | `security-audit`, `supabase-postgres-best-practices` |
| Android tasks | `android-development`, plus `android-permissions-security` (microphone), `testing-setup` (login), `adaptive` (touch targets) |
| Gate | `simplify`, `code-review`, `security-audit` |

## Wave log

### Wave 0: contracts

- `backend/app/db/schema.sql`: `users`, `auth_tokens`, FK `sessions.user_id -> users.id`, `sessions.busy_since`.
- `backend/app/auth/{passwords,tokens,repo,seed}.py` and `backend/app/api/routes_auth.py`: contract docstrings and signatures (implemented in wave 2).
- `backend/tests/conftest.py`: `test_users` fixture; the four isolation tests now create real users (the FK requires them).
- `docs/DECISIONS.md`: D-43 to D-49; D-10 and D-11 point to them.
- Tests: backend 1337 passed.

### Wave 1: data and backend fixes

| Task | Result |
|---|---|
| 1.0 Spend control | `app/spend.py` `budgeted(step, max_usd)`: fails closed, refuses when the key has less than the cap left, logs each paid step to `docs/spend-log.md` (waits and re-reads, since OpenRouter reports usage late). `max_tokens` per task (agent 1024, extract 4096), `max_retries` 1, at most `VISION_MAX_CALLS` (7) vision calls per run, `eval/run.py --max-usd`. A conftest fixture blocks OpenRouter in every test. |
| 1A OCR | Rows per table now exact (T3 9 -> 11: the suffix check dropped part numbers read with a letter O; the merged N/A box made 4 rows flag). Cell accuracy 95.2% -> 99.75%, flagged cells 78 -> 8 (all 5 real misreads among them), 4 tables still escalate. New slow test against the golden file. |
| 1B Real vision run ($) | Ladder followed: fake-escalator rehearsal (0 cells differ), estimate (about USD 0.19 at most), one real call on T3 (11/11 rows, 0 differences), Docker OCR-only rehearsal, full Docker run: 4 calls, output byte-identical to the committed `actuators.json`. |
| 1C OCR in Docker | `STARTUP_ESCALATION=auto` by default; `make ingest-pdf` writes to `backend/data/rebuilt/` (bind mount, gitignored). Found and fixed: the image had no `poppler-utils`, so PDF re-extraction had never worked inside Docker. |
| 1D Docs | README offline-command text and `debug`/`trace`, `ARCHITECTURE.md` sessions shape, benchmark copies removed (cells fixture moved to `tests/fixtures/`). |
| 1E History window | `HISTORY_TURNS` (10); the product context still scans the whole history. |
| 1F Number guard v2 | No always-allowed integers, number words (EN/ES), figures bound to the product they follow, counts of tool results verified. 29 black-box tests written separately from the contract, all passing. |
| 1G Referent | `agent/referent.py`; the context line names the only product of the previous answer, or asks to clarify among several; the guard binds figures to it. |
| 1H Turn lock | `sessions.busy_since`; a concurrent turn gets 409 `turn_in_progress`; the assistant write is retried once. |
| 1I Small talk | Introduces itself only on the first turn; later greetings get a short natural reply; 5 `small_talk` eval cases. |

Tests: backend 1418 passed, plus 8 slow (OCR against golden). ruff, format and mypy clean. Spend in this wave: about USD 0.149 for the five vision calls (first logged as USD 0.031 because OpenRouter books costs late; corrected in wave 3, see `docs/spend-log.md`).

### Wave 2: login backend

| Task | Result |
|---|---|
| 2A `app/auth/` | argon2id hashes (`pwdlib`), opaque tokens stored as SHA-256 (7 days), `authenticate` with a dummy hash for unknown emails (no timing leak), idempotent seeding of the three test users. 26 tests. |
| 2B API | `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`; 401 `unauthorized` + `WWW-Authenticate: Bearer` on every other `/api` route; `user.id` passed to every session query (another user's session answers 404); `debug`/`trace` empty for role `user`. Existing API tests act as a seeded developer. 25 tests. |
| 2C Black-box tests | 20 HTTP tests written from the contract only. They found a real bug before wiring: `seed.py` read the count as a tuple, which fails on the API's `dict_row` connections (fixed, regression test added). |
| Docs | README quick start logs in first, endpoint table, test users table; `.env.example` `SEED_TEST_USERS`; `recovery.sh` scenario (e) logs in as ana. |

Verified on the Docker stack (no LLM calls): no token 401, wrong password and unknown email give the same body, `/me`, logout then 401, `/health` public, hashes stored as `$argon2id$`. Note: sessions created before login have no owner and are not shown to anyone. One Docker build failed on a transient network error while installing the new dependency; the retry succeeded.

Tests: backend 1489 passed, plus 8 slow. ruff, format and mypy clean. Spend in this wave: USD 0.

### Wave 3: real evaluation

| Step | Result | Cost |
|---|---|---|
| New cases | 4 more (number word, two-product comparison, follow-up after several products, 12-turn session past the 10-message window): 49 cases, 71 turns | — |
| Rehearsal 1, free model | 39/49. 17 of 71 turns were empty: the wave-1 cap `AGENT_MAX_TOKENS=1024` ran out while the model reasoned. Confirmed on the 8 failing cases with 4096 (8/8). | USD 0 |
| Fixes (D-50) | Cap 4096; an empty answer falls back to the template; the first answer to a technical question no longer starts with an introduction; one case expectation corrected | — |
| Rehearsal 2, free model | 48/49 | USD 0 |
| One real case, `gpt-6-luna` | 1/1 | USD 0.00006 |
| Full run 1 | 47/49: the model computed a difference ("1250 Nm more", caught by the guard) and looked up a product for "lol ok" | USD 0.011 |
| Fixes (D-50) | Comparison rule in the prompt (values as printed, no differences); no tools for small talk; a guard hit on a multi-product follow-up asks which product | — |
| Full run 2 | 47/49 (model variance: a follow-up answered from memory, caught by the guard) | USD 0.012 |
| Full run 3, final code | **48/49 (98%)**, 0 empty answers. The failure (`subset-02`) answers correctly but via `describe_catalog` | USD 0.008 |

Spend control finding: OpenRouter books a call's cost late, sometimes in parts (20-50 s for chat, more than a minute for vision). The wave-1 log under-reported the vision run (USD 0.031 logged, about USD 0.149 real, matching the estimate). `budgeted` now polls the key for 2 minutes after paid calls; the log carries a correction note. Sprint spend so far: about USD 0.18 of the USD 1.00 cap.

Tests: backend 1493 passed, plus 8 slow.

### Wave 4: Android login and voice

| Task | Result |
|---|---|
| 4A Login | `login/LoginScreen.kt` and `LoginViewModel.kt` (email, password, show/hide, errors under the form). Token in the `auth` DataStore (`data/SessionStore.kt`); `data/AuthInterceptor.kt` sends `Authorization: Bearer`. Any 401 outside the login call clears the session and returns to Login with the back stack cleared. Splash routes by the stored session. Sign out in the Account menu calls logout best-effort and always clears the local session. A 409 `turn_in_progress` is retryable (Retry banner). |
| 4B Debug role gate | The 5-tap gesture opens Debug only for role `developer`; for `user` it does nothing (the backend already sends empty traces). |
| 4C Voice input | `voice/VoiceInput.kt`: mic button, `SpeechRecognizer` with partial results typed into the field, `RECORD_AUDIO` requested at runtime. If denied, the app explains and typing keeps working; if denied permanently, it points to Settings; if the device has no recognizer, voice is unavailable. |
| 4D Voice output | `voice/Speaker.kt`: `TextToSpeech` reads the answer text (not product cards or tables) of a spoken message; every assistant message has a speaker button (read or stop). `voice/SpeechLanguage.kt` picks Spanish or English from the text. Numbers and part numbers are read as printed. |
| 4E Accessibility | Content descriptions, 48 dp touch targets, TalkBack headings and live regions. |

Tests: 132 Android unit tests pass (`./gradlew testDebugUnitTest`), `lintDebug` has no errors and no accessibility warnings, and all 35 instrumented tests pass on the emulator (`connectedDebugAndroidTest`, API 37). The instrumented run caught two real problems, both fixed: the Send and Back buttons were 40 dp (now 48 dp), and a card test needed `useUnmergedTree` after the card merged its semantics for TalkBack. Backend: no change in this wave.

Emulator smoke test (no OpenRouter calls): wrong password shows "Wrong email or password"; ana signs in and sees only her own (empty) list; the session survives a force-stop; five taps on the title do nothing for ana; the mic asks for `RECORD_AUDIO`, a denial shows "Microphone permission needed — you can still type", and after granting it the recognizer starts (no audio on the emulator, so it reports "Didn't catch that, try again"); Sign out returns to Login and Back leaves the app instead of reopening ana's list. Spoken answers read aloud need a real turn, so they move to the wave 5 demo.

Spend in this wave: USD 0 (no OpenRouter calls). Sprint spend stays at about USD 0.18 of the USD 1.00 cap.

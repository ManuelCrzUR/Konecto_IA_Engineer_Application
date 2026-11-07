# Sprint 9: closing the self-evaluation gaps

Planning record for Sprint 9. Status per wave is updated as the work lands.

## Why this sprint exists

After Sprint 8 we re-ran the same 9-criterion rubric as the external evaluation, on a clean clone of `b5b641e` without a key. It scored about 90/100 (81 before Sprint 8), with both optional features complete. This sprint closes the gaps that can be closed without redoing the project. Three limits are kept and documented: the extractor is tuned to this PDF, the UI polish scope, and the third-party skills in `.claude/`.

| Criterion | Gap | Fix |
|---|---|---|
| Number fidelity | Figures bound to a product, not to a field | D-51: unit-aware field binding; `no_match` messages print whole numbers as printed (9000, not 9000.0) |
| Code quality | `response.py` and `ocr.py` near 400 lines, against the ~150-line rule | Split into single-purpose modules; public imports unchanged |
| Agent and tools | Eval case `subset-02` rejects a correct answer reached through `describe_catalog` | The case accepts either valid tool; new cases for field binding; final paid eval |
| API | No login rate limit, `user_id` in session payloads | D-52 |
| App and docs | Screenshots predate login and voice; four stale passages; `TOOLING.md` has no Sprint 8 | New screenshots from the tablet, doc fixes, unused images removed |
| Deliverables | Large commits | One commit per micro-task |

## How it is run

Same as Sprint 8: Opus writes the contracts, integrates and decides; each micro-task is one module plus its tests, done by a Sonnet or Haiku subagent that first invokes its skill. Work runs on `main` without worktrees (the folders of a wave do not overlap). The user makes the commits; the work stops at the end of each wave. Paid steps run inside `app.spend.budgeted`; sprint cap USD 0.10.

## Waves

| Wave | Content | Decisions | Status |
|---|---|---|---|
| 0 | Contracts, D-51, D-52, this plan | D-51, D-52 | Done |
| 1 | 1A guard split + field binding + whole numbers in `no_match`; 1B `ocr.py` split; 1C login limit + no `user_id`; 1D eval cases | D-51, D-52 | Done |
| 2 | Final paid eval (`openai/gpt-6-luna`, cap USD 0.05) | | Done |
| 3 | Tablet screenshots (login, voice, Debug), README / ARCHITECTURE / TOOLING fixes | | Done |
| 4 | Gate: suites, verifier, code review, clean clone, new self-evaluation | D-51, D-52, D-53 addenda | Done (eval re-run pending approval) |

## Skills per task

| Task | Model | Skill |
|---|---|---|
| 1A guard | Sonnet (+ Haiku black-box tests) | `langchain-fundamentals` |
| 1B OCR split | Sonnet | `anthropic-skills:pdf` |
| 1C login limit | Sonnet | `security-audit`, `supabase-postgres-best-practices` |
| 1D eval cases | Haiku | `langchain-fundamentals` |
| 3 screenshots | Opus (mobile MCP) | `android-development` |
| 4 gate | Opus | `/simplify`, `/code-review` |

## Wave log

### Wave 0: contracts (done)

D-51 (unit-aware field binding) and D-52 (login attempt limit, no `user_id` in payloads) written with alternatives and trade-offs; this plan added. Spend: USD 0.

### Wave 1: backend fixes (done)

Five subagents in parallel, one folder each, each invoking its skill first.

- **1A guard (Sonnet, `langchain-fundamentals`).** `response.py` (397 lines) is now `response.py` (90, `build_result` and re-exports, so no caller changed), `products.py` (61, one shared iteration over traced products, which removed a duplicate), `guard.py` (188), `units.py` (43, the D-51 unit map), `template.py` (104) and `persona.py` (43). D-51: a figure bound to a product and followed by a unit must be a value of that product's fields with that unit (Nm, in-lbs, A, W, %, s, cycles/h, starts/h, English and Spanish words); table notes stay valid for every unit. `no_match` messages print whole numbers as printed (9000, not 9000.0). New `tests/test_guard_fields.py` (18 cases).
- **1A black-box tests (Haiku).** `tests/test_guard_fields_blackbox.py`, written from the D-51 text only: 37 cases, 9 failing before the implementation (the wrong-column cases), 37 passing after.
- **1B OCR split (Sonnet, `pdf`).** `ocr.py` (396 lines) is now `ocr.py` (74, entry points and re-exports), `ocr_boxes.py` (112), `ocr_layout.py` (115) and `ocr_cells.py` (168). No logic change: the slow OCR tests give the same results before and after, and a direct measurement gives 68 rows and 5 cells out of 2040 different from the golden file (99.75%), as documented.
- **1C login limit (Sonnet, `security-audit`, `supabase-postgres-best-practices`).** `app/auth/attempts.py` (75): 5 failed sign-ins per email in 5 minutes, then 429 `too_many_attempts` with `Retry-After`, checked before any password hashing; unknown emails are limited the same way. `SessionOut` is an explicit model without `user_id`. README sections 2, 5 and 7 and `docs/security/REPORT.md` updated. New `tests/test_login_attempts.py` (11 tests).
- **1D eval cases (Haiku, `langchain-fundamentals`).** New expectation `tools_any` (at least one of these tools); result checks run only when the tool that carries them was called. `subset-02` accepts `search_actuators` or `describe_catalog`. Three new cases bind several fields with units (`lookup-05`, `lookup-06`, `multi-04`): 52 cases in total.

Integration (Opus): the subagents' DB-backed runs collided on the shared test database while they ran in parallel; the full suite after all of them finished gives **1567 passed** (8 slow OCR tests deselected and passing), ruff, format and mypy clean. Spend: USD 0.

### Wave 2: final paid eval (done)

Ladder as in Sprint 8: one real case first (`lookup-05`, USD 0.00027), then the full run inside `app.spend.budgeted("eval", 0.05)`. Result: **52/52 (100%)**, USD 0.011458 (`docs/spend-log.md`). Every category at 100%. `subset-02` passed through `describe_catalog` with the right answer. The field-bound guard (D-51) replaced no correct answer: every case that expects `guard_ok` passed. README (case count, final evaluation, the number-guard bullet) and ARCHITECTURE section 8 updated. Sprint spend so far: about USD 0.012.

### Wave 3: screenshots and docs (done)

- **3A screenshots (Opus, `android-development`).** Captured on the Lenovo Tab M11 (Android 15) against the local API rebuilt with the Sprint 9 code (`make up`, data kept): sign in, voice dictation in progress, the spoken answer with its product card and speaker buttons, and the Debug screen as `dev@konecto.test`. The README gallery now shows these plus the conversations list and the comparison table; 15 images no document used were removed (`docs/screenshots/` keeps 6). The voice exchange was real and is described under the gallery: the recognizer heard "764A00-11300000/A" as "76 4a 00113 0000 raya a" (wrong digits), `get_actuator` answered not found with the closest part numbers, and the follow-up "es del primero" got the right card. Spoken part numbers are a known weak spot of on-device recognition; the not-found suggestions are what recover it. Agent model from `.env` (free), USD 0.
- **3B docs (Haiku).** README section 7 rewritten in order (Sprint 6 findings, Sprint 8 login and audit, Sprint 9 limit) with the risks still open; `TOOLING.md` gains Sprints 8 and 9 skill usage and an honest `swarm` entry (Opus fixed a second sentence that contradicted it); `ARCHITECTURE.md` section 8 final runs, section 11 decisions D-43 to D-50 and a Sprint 9 item, new modules in the tree; `CLAUDE.md` section 10 status.

### Extra: login animation (done)

User request: Axel spins once on a successful sign-in and fades out before the conversations screen. `login/WelcomeSpin.kt` (71 lines): form fades in 200 ms, Axel turns 360 degrees with a slight scale-up in 700 ms, then shrinks and fades in 300 ms (about 1.0 s, `FastOutSlowInEasing`, `Animatable` read in `graphicsLayer`); skipped when system animations are off (`LocalAnimationsEnabled`); `canSubmit` is false during the animation, so no double submit. Sonnet with `android-development` and `jetpack-compose-performance`. Unit tests, lint and `LoginScreenTest` (3/3 on the emulator) pass; the full instrumented suite runs in the wave 4 gate.

### Voice waves V0-V1: OpenRouter transcription with the Android recognizer as fallback (D-53)

The tablet demo showed that the on-device recognizer mishears dictated part numbers. The user chose OpenRouter transcription as the primary path with the current recognizer as fallback. V0: D-53 contract (route `POST /api/transcribe`, errors, limits, fallback rules) and real prices from the public Models API (USD 0.0000033 to 0.0001 per second of audio). V1: `backend/scripts/stt_bench/run.py`, one-call probe (USD 0.00002) then 7 synthetic clips through 5 models (USD 0.0092, `budgeted` cap 0.03). Result in D-53 and `backend/scripts/stt_bench/REPORT.md`; the user chose `google/gemini-3.5-transcribe`.

### Voice wave V2: build (done)

Each task in its own folder, each invoking its skill first.

- **V2-A backend (`security-audit`).** `backend/app/speech/client.py` (one OpenRouter call, 20 s timeout, no retries, audio never stored), `backend/app/speech/limits.py` (20 requests per 10 minutes per user, in memory, D-53) and `backend/app/api/routes_transcribe.py` (`POST /api/transcribe` and the D-53 error codes). Dependency added: `python-multipart`. Route and client tests: 22.
- **V2-B normalizer (`langchain-fundamentals`, plus Haiku black-box tests).** `backend/app/speech/normalize.py`: spoken separators, joined digit groups, "por" or "by" between a model number and two digits to `X`, canonical shape only when the characters fit. 128 normalizer tests, 25 of them black-box, written by Haiku from the D-53 text.
- **V2-C Android (`android-development`, `android-permissions-security`).** `voice/CloudVoiceInput.kt` (record, then transcribe, with the Transcribing state), `voice/FallbackVoiceInput.kt` (the Notice and the 5-minute memory), `voice/AudioRecorder.kt` (AAC in an m4a container, 16 kHz mono, 64 kbps, 30 s cap) and `data/Transcriber.kt` (15 s timeout). 153 JVM unit tests.

Integration: the backend suite passes with **1602 tests** after the three tasks were merged.

### Voice wave V3: docs (done); tablet demo pending

This wave changed docs only: README (sections 4, 6 and 8), `docs/DECISIONS.md` (D-48 status update), `docs/ARCHITECTURE.md`, `docs/TOOLING.md` and `CLAUDE.md` section 10. Spend: USD 0.

The tablet demo was deferred. The tablet disconnected during the run, so the spend-log row `demo-voice-tablet` shows USD 0 and "not run". The demo runs again before the key expires on 2026-11-09. Until then, the wave 4 gate tests recording on the emulator instead.

### Wave 4: final gate (done)

- **`/code-review high`** over `git diff b5b641e` (all of Sprint 9) found 10 issues; all fixed by five parallel subagents, each with its skill:
  - Normalizer (`langchain-fundamentals`): the Spanish "a" before a number was glued into a fake part number ("764 a 60 Hz" -> "764A60 Hz"); a base-only result followed by a unit is now left as written.
  - Test loss: the speech normalizer tests had overwritten `tests/test_normalize.py` (the ingestion normalizer tests, including the 68-row golden round trip). Opus restored it from git and moved the speech tests to `tests/test_speech_normalize*.py`.
  - Guard (`langchain-fundamentals`): a figure in a later sentence is bound to the only product the answer names; counts no longer exempt a figure with a unit; units after markdown emphasis or narrow spaces are detected; `guard.py` 188 -> 140 lines (`guard_values.py` added). D-51 addendum.
  - Login limiter (`security-audit`): keyed by email and client address (an attacker elsewhere can no longer lock a user out), atomic `try_begin` counted before hashing, sliding window. D-52 revised.
  - Transcription (`security-audit`): `app/api/body_limit.py` rejects a missing length (411) or an oversized body (413) before parsing or auth; provider timeout 12 s, under the app's 15 s. D-53 updated.
  - Android (`android-development`): the recorder backstop is 31 s so the 30 s cap is the only normal stop; a recording is kept when `stop()` throws with data.
- **Suites:** backend 1668 passed (8 slow OCR tests deselected), ruff, format, mypy clean; Android 156 unit tests, lint clean, **36 instrumented tests on the emulator, 0 failures** (cold-restarted emulator).
- **End-to-end voice:** two synthetic clips through `POST /api/transcribe` on the running stack (USD 0.0017, about 2.8 s each); on the emulator, the app recorded through MediaRecorder, showed Listening, Transcribing and sent the transcript (the emulator microphone picked up room noise, which Gemini transcribed as a short Spanish phrase: with pure noise the model can return invented text, a known limit). The tablet demo with real dictation stays pending until the tablet is connected (before the key expires on 2026-11-09).
- **Clean copy** of exactly the files to be committed, no `.env` (copied from `.env.example`, other ports): `make up` healthy with 68 rows, `make test` 1668 passed, the app builds and its tests pass; without a key `/api/transcribe` answers 503 `transcription_not_configured`, which is what sends the app to the device recognizer.
- Not run: `/simplify` (the code review covered the same diff and its fixes were applied) and a separate `security-audit` run (the auth and upload fixes were made with that skill). The final eval was not re-run after the stricter guard: it needs a paid run (about USD 0.012) and the user's approval.

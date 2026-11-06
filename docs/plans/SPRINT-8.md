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
8. Dead code in `app/ingestion/_reference/`; little accessibility in the app.
9. Optional features (login, voice) scored 0.

We also found, by using the app, that small talk felt robotic: the agent re-introduced itself on every greeting.

## How it is run

- Waves of small tasks (one module plus its test), each done by a Sonnet (code) or Haiku (docs, black-box tests, verification) subagent that first invokes the skill the task needs. Opus writes the contracts, integrates and decides.
- At the end of each wave: full test suite, a plain-language summary for the developer, a suggested commit, and a stop until the developer approves. One commit per wave.
- Steps that spend the OpenRouter key are marked $ and need explicit approval. The key expires on 2026-11-09, so those steps go first.

## Waves

| Wave | Content | Decisions | Status |
|---|---|---|---|
| 0 | Contracts: auth module stubs, schema (`users`, `auth_tokens`, `sessions.busy_since`, FK), decisions, this plan | D-43 to D-49 | Done |
| 1 | OCR fix (T3) and real hybrid run ($), OCR in Docker with vision fallback, docs fixes, `_reference/` cleanup, history window, number guard v2, follow-up referent, natural small talk, per-session lock | D-44 to D-47, D-49 | Pending |
| 2 | Login backend: argon2 hashes, opaque tokens, 401 on every `/api` route, per-user isolation, trace only for `developer`, seeded test users | D-43 | Pending |
| 3 | Real eval with the final model ($), new cases (number words, wrong-product numbers, follow-ups with 1 and 3 products, 30-turn session, small talk) | — | Pending |
| 4 | Android: login screen and token, Debug only for `developer`, voice input (`SpeechRecognizer`), voice output (`TextToSpeech`), accessibility | D-48 | Pending |
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

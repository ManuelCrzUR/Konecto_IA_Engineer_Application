# Sprint 10: spoken answers with a cloud voice (D-54)

Planning record. Status per wave is updated as the work lands.

## Why

The user wants a modern voice for Axel's spoken answers. D-54: OpenRouter text-to-speech first (Gemini 3.8 Flash TTS or ElevenLabs, chosen by an experiment and by ear), the device `TextToSpeech` of D-48 as fallback.

## How it is run

Same as Sprints 8 and 9: Opus writes contracts, integrates and decides; Sonnet or Haiku subagents do the micro-tasks after invoking their skill; the user makes the commits; paid steps run inside `app.spend.budgeted` (sprint cap USD 0.15).

| Wave | Content | Who / skill | Spend cap | Status |
|---|---|---|---|---|
| S0 | D-54 contract, real prices and voices | Opus | 0 | Done |
| S1 | Experiment: 4 real answers (es/en, numbers, part numbers) x Gemini 3.8 Flash TTS and two ElevenLabs models; cost, latency, audio for the user to judge | Sonnet writes the script (`langchain-fundamentals`), Opus runs it | USD 0.10 | Done (two rounds, USD 0.141) |
| S2 | `/api/speech` backend; Android `CloudSpeaker` + `FallbackSpeaker` with cache | Sonnet (`security-audit`); Sonnet (`android-development`) | 0 | Done (plus S2.5) |
| S3 | Tablet demo, README, D-54 result, D-48 note | Opus; Haiku (docs) | USD 0.05 | Done (USD 0.023) |
| S4 | Gate: code review, suites, emulator tests, clean copy, self-evaluation | Opus and subagents | 0 | Done |

## Wave log

### Wave S0: contract (done)

D-54 written; prices and voice lists read from the public Models API (Gemini TTS: 30 voices, per-token pricing, PCM only; ElevenLabs: 21 voices, per-character pricing, MP3). Spend USD 0.

### Wave S1, round 1: first comparison (done)

`backend/scripts/tts_bench/run.py` (written by a Sonnet subagent, run by Opus). Probe with one sentence per model (USD 0.0154), then 4 texts (2 Spanish, 2 English) x 3 models (USD 0.0896). The second run went over its USD 0.08 cap by about USD 0.01, because `budgeted` checks after each model and the last model crossed it; round 1 cost USD 0.105 in total against the planned USD 0.10.

| Model | Voice | Time to first byte | Cost per 300 characters |
|---|---|---|---|
| `google/gemini-3.8-flash-tts` | Kore | 7.2 s | USD 0.010 |
| `elevenlabs/eleven-flash-v2.5` | sarah | 0.8 s | USD 0.012 |
| `elevenlabs/eleven-multilingual-v2` | sarah | 1.3 s | USD 0.024 |

The user listened to the 12 files on the tablet: Gemini Kore is the favourite voice; ElevenLabs sounds fluent but mixes English into Spanish answers. Causes: no `language_code` was sent, and `sarah` is an English-native voice. Gemini's 7 s before the first word fails the 3 s rule. Round 2 tests Spanish forced on ElevenLabs, another voice, Gemini Flash Lite, and sentence-by-sentence synthesis (user-approved, cap USD 0.05).

### Wave S1, round 2 (done)

User-approved, cap USD 0.05; cost about USD 0.036 (Spanish texts only; ElevenLabs on es1 only to stay under the cap). A first launch passed the arguments through a zsh variable and ran nothing (USD 0); it was relaunched with bash.

| Variant | First audio | Cost |
|---|---|---|
| Gemini Flash, Kore | 8.7 s | USD 0.010 (2 texts) |
| Gemini Flash Lite, Kore | 6.8 s (TTFB 5.3 s) | USD 0.007 |
| Gemini Flash, Kore, sentence by sentence | 5.3 s (TTFB 4.7 s) | USD 0.011 |
| ElevenLabs Flash v2.5, laura, `language_code: es` | 1.3 s | USD 0.004 (1 text) |
| ElevenLabs Flash v2.5, sarah, `language_code: es` | 0.8 s | USD 0.004 (1 text) |

The user judged by ear: no ElevenLabs voice sounds right in Spanish; Gemini Kore stays, with Flash Lite. The user also chose synchronized text and voice for spoken questions, with Claude-Code-style phase labels while waiting, and asked to remove the static "Looking up the tables..." text. Recorded in D-54. Spend note: the 30-minute tablet demo budget row overlaps these bench rows; annotated in `docs/spend-log.md`.

### Wave S2 and S2.5: build (done)

S2 done by two Sonnet subagents: backend `/api/speech` (84 tests in its run), Android `CloudSpeaker` and `FallbackSpeaker` with a per-message cache (175 unit tests). S2.5 done (Android 201 unit tests, backend 87 in its run): Android sentence pipeline, synchronized reveal, phase labels, animated speaker button, 10 s safety net; backend defaults (Flash Lite, Kore), 120 speech requests per 10 minutes, `language` in the conversation response.

### Wave S3: tablet demo and docs (done)

The user tested on the Lenovo Tab M11 with the agent on `openai/gpt-6-luna`: spoken questions transcribed by Gemini (`/api/transcribe`), answers read by Gemini Flash Lite with voice Kore (`/api/speech`, several sentences per answer), all 200 OK in the API log. Spend for the 30-minute demo window: USD 0.023 (cap 0.05). Docs pass by a Sonnet subagent: README sections 1, 2, 4, 6, 8 and 9, ARCHITECTURE sections 4, 5, 6, 9 and 11, TOOLING Sprint 10 rows, CLAUDE.md status; all relative links resolve.

### Wave S4: final gate (done)

- `/code-review high` over the Sprint 10 diff: 10 issues, all fixed by two Sonnet subagents (Android with `android-development`, backend with `security-audit`); see the D-54 gate addendum.
- Suites: backend 1719 passed (8 slow OCR tests deselected), ruff, format, mypy clean; Android 211 unit tests, lint clean, 36 instrumented tests on the emulator with 0 failures.
- Clean copy of exactly the files to commit, no `.env` (copied from `.env.example`, other ports): `make up` healthy with 68 rows, `make test` 1719 passed; without a key `/api/speech` answers 503 `speech_not_configured` (the app then uses the device voice), 413 over 1,500 characters, 401 without a token.
- Not committed by design: `backend/scripts/tts_bench/audio/` (ignored), the local Postgres volume with test conversations.
- Sprint 10 spend: about USD 0.164 (experiment 0.141, demo 0.023). Key usage at the end of the sprint: about USD 0.51 of 10.

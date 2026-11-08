# OpenRouter spend log

Rows are appended automatically by `backend/app/spend.py` after every paid step.

Notes (corrected by hand, Sprint 8 wave 3):
- OpenRouter books a call's cost late, sometimes in parts. The first rows below under-report: the key's `usage_daily` for 2026-11-06 was USD 0.1489 when the rows summed to USD 0.031. The two eval smoke runs with `openai/gpt-6-luna` cost USD 0.000059 each (measured by polling the key for 3 minutes), and the `stealth/crouton-alpha` rehearsals cost USD 0 (also measured). So the five `anthropic/claude-sonnet-5.5` vision calls (smoke T3 + full run) cost about USD 0.149 in total, about USD 0.03 per call, which matches the pre-run estimate (USD 0.036 per call).
- Since then `budgeted` polls the key for 2 minutes after paid calls (SETTLE_S) and logs the last value.

| date (UTC) | step | model | calls | spent USD | cap USD | outcome |
|---|---|---|---|---|---|---|
| 2026-11-06T16:02:43+00:00 | vision-smoke T3 | anthropic/claude-sonnet-5.5 | 1 | 0.001257 | 0.10 | ok |
| 2026-11-06T16:14:02+00:00 | vision full run (make ingest-pdf) | anthropic/claude-sonnet-5.5 | 0 | 0.000000 | 0.50 | failed |
| 2026-11-06T16:17:03+00:00 | vision full run (make ingest-pdf) | anthropic/claude-sonnet-5.5 | 4 | 0.029448 | 0.50 | ok |
| 2026-11-06T19:55:19+00:00 | eval | stealth/crouton-alpha | 49 | 0.000000 | 0.01 | ok |
| 2026-11-06T19:57:53+00:00 | eval | stealth/crouton-alpha | 8 | 0.000000 | 0.01 | ok |
| 2026-11-06T20:10:01+00:00 | eval | stealth/crouton-alpha | 49 | 0.000000 | 0.01 | ok |
| 2026-11-06T20:12:14+00:00 | eval | stealth/crouton-alpha | 9 | 0.000000 | 0.01 | ok |
| 2026-11-06T20:12:56+00:00 | eval | openai/gpt-6-luna | 1 | 0.000000 | 0.02 | ok |
| 2026-11-06T20:18:57+00:00 | eval | openai/gpt-6-luna | 1 | 0.000000 | 0.02 | ok |
| 2026-11-06T20:27:29+00:00 | eval | openai/gpt-6-luna | 49 | 0.011262 | 0.10 | ok |
| 2026-11-06T20:30:05+00:00 | guard probe (guard-compare-01) x2 | openai/gpt-6-luna | 2 | 0.000196 | 0.01 | ok |
| 2026-11-06T20:35:36+00:00 | eval | openai/gpt-6-luna | 49 | 0.011921 | 0.08 | ok |
| 2026-11-06T20:41:07+00:00 | eval | openai/gpt-6-luna | 49 | 0.008063 | 0.06 | ok |
| 2026-11-06T23:11:09+00:00 | demo-emulator | stealth/crouton-alpha | 2 | 0.000000 | 0.10 | ok |
| 2026-11-07T04:23:18+00:00 | eval | openai/gpt-6-luna | 1 | 0.000270 | 0.01 | ok |
| 2026-11-07T04:27:45+00:00 | eval | openai/gpt-6-luna | 52 | 0.011458 | 0.05 | ok |
| 2026-11-07T05:23:24+00:00 | stt-bench | openai/whisper-large-v3-turbo | 1 | 0.000023 | 0.01 | ok |
| 2026-11-07T05:26:39+00:00 | stt-bench | openai/whisper-large-v3-turbo,openai/whisper-large-v3,openai/gpt-4o-mini-transcribe,mistralai/voxtral-mini-transcribe-3-0,google/gemini-3.5-transcribe | 35 | 0.009110 | 0.03 | ok |
| 2026-11-07T07:34:03+00:00 | demo-voice-tablet | google/gemini-3.5-transcribe + agent | 0 | 0.000000 | 0.05 | not run: tablet disconnected (usage re-read by hand, 0.330294 before and after) |
| 2026-11-07T15:42:20+00:00 | transcribe-e2e (API, 2 clips) | google/gemini-3.5-transcribe | 2 | 0.001718 | 0.01 | ok |
| 2026-11-07T15:56:29+00:00 | eval | openai/gpt-6-luna | 52 | 0.011426 | 0.05 | ok |
| 2026-11-07T23:07:48+00:00 | tts-bench | google/gemini-3.8-flash-tts,elevenlabs/eleven-flash-v2.5,elevenlabs/eleven-multilingual-v2 | 3 | 0.015397 | 0.03 | ok |
| 2026-11-07T23:10:51+00:00 | tts-bench | google/gemini-3.8-flash-tts,elevenlabs/eleven-flash-v2.5,elevenlabs/eleven-multilingual-v2 | 12 | 0.089615 | 0.08 | ok |
| 2026-11-07T23:19:55+00:00 | tts-bench | google/gemini-3.8-flash-tts | 2 | 0.010104 | 0.01 | ok |
| 2026-11-07T23:22:20+00:00 | tts-bench | google/gemini-3.8-flash-lite-tts | 2 | 0.007308 | 0.01 | ok |
| 2026-11-07T23:24:56+00:00 | tts-bench | google/gemini-3.8-flash-tts | 5 | 0.010942 | 0.01 | ok |
| 2026-11-07T23:26:46+00:00 | demo-voice-tablet | google/gemini-3.5-transcribe + agent | 1 | 0.139985 | 0.05 | overlap: this 30-min window also contains the tts-bench rows above (0.133366); the demo itself (transcriptions + gpt-6-luna test turn) was about 0.0066 |
| 2026-11-07T23:27:05+00:00 | tts-bench | elevenlabs/eleven-flash-v2.5 | 1 | 0.003800 | 0.01 | ok |
| 2026-11-07T23:29:13+00:00 | tts-bench | elevenlabs/eleven-flash-v2.5 | 1 | 0.003800 | 0.01 | ok |
| 2026-11-08T00:27:07+00:00 | demo-voice-tts-tablet | gemini-3.5-transcribe + gpt-6-luna + gemini-3.8-flash-lite-tts | 1 | 0.022950 | 0.05 | ok |

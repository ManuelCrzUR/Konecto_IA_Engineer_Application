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

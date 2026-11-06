# OpenRouter spend log

Rows are appended automatically by `backend/app/spend.py` after every paid step.

Note: the vision-smoke T3 row was first logged as 0.000000 because OpenRouter reports usage a few seconds late; corrected by hand from the key usage (0.127760 at the end of Sprint 7 -> 0.129017), an upper bound for that call. `budgeted` now waits and re-reads (SETTLE_S).

| date (UTC) | step | model | calls | spent USD | cap USD | outcome |
|---|---|---|---|---|---|---|
| 2026-11-06T16:02:43+00:00 | vision-smoke T3 | anthropic/claude-sonnet-5.5 | 1 | 0.001257 | 0.10 | ok |
| 2026-11-06T16:14:02+00:00 | vision full run (make ingest-pdf) | anthropic/claude-sonnet-5.5 | 0 | 0.000000 | 0.50 | failed |
| 2026-11-06T16:17:03+00:00 | vision full run (make ingest-pdf) | anthropic/claude-sonnet-5.5 | 4 | 0.029448 | 0.50 | ok |

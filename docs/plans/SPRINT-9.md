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
| 2 | Final paid eval (`openai/gpt-6-luna`, cap USD 0.05) | | Pending |
| 3 | Tablet screenshots (login, voice, Debug), README / ARCHITECTURE / TOOLING fixes | | Pending |
| 4 | Gate: suites, verifier, code review, clean clone, new self-evaluation | | Pending |

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

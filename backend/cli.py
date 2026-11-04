"""Terminal chat with the Series 76 assistant (no API needed).

Usage (from backend/):
    uv run python cli.py                    # interactive chat, multi-turn
    uv run python cli.py -q "question"      # one question, then exit
    uv run python cli.py --debug            # also print the tool trace

Contract:
- main(argv=None) -> int (exit code). Steps: load .env; open a connection,
  apply_schema and ensure_data(conn) (the self-healing chain; escalation OFF:
  the CLI never makes a paid vision call); then chat.
- Chat loop: read a line ("> " prompt); empty line is ignored; "exit", "quit"
  or EOF ends with code 0. Each turn calls run_agent(query, history) and keeps
  history in memory as HistoryTurn items (user turn, then assistant turn with
  part_numbers = the result's product part numbers).
- Output per turn: the answer; then, if any, one line per product
  ("  <part_number> | <voltage> | <enclosure> | <key printed fields>");
  with --debug, one line per ToolTrace (tool, params, duration) and a note when
  guard_triggered.
- Errors: LLMConfigError -> message naming the variable, exit 2.
  AgentError -> print a short error and continue the loop (exit 1 in -q mode).
  Postgres unreachable -> clear message ("start it: docker compose up -d db"), exit 1.
- format_turn(result, debug) -> str is the pure formatter used for output
  (tested without I/O). run_agent is looked up at call time from
  app.agent.agent so tests can monkeypatch it.
"""

from __future__ import annotations

import argparse
import json
import sys

import psycopg
from dotenv import load_dotenv

from app.agent import agent as agent_mod
from app.bootstrap import ensure_data
from app.db.connection import apply_schema, connect
from app.domain.conversation import AgentResult, HistoryTurn
from app.domain.models import Product
from app.ingestion.pipeline import ExtractionError
from app.ingestion.store_json import CatalogFileError
from app.ingestion.validate import ValidationFailed
from app.llm import LLMConfigError

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_CONFIG = 2

# On a product line, the first present field of each group is shown.
KEY_FIELD_GROUPS: tuple[tuple[str, ...], ...] = (
    ("onoff_torque_in_lbs", "mod_torque_in_lbs", "output_torque_in_lbs"),
    ("onoff_duty_cycle_pct", "mod_duty_cycle_pct", "duty_cycle_pct"),
    ("speed_sec_60hz", "speed_sec"),
    ("fla_60hz_a", "fla_a"),
)


def _format_product(product: Product) -> str:
    parts = [product.part_number, product.voltage, product.enclosure]
    for group in KEY_FIELD_GROUPS:
        for name in group:
            value = product.fields.get(name)
            if value is not None:
                parts.append(f"{name}={value:g}")
                break
    if not product.has_data:
        parts.append("no data")
    if not product.csa_certified:
        parts.append("not CSA certified")
    parts.extend(product.notes)
    return "  " + " | ".join(parts)


def format_turn(result: AgentResult, debug: bool = False) -> str:
    lines = [result.answer]
    lines.extend(_format_product(p) for p in result.products)
    if debug:
        for t in result.trace:
            params = json.dumps(t.params, ensure_ascii=False, sort_keys=True, default=str)
            took = "? ms" if t.duration_ms is None else f"{t.duration_ms:.0f} ms"
            lines.append(f"  [tool] {t.tool}({params}) {took}")
        if result.guard_triggered:
            lines.append("  note: number guard replaced the answer (a figure did not match)")
    return "\n".join(lines)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chat with the Series 76 assistant.")
    parser.add_argument("-q", "--question", help="ask one question, print the answer and exit")
    parser.add_argument("--debug", action="store_true", help="also print the tool trace")
    return parser.parse_args(argv)


def _chat(debug: bool) -> int:
    history: list[HistoryTurn] = []
    while True:
        try:
            line = input("> ")
        except EOFError:
            print()
            return EXIT_OK
        query = line.strip()
        if not query:
            continue
        if query.lower() in ("exit", "quit"):
            return EXIT_OK
        try:
            result = agent_mod.run_agent(query, history)
        except agent_mod.AgentError as exc:
            print(f"error: {exc}", file=sys.stderr)
            continue
        print(format_turn(result, debug))
        pns = [p.part_number for p in result.products]
        history += [
            HistoryTurn(role="user", content=query),
            HistoryTurn(role="assistant", content=result.answer, part_numbers=pns),
        ]


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = _parse_args(argv)
    try:
        with connect() as conn:  # ensure_data runs with escalator=None: no paid vision call
            apply_schema(conn)
            ensure_data(conn, escalator=None)
        if args.question is not None:
            try:
                result = agent_mod.run_agent(args.question, [])
            except agent_mod.AgentError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return EXIT_FAILED
            print(format_turn(result, args.debug))
            return EXIT_OK
        return _chat(args.debug)
    except LLMConfigError as exc:
        print(f"error: {exc}. Set it in .env (see .env.example).", file=sys.stderr)
        return EXIT_CONFIG
    except psycopg.OperationalError as exc:
        print(
            f"error: cannot reach Postgres ({exc}). Is it running? Try: docker compose up -d db",
            file=sys.stderr,
        )
        return EXIT_FAILED
    except (ExtractionError, ValidationFailed, CatalogFileError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())

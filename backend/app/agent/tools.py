"""LangChain tools: thin wrappers over db/actuators_repo. No LLM knowledge here.

Contract:
- normalize_part_number(text) -> str: uppercase, strip spaces and '*',
  tolerate missing '/A' or missing voltage suffix (e.g. '764a00' -> '764A00').
- lookup_actuator(conn, part_number) -> ActuatorLookup   (pure, testable)
- search(conn, filters) -> SearchResult                   (pure, testable)
- describe(conn) -> CatalogSummary                        (pure, testable)
- make_tools(conn_factory) -> list[BaseTool]: `get_actuator`, `search_actuators`,
  `describe_catalog` as @tool functions whose output is
  `model.model_dump(mode="json")`. The LLM never writes SQL.
"""

from __future__ import annotations

import psycopg
from langchain_core.tools import BaseTool

from app.db.connection import ConnFactory
from app.domain.search import ActuatorLookup, CatalogSummary, SearchFilters, SearchResult

TOOL_NAMES = ("get_actuator", "search_actuators", "describe_catalog")


def normalize_part_number(text: str) -> str:
    raise NotImplementedError


def lookup_actuator(conn: psycopg.Connection, part_number: str) -> ActuatorLookup:
    raise NotImplementedError


def search(conn: psycopg.Connection, filters: SearchFilters) -> SearchResult:
    raise NotImplementedError


def describe(conn: psycopg.Connection) -> CatalogSummary:
    raise NotImplementedError


def make_tools(conn_factory: ConnFactory) -> list[BaseTool]:
    raise NotImplementedError

"""Loads and enforces policy.yaml -- the single source of truth for what
Claude is allowed to see and do in this database. No guardrail elsewhere in
this codebase is hard-coded; everything reads from here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class TablePolicy:
    read: bool = False
    write: bool = False
    columns: list[str] = field(default_factory=list)
    pii_columns: list[str] = field(default_factory=list)
    row_limit: int | None = None
    primary_key: str | None = None
    writable_columns: list[str] = field(default_factory=list)


@dataclass
class Policy:
    tables: dict[str, TablePolicy]
    default_row_limit: int
    query_timeout_seconds: int

    def readable_tables(self) -> set[str]:
        return {name for name, t in self.tables.items() if t.read}

    def writable_tables(self) -> set[str]:
        return {name for name, t in self.tables.items() if t.write}

    def table(self, name: str) -> TablePolicy | None:
        return self.tables.get(name)

    def row_limit_for(self, name: str) -> int:
        t = self.tables.get(name)
        if t and t.row_limit:
            return t.row_limit
        return self.default_row_limit


def load_policy(path: str | Path | None = None) -> Policy:
    resolved = Path(path or os.environ.get("POLICY_PATH", "policy.yaml"))
    if not resolved.exists():
        raise FileNotFoundError(
            f"Policy file not found: {resolved}. "
            "Copy policy.example.yaml to policy.yaml and edit it."
        )
    raw = yaml.safe_load(resolved.read_text()) or {}

    tables = {
        name: TablePolicy(
            read=cfg.get("read", False),
            write=cfg.get("write", False),
            columns=cfg.get("columns", []),
            pii_columns=cfg.get("pii_columns", []),
            row_limit=cfg.get("row_limit"),
            primary_key=cfg.get("primary_key"),
            writable_columns=cfg.get("writable_columns", []),
        )
        for name, cfg in (raw.get("tables") or {}).items()
    }

    return Policy(
        tables=tables,
        default_row_limit=raw.get("default_row_limit", 100),
        query_timeout_seconds=raw.get("query_timeout_seconds", 5),
    )


_policy: Policy | None = None


def get_policy() -> Policy:
    """Cached singleton, mirroring db.get_pool()'s pattern -- load once,
    reuse for every tool call in this process."""
    global _policy
    if _policy is None:
        _policy = load_policy()
    return _policy

"""PII redaction -- two strategies, used in different places:

- redact_row()/redact_rows(): precise, policy-driven masking of specific
  columns in structured query results (query()/describe_table()'s rows).
  This is the primary guardrail -- it always knows exactly which columns
  are PII because policy.yaml says so.
- redact_text(): a regex safety net for free-form text (the raw SQL a
  caller sent), used before writing it to the audit log. Someone could type
  a literal email into a WHERE clause -- that's not a "column", so
  redact_row() can't catch it, but the audit log still shouldn't retain it
  in the clear.
"""

from __future__ import annotations

import re

MASK = "***REDACTED***"

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\+?\d[\d\-\s]{7,}\d")


def redact_row(row: dict, pii_columns: set[str]) -> dict:
    return {key: (MASK if key in pii_columns else value) for key, value in row.items()}


def redact_rows(rows: list[dict], pii_columns: set[str]) -> list[dict]:
    return [redact_row(r, pii_columns) for r in rows]


def redact_text(text: str) -> str:
    text = _EMAIL_RE.sub(MASK, text)
    text = _PHONE_RE.sub(MASK, text)
    return text

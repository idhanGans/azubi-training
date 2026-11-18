"""Gemeinsame Model-Helfer."""
from datetime import datetime, timezone


def utcnow():
    """Zeitzonenbewusster Zeitstempel (UTC) — Spalten sind `timestamptz`."""
    return datetime.now(timezone.utc)


def iso(value):
    """Zeitstempel als ISO-8601 mit Offset (oder None)."""
    return value.isoformat() if value else None

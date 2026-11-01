"""Audit trail entries for changes to a case."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.models.entities import AuditLog


def log_action(session: Session, case_id: UUID | None, action: str, details: dict[str, Any]) -> None:
    """Adds an audit entry to the session. The caller commits it with the change it describes."""
    session.add(AuditLog(case_id=case_id, action=action, details=details))

"""SQLModel tables and workflow status enums."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Returns the current time in UTC."""
    return datetime.now(UTC)


class CaseStatus(StrEnum):
    draft = "draft"
    intake_submitted = "intake_submitted"
    checklist_ready = "checklist_ready"
    qa_reviewed = "qa_reviewed"


class ChecklistApplicability(StrEnum):
    required = "required"
    recommended = "recommended"
    conditional = "conditional"
    not_applicable = "not_applicable"


class ChecklistProgressStatus(StrEnum):
    not_started = "not_started"
    pending = "pending"
    in_progress = "in_progress"
    uploaded = "uploaded"
    almost_done = "almost_done"
    approved = "approved"
    complete = "complete"
    not_applicable = "not_applicable"


class UploadStatus(StrEnum):
    requested = "requested"
    uploaded = "uploaded"
    confirmed = "confirmed"


class ReviewStatus(StrEnum):
    pending = "pending"
    reviewed = "reviewed"


class OCRStatus(StrEnum):
    not_started = "not_started"
    queued = "queued"
    complete = "complete"


class IssueSeverity(StrEnum):
    blocking = "blocking"
    important = "important"
    recommended = "recommended"


class CaseRecord(SQLModel, table=True):
    __tablename__ = "cases"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    case_name: str = Field(max_length=255, index=True)
    workflow_type: str = Field(default="marriage_concurrent", max_length=64)
    status: str = Field(default=CaseStatus.draft.value, max_length=64)
    petitioner_email: str | None = Field(default=None, max_length=255)
    beneficiary_email: str | None = Field(default=None, max_length=255)
    country_of_focus: str | None = Field(default=None, max_length=8)
    readiness_score: int = 0
    readiness_label: str = Field(default="Not started", max_length=64)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class PersonRecord(SQLModel, table=True):
    __tablename__ = "people"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    case_id: UUID = Field(foreign_key="cases.id", index=True)
    role: str = Field(max_length=32, index=True)
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=255)
    country_of_birth: str | None = Field(default=None, max_length=8)
    country_of_citizenship: str | None = Field(default=None, max_length=8)
    location: str | None = Field(default=None, max_length=32)
    entered_us_legally: bool | None = None
    current_immigration_status: str | None = Field(default=None, max_length=120)
    annual_income: float | None = None
    employment_status: str | None = Field(default=None, max_length=120)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class MarriageRecord(SQLModel, table=True):
    __tablename__ = "marriages"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    case_id: UUID = Field(foreign_key="cases.id", index=True)
    marriage_date: date | None = None
    first_marriage_for_both: bool | None = None
    has_children: bool | None = None
    household_size: int | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class IntakeResponse(SQLModel, table=True):
    __tablename__ = "intake_responses"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    case_id: UUID = Field(foreign_key="cases.id", index=True)
    step_key: str = Field(max_length=64, index=True)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CaseChecklistItem(SQLModel, table=True):
    __tablename__ = "case_checklist_items"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    case_id: UUID = Field(foreign_key="cases.id", index=True)
    code: str = Field(max_length=96, index=True)
    category: str = Field(max_length=64, index=True)
    label: str = Field(max_length=255)
    applicability: str = Field(default=ChecklistApplicability.required.value, max_length=32)
    completion_status: str = Field(default=ChecklistProgressStatus.not_started.value, max_length=32)
    owner_role: str = Field(default="shared", max_length=32)
    description: str = Field(sa_column=Column(Text))
    why_needed: str = Field(sa_column=Column(Text))
    what_to_save_now: str = Field(default="", sa_column=Column(Text))
    conditional_reason: str | None = Field(default=None, sa_column=Column(Text))
    sort_order: int = 0
    item_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class UploadedDocument(SQLModel, table=True):
    __tablename__ = "uploaded_documents"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    case_id: UUID = Field(foreign_key="cases.id", index=True)
    checklist_item_code: str | None = Field(default=None, max_length=96, index=True)
    original_filename: str = Field(max_length=255)
    stored_filename: str | None = Field(default=None, max_length=255)
    mime_type: str | None = Field(default=None, max_length=120)
    file_size: int = 0
    upload_status: str = Field(default=UploadStatus.requested.value, max_length=32)
    review_status: str = Field(default=ReviewStatus.pending.value, max_length=32)
    ocr_status: str = Field(default=OCRStatus.not_started.value, max_length=32)
    extraction_confidence: float = 0.0
    document_type: str | None = Field(default=None, max_length=120)
    document_language: str = Field(default="unknown", max_length=32)
    requires_translation: bool = False
    has_translation: bool = False
    version: int = 1
    extracted_fields: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class QAIssue(SQLModel, table=True):
    __tablename__ = "qa_issues"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    case_id: UUID = Field(foreign_key="cases.id", index=True)
    severity: str = Field(max_length=32, index=True)
    code: str = Field(max_length=120, index=True)
    title: str = Field(max_length=255)
    description: str = Field(sa_column=Column(Text))
    checklist_item_code: str | None = Field(default=None, max_length=96)
    is_resolved: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class Invitation(SQLModel, table=True):
    __tablename__ = "invitations"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    case_id: UUID = Field(foreign_key="cases.id", index=True)
    email: str = Field(max_length=255)
    role: str = Field(default="collaborator", max_length=64)
    status: str = Field(default="pending", max_length=32)
    created_at: datetime = Field(default_factory=utcnow)


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    case_id: UUID | None = Field(default=None, foreign_key="cases.id", index=True)
    action: str = Field(max_length=120, index=True)
    actor: str = Field(default="system", max_length=120)
    details: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)

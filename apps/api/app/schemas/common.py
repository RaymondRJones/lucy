"""Pydantic models for API requests and responses."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.entities import ChecklistProgressStatus


class PersonRead(BaseModel):
    role: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    country_of_birth: str | None = None
    country_of_citizenship: str | None = None
    location: str | None = None
    entered_us_legally: bool | None = None
    current_immigration_status: str | None = None
    annual_income: float | None = None
    employment_status: str | None = None

    model_config = ConfigDict(from_attributes=True)


class MarriageRead(BaseModel):
    marriage_date: date | None = None
    first_marriage_for_both: bool | None = None
    has_children: bool | None = None
    household_size: int | None = None

    model_config = ConfigDict(from_attributes=True)


class CaseCreateRequest(BaseModel):
    case_name: str = Field(min_length=3, max_length=255)
    petitioner_email: str | None = Field(default=None, max_length=255)
    beneficiary_email: str | None = Field(default=None, max_length=255)
    country_of_focus: str | None = Field(default=None, max_length=64)


class CaseUpdateRequest(BaseModel):
    case_name: str | None = Field(default=None, min_length=3, max_length=255)
    petitioner_email: str | None = Field(default=None, max_length=255)
    beneficiary_email: str | None = Field(default=None, max_length=255)
    country_of_focus: str | None = Field(default=None, max_length=64)


class CaseRead(BaseModel):
    id: UUID
    case_name: str
    workflow_type: str
    status: str
    petitioner_email: str | None = None
    beneficiary_email: str | None = None
    country_of_focus: str | None = None
    readiness_score: int
    readiness_label: str
    created_at: datetime
    updated_at: datetime
    petitioner: PersonRead | None = None
    beneficiary: PersonRead | None = None
    marriage: MarriageRead | None = None
    counts: dict[str, int]


class InvitationCreateRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    role: str = Field(default="collaborator", max_length=64)


class InvitationRead(BaseModel):
    id: UUID
    email: str
    role: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IntakeStepWrite(BaseModel):
    step_key: str = Field(min_length=2, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)


class IntakeStepRead(BaseModel):
    step_key: str
    payload: dict[str, Any]
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IntakeStateRead(BaseModel):
    case_id: UUID
    steps: list[IntakeStepRead]
    merged: dict[str, Any]
    missing_fields: list[str]


class IntakeSubmitResponse(BaseModel):
    case_id: UUID
    status: str
    missing_fields: list[str]
    generated_items: int
    facts: dict[str, Any]


class PrescreenQuestionnaireRead(BaseModel):
    version: str
    verified_on: str
    sources: list[dict[str, Any]]
    questions: list[dict[str, Any]]


class PrescreenStateRead(BaseModel):
    case_id: UUID
    answers: dict[str, Any]
    answer_sources: dict[str, Any] = Field(default_factory=dict)
    evaluation: dict[str, Any]


class PrescreenAnswersWrite(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


class ChecklistItemRead(BaseModel):
    id: UUID
    case_id: UUID
    code: str
    category: str
    label: str
    applicability: str
    completion_status: str
    owner_role: str
    description: str
    why_needed: str
    what_to_save_now: str
    conditional_reason: str | None = None
    sort_order: int
    item_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChecklistResponse(BaseModel):
    case_id: UUID
    facts: dict[str, Any]
    items: list[ChecklistItemRead]


class ChecklistItemUpdateRequest(BaseModel):
    completion_status: str | None = Field(default=None, max_length=32)

    @field_validator("completion_status")
    @classmethod
    def validate_completion_status(cls, value: str | None) -> str | None:
        if value is None:
            return value
        allowed_statuses = {status.value for status in ChecklistProgressStatus}
        if value not in allowed_statuses:
            raise ValueError(f"Unsupported checklist status '{value}'.")
        return value


class UploadRequestCreate(BaseModel):
    checklist_item_code: str | None = Field(default=None, max_length=96)
    original_filename: str = Field(min_length=1, max_length=255)
    mime_type: str | None = Field(default=None, max_length=120)
    document_language: str = Field(default="unknown", max_length=32)
    has_translation: bool = False
    extracted_fields: dict[str, Any] = Field(default_factory=dict)


class UploadRequestRead(BaseModel):
    upload_id: UUID
    upload_url: str
    max_upload_size_mb: int


class UploadConfirmRequest(BaseModel):
    document_type: str | None = Field(default=None, max_length=120)
    document_language: str | None = Field(default=None, max_length=32)
    has_translation: bool | None = None
    extracted_fields: dict[str, Any] | None = None
    extraction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class UploadedDocumentRead(BaseModel):
    id: UUID
    case_id: UUID
    checklist_item_code: str | None = None
    original_filename: str
    stored_filename: str | None = None
    mime_type: str | None = None
    file_size: int
    upload_status: str
    review_status: str
    ocr_status: str
    extraction_confidence: float
    document_type: str | None = None
    document_language: str
    requires_translation: bool
    has_translation: bool
    version: int
    extracted_fields: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QAIssueRead(BaseModel):
    id: UUID
    severity: str
    code: str
    title: str
    description: str
    checklist_item_code: str | None = None
    is_resolved: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QASummaryRead(BaseModel):
    score: int
    label: str
    explanation: str
    issue_counts: dict[str, int]
    required_completion_pct: int


class QAResultsRead(BaseModel):
    case_id: UUID
    summary: QASummaryRead
    issues: list[QAIssueRead]


class FilingValidationRequest(BaseModel):
    form_codes: list[str] | None = None
    template_paths: dict[str, str] = Field(default_factory=dict)


class FilingValidationIssueRead(BaseModel):
    form_code: str
    severity: str
    code: str
    title: str
    description: str
    source: str
    field_key: str | None = None
    question_id: str | None = None
    pdf_ref: str | None = None
    pdf_fields: list[str] = Field(default_factory=list)
    expected: Any = None
    actual: Any = None


class FilingValidationFormResultRead(BaseModel):
    form_code: str
    label: str
    status: str
    issue_counts: dict[str, int]
    field_count: int
    required_field_count: int
    missing_required_count: int
    template_field_count: int
    template_path: str | None = None
    source: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)
    issues: list[FilingValidationIssueRead]


class FilingValidationResponseRead(BaseModel):
    case_id: UUID
    generated_at: datetime
    validation_scope: list[str]
    summary: dict[str, Any]
    assumptions: dict[str, Any]
    forms: list[FilingValidationFormResultRead]
    roadmap: list[dict[str, Any]]


class FilingValidationCapabilitiesRead(BaseModel):
    default_validation_scope: list[str]
    supported_form_codes: list[str]
    forms: list[dict[str, Any]]


class G1450BillingAddressWrite(BaseModel):
    street_1: str = Field(min_length=1, max_length=160)
    street_2: str = Field(default="", max_length=80)
    city: str = Field(min_length=1, max_length=80)
    state: str = Field(min_length=2, max_length=32)
    postal_code: str = Field(min_length=3, max_length=20)


class G1450CardDetailsWrite(BaseModel):
    cardholder_name: str = Field(min_length=1, max_length=160)
    credit_card_type: str = Field(min_length=1, max_length=32)
    credit_card_number: str = Field(min_length=12, max_length=32)
    expiration_month: str = Field(min_length=1, max_length=2)
    expiration_year: str = Field(min_length=2, max_length=4)
    security_code: str = Field(min_length=3, max_length=4)
    billing_address: G1450BillingAddressWrite
    daytime_phone_number: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=255)


class G1650BankDetailsWrite(BaseModel):
    account_ownership: str = Field(min_length=1, max_length=16)
    account_type: str = Field(min_length=1, max_length=16)
    account_holder_name: str = Field(default="", max_length=160)
    business_name: str = Field(default="", max_length=160)
    bank_name: str = Field(min_length=1, max_length=160)
    routing_number: str = Field(min_length=9, max_length=16)
    account_number: str = Field(min_length=4, max_length=32)


class G1450PaymentOptionRead(BaseModel):
    checklist_code: str
    form_code: str
    label: str
    filing_category: str
    paper_fee: str
    source_url: str
    verified_on: str
    source_edition: str
    is_payable: bool


class G1450PaymentOptionsRead(BaseModel):
    case_id: UUID
    template_pdf: str
    template_exists: bool
    g1650_template_exists: bool
    payment_note: str
    options: list[G1450PaymentOptionRead]


class G1450GenerateRequest(G1450CardDetailsWrite):
    selected_checklist_codes: list[str] | None = None

    @field_validator("selected_checklist_codes")
    @classmethod
    def validate_selected_checklist_codes(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("Select at least one payment form to generate.")
        return cleaned


class G1650GenerateRequest(G1650BankDetailsWrite):
    selected_checklist_codes: list[str] | None = None

    @field_validator("selected_checklist_codes")
    @classmethod
    def validate_selected_checklist_codes(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("Select at least one payment form to generate.")
        return cleaned


class G1450GeneratedPdfRead(BaseModel):
    checklist_code: str | None = None
    form_code: str | None = None
    filing_category: str | None = None
    authorized_amount: str
    generated_pdf: str
    download_url: str


class G1450GenerateResponseRead(BaseModel):
    case_id: UUID
    generated: list[G1450GeneratedPdfRead]
    skipped: list[dict[str, Any]]
    total_authorized_amount: str
    payment_note: str


class CountryGuidanceRead(BaseModel):
    country_code: str
    country_name: str
    overview: str
    translation_note: str
    availability_note: str
    documents: list[dict[str, Any]]
    sources: list[dict[str, Any]]


class ExplanationContentRead(BaseModel):
    issue_severity_help: dict[str, str]
    readiness_labels: dict[str, str]
    disclaimers: list[str]
    escalation_triggers: list[str]


class USCISInitialEvidenceRead(BaseModel):
    checklist_code: str
    label: str
    necessity: str
    requirement_type: str
    notes: str
    conditional_note: str | None = None


class USCISRequirementRead(BaseModel):
    code: str
    label: str
    accepted_edition: str | None = None
    verified_on: str
    official_url: str
    summary: str
    important_notes: list[str]
    fee_url: str | None = None
    related_checklist_codes: list[str] = Field(default_factory=list)
    initial_evidence: list[USCISInitialEvidenceRead] = Field(default_factory=list)


class USCISRequirementsPayloadRead(BaseModel):
    verified_on: str
    general_rules: list[dict[str, Any]]
    forms: list[USCISRequirementRead]


class I485QuestionnaireRead(BaseModel):
    version: str
    verified_on: str
    official_url: str
    official_pdf_url: str
    local_reference_pdf: str
    sources: list[dict[str, Any]]
    pages: list[dict[str, Any]]


class I485PageAnswersWrite(BaseModel):
    page_id: str = Field(min_length=2, max_length=96)
    answers: dict[str, Any] = Field(default_factory=dict)
    manual_flags: dict[str, Any] = Field(default_factory=dict)


class I485IngestionStateRead(BaseModel):
    case_id: UUID
    answers: dict[str, Any]
    answer_sources: dict[str, Any] = Field(default_factory=dict)
    manual_flags: dict[str, Any] = Field(default_factory=dict)
    evaluation: dict[str, Any]
    saved_pages: list[str]


class I485PdfImportRequest(BaseModel):
    upload_id: UUID | None = None
    overwrite: bool = False


class I485PdfImportResponseRead(BaseModel):
    state: I485IngestionStateRead
    proposals: list[dict[str, Any]]
    imported_count: int
    skipped_count: int
    upload_id: UUID


class I485CaseDataImportRequest(BaseModel):
    overwrite: bool = False


class I485CaseDataImportResponseRead(BaseModel):
    state: I485IngestionStateRead
    proposals: list[dict[str, Any]]
    imported_count: int
    skipped_count: int


class I485FormFillPreviewRead(BaseModel):
    case_id: UUID
    generation_status: str
    ready_for_pdf_generation: bool
    questionnaire_version: str
    field_count: int
    missing_required_count: int
    blocking_flag_count: int
    outside_niche_flag_count: int
    low_confidence_count: int
    fields: list[dict[str, Any]]
    missing_required: list[dict[str, Any]]
    blocking_flags: list[dict[str, Any]]
    outside_niche_flags: list[dict[str, Any]]
    low_confidence_fields: list[dict[str, Any]]
    recommendations: list[str]


class I485PdfGenerateRequest(BaseModel):
    template_path: str | None = None
    output_path: str | None = None
    output_dir: str | None = None
    allow_incomplete: bool = True


class I485PdfGenerateResponseRead(BaseModel):
    case_id: UUID
    generated_pdf: str
    download_url: str
    template_pdf: str
    generation_status: str
    ready_for_pdf_generation: bool
    field_count: int
    text_field_count: int
    checkbox_field_count: int
    mapped_question_count: int
    unmapped_answer_count: int
    missing_required_count: int
    blocking_flag_count: int
    outside_niche_flag_count: int
    low_confidence_count: int
    warnings: list[str]
    mapped_questions: list[dict[str, Any]]
    unmapped_answered_questions: list[dict[str, Any]]
    missing_template_fields: list[str]


class FormQuestionnaireRead(BaseModel):
    form_key: str
    form_code: str
    title: str
    version: str
    verified_on: str
    official_url: str
    official_pdf_url: str
    local_template_pdf: str
    sources: list[dict[str, Any]]
    pages: list[dict[str, Any]]


class FormPageAnswersWrite(BaseModel):
    page_id: str = Field(min_length=2, max_length=96)
    answers: dict[str, Any] = Field(default_factory=dict)
    manual_flags: dict[str, Any] = Field(default_factory=dict)


class FormIngestionStateRead(BaseModel):
    case_id: UUID
    form_key: str
    answers: dict[str, Any]
    answer_sources: dict[str, Any] = Field(default_factory=dict)
    manual_flags: dict[str, Any] = Field(default_factory=dict)
    evaluation: dict[str, Any]
    saved_pages: list[str]


class FormCaseDataImportRequest(BaseModel):
    overwrite: bool = False


class FormCaseDataImportResponseRead(BaseModel):
    state: FormIngestionStateRead
    proposals: list[dict[str, Any]]
    imported_count: int
    skipped_count: int


class FormFillPreviewRead(BaseModel):
    case_id: UUID
    form_key: str
    generation_status: str
    ready_for_pdf_generation: bool
    questionnaire_version: str
    field_count: int
    missing_required_count: int
    blocking_flag_count: int
    outside_niche_flag_count: int
    low_confidence_count: int
    fields: list[dict[str, Any]]
    missing_required: list[dict[str, Any]]
    blocking_flags: list[dict[str, Any]]
    outside_niche_flags: list[dict[str, Any]]
    low_confidence_fields: list[dict[str, Any]]
    recommendations: list[str]


class FormPdfGenerateRequest(BaseModel):
    template_path: str | None = None
    output_path: str | None = None
    output_dir: str | None = None
    allow_incomplete: bool = True


class FormPdfGenerateResponseRead(BaseModel):
    case_id: UUID
    form_key: str
    generated_pdf: str
    download_url: str
    template_pdf: str
    generation_status: str
    ready_for_pdf_generation: bool
    field_count: int
    text_field_count: int
    checkbox_field_count: int
    mapped_question_count: int
    unmapped_answer_count: int
    missing_required_count: int
    blocking_flag_count: int
    outside_niche_flag_count: int
    low_confidence_count: int
    warnings: list[str]
    mapped_questions: list[dict[str, Any]]
    unmapped_answered_questions: list[dict[str, Any]]
    missing_template_fields: list[str]


class PacketAssemblyGenerateRequest(BaseModel):
    state_code: str | None = None
    carrier: str = "usps"
    include_upload_ids: list[UUID] | None = None
    include_supporting_evidence: bool = True
    include_generated_forms: bool = True
    allow_incomplete: bool = True
    g1450_payment: G1450CardDetailsWrite | None = None
    g1650_payment: G1650BankDetailsWrite | None = None
    g1450_selected_checklist_codes: list[str] | None = None

    @model_validator(mode="after")
    def validate_single_payment_method(self) -> "PacketAssemblyGenerateRequest":
        if self.g1450_payment is not None and self.g1650_payment is not None:
            raise ValueError("Choose either card (G-1450) or bank account (G-1650) payment for a packet, not both.")
        return self

    @field_validator("g1450_selected_checklist_codes")
    @classmethod
    def validate_g1450_selected_checklist_codes(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("Select at least one payment form to generate.")
        return cleaned


class PacketAssemblyDocumentRead(BaseModel):
    label: str
    source_type: str
    section: str | None = None
    form_key: str | None = None
    checklist_item_code: str | None = None
    upload_id: str | None = None
    filename: str | None = None
    path: str | None = None
    page_count: int


class PacketAssemblySkippedDocumentRead(BaseModel):
    label: str
    source_type: str
    section: str | None = None
    form_key: str | None = None
    checklist_item_code: str | None = None
    upload_id: str | None = None
    filename: str | None = None
    path: str | None = None
    reason: str


class PacketMailingRecommendationRead(BaseModel):
    location_code: str
    location_label: str
    carrier: str
    lockbox: str
    address_lines: list[str]
    usps_address_lines: list[str]
    private_carrier_address_lines: list[str]
    source_url: str
    related_source_urls: list[str]
    source_last_reviewed: str
    verified_on: str
    note: str


class PacketAssemblyResponseRead(BaseModel):
    case_id: UUID
    generated_pdf: str
    download_url: str
    manifest_json: str
    manifest_download_url: str
    total_page_count: int
    included_documents: list[PacketAssemblyDocumentRead]
    skipped_documents: list[PacketAssemblySkippedDocumentRead]
    warnings: list[str]
    mailing_recommendation: PacketMailingRecommendationRead | None = None

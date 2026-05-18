export type ChecklistWorkflowStatus =
  | "not_started"
  | "pending"
  | "in_progress"
  | "uploaded"
  | "almost_done"
  | "approved"
  | "complete"
  | "not_applicable";

export type ChecklistDocumentStatus = "missing" | "requested" | "uploaded" | "confirmed";

export const CHECKLIST_STATUS_OPTIONS: Array<{
  value: ChecklistWorkflowStatus;
  label: string;
}> = [
  { value: "not_started", label: "Not started" },
  { value: "pending", label: "Pending" },
  { value: "in_progress", label: "In progress" },
  { value: "uploaded", label: "Uploaded" },
  { value: "almost_done", label: "Almost done" },
  { value: "approved", label: "Approved" },
  { value: "complete", label: "Complete" },
];

export type CaseSummary = {
  id: string;
  case_name: string;
  workflow_type: string;
  status: string;
  petitioner_email: string | null;
  beneficiary_email: string | null;
  country_of_focus: string | null;
  readiness_score: number;
  readiness_label: string;
  petitioner?: PersonSummary | null;
  beneficiary?: PersonSummary | null;
  marriage?: MarriageSummary | null;
  counts: {
    checklist_items: number;
    uploads: number;
    qa_issues: number;
  };
};

export type PersonSummary = {
  role: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  country_of_birth: string | null;
  country_of_citizenship: string | null;
  location: string | null;
  entered_us_legally: boolean | null;
  current_immigration_status: string | null;
  annual_income: number | null;
  employment_status: string | null;
};

export type MarriageSummary = {
  marriage_date: string | null;
  first_marriage_for_both: boolean | null;
  has_children: boolean | null;
  household_size: number | null;
};

export type IntakeState = {
  case_id: string;
  steps: { step_key: string; payload: Record<string, unknown>; updated_at: string }[];
  merged: Record<string, unknown>;
  missing_fields: string[];
};

export type PrescreenQuestion = {
  id: string;
  label: string;
  answer_type: string;
  section: string;
  db_path?: string | null;
  options: { value: string; label: string }[];
  fields?: PrescreenQuestionField[];
  field_mappings?: Record<string, string>;
  ideal_answer?: unknown;
  flag_when?: unknown;
  flag_code?: string | null;
  flag_title?: string | null;
  flag_description?: string | null;
  flag_category?: string | null;
  flag_severity?: string | null;
  flag_rules?: {
    when: unknown;
    code: string;
    severity?: string;
    category?: string;
    title?: string;
    description?: string;
  }[];
  visible_when: Record<string, unknown>;
  elimination_text?: string | null;
  help_text?: string | null;
  why?: string | null;
  smart_default_sources?: string[];
};

export type PrescreenQuestionField = {
  key: string;
  label: string;
  type: string;
  required?: boolean;
  placeholder?: string;
  options?: { value: string; label: string }[];
};

export type PrescreenQuestionnaire = {
  version: string;
  verified_on: string;
  sources: { label: string; url: string; verified_on: string; notes: string }[];
  questions: PrescreenQuestion[];
};

export type PrescreenFlag = {
  code: string;
  severity: string;
  category: string;
  question_id: string;
  title: string;
  description: string;
};

export type PrescreenEvaluation = {
  version: string;
  verified_on: string;
  sources: PrescreenQuestionnaire["sources"];
  status: string;
  completion_pct: number;
  visible_questions: PrescreenQuestion[];
  eliminated_questions: { question_id: string; label: string; reason: string }[];
  flags: PrescreenFlag[];
  included_forms: string[];
  eliminated_forms: { form_code: string; label: string; reason: string }[];
  next_steps: { label: string; description: string }[];
  generated_at: string;
};

export type PrescreenState = {
  case_id: string;
  answers: Record<string, unknown>;
  answer_sources?: Record<string, string>;
  evaluation: PrescreenEvaluation;
};

export type ChecklistItem = {
  id: string;
  case_id: string;
  code: string;
  category: string;
  label: string;
  applicability: string;
  completion_status: ChecklistWorkflowStatus;
  owner_role: string;
  description: string;
  why_needed: string;
  what_to_save_now: string;
  conditional_reason?: string | null;
  sort_order: number;
  item_metadata: Record<string, unknown>;
};

export type ChecklistResponse = {
  case_id: string;
  facts: Record<string, unknown>;
  items: ChecklistItem[];
};

export type UploadRecord = {
  id: string;
  case_id: string;
  checklist_item_code: string | null;
  original_filename: string;
  stored_filename: string | null;
  mime_type: string | null;
  file_size: number;
  upload_status: string;
  review_status: string;
  ocr_status: string;
  extraction_confidence: number;
  document_type: string | null;
  document_language: string;
  requires_translation: boolean;
  has_translation: boolean;
  version: number;
  extracted_fields: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type UploadRequestResponse = {
  upload_id: string;
  upload_url: string;
  max_upload_size_mb: number;
};

export type QaSummary = {
  score: number;
  label: string;
  explanation: string;
  issue_counts: Record<string, number>;
  required_completion_pct: number;
};

export type QaIssue = {
  id: string;
  severity: string;
  code: string;
  title: string;
  description: string;
  checklist_item_code: string | null;
  is_resolved: boolean;
  created_at: string;
};

export type QaResults = {
  case_id: string;
  summary: QaSummary;
  issues: QaIssue[];
};

export type CountryGuidance = {
  country_code: string;
  country_name: string;
  overview: string;
  translation_note: string;
  availability_note: string;
  documents: {
    code: string;
    label: string;
    common_name: string;
    category: string;
    translation_required: boolean;
    tips: string[];
  }[];
  sources: { label: string; url: string | null }[];
};

export type ExplanationContent = {
  issue_severity_help: Record<string, string>;
  readiness_labels: Record<string, string>;
  disclaimers: string[];
  escalation_triggers: string[];
};

export type UscisRequirement = {
  code: string;
  label: string;
  accepted_edition: string | null;
  verified_on: string;
  official_url: string;
  summary: string;
  important_notes: string[];
  fee_url: string | null;
  related_checklist_codes: string[];
  initial_evidence: {
    checklist_code: string;
    label: string;
    necessity: string;
    requirement_type: string;
    notes: string;
    conditional_note?: string | null;
  }[];
};

export type UscisRequirementsPayload = {
  verified_on: string;
  general_rules: {
    code: string;
    label: string;
    verified_on: string;
    official_url: string;
    summary: string;
    important_notes: string[];
    fee_url: string | null;
  }[];
  forms: UscisRequirement[];
};

export type I485QuestionEntryField = {
  key: string;
  label: string;
  type: string;
  required?: boolean;
  options?: { value: string; label: string }[];
};

export type I485Question = {
  id: string;
  label: string;
  answer_type: string;
  required: boolean;
  pdf_ref: string;
  db_path?: string | null;
  options: { value: string; label: string }[];
  ideal_answer?: unknown;
  risk_when?: unknown;
  risk_code?: string | null;
  help_text?: string | null;
  plain_language?: string | null;
  deep_explanation?: string | null;
  teaching_source?: {
    label: string;
    url: string;
    transcript_path?: string;
    fetched_on: string;
    pdf_ref?: string;
  } | null;
  entry_fields?: I485QuestionEntryField[];
  form_entry_limit?: number | null;
  overflow_pdf_ref?: string | null;
};

export type I485QuestionnairePage = {
  id: string;
  title: string;
  pdf_part: string;
  local_pdf_pages: number[];
  questions: I485Question[];
};

export type I485Questionnaire = {
  version: string;
  verified_on: string;
  official_url: string;
  official_pdf_url: string;
  local_reference_pdf: string;
  sources: { label: string; url: string; verified_on: string; notes: string }[];
  pages: I485QuestionnairePage[];
};

export type I485Flag = {
  code: string;
  severity: string;
  category: string;
  question_id: string;
  title: string;
  description: string;
  pdf_ref: string;
};

export type I485Evaluation = {
  required_questions: number;
  answered_required: number;
  completion_pct: number;
  readiness: string;
  flags: I485Flag[];
  page_summaries: {
    page_number: number;
    page_id: string;
    title: string;
    required_questions: number;
    answered_required: number;
    flags: I485Flag[];
  }[];
  mapped_fields: { question_id: string; db_path: string; pdf_ref: string }[];
};

export type I485IngestionState = {
  case_id: string;
  answers: Record<string, unknown>;
  answer_sources: Record<
    string,
    {
      source_type: string;
      upload_id?: string;
      filename?: string;
      source_field?: string;
      confidence?: number;
      updated_at?: string;
    }
  >;
  manual_flags: Record<string, unknown>;
  evaluation: I485Evaluation;
  saved_pages: string[];
};

export type I485PdfImportResponse = {
  state: I485IngestionState;
  proposals: {
    question_id: string;
    page_id: string;
    label: string;
    value: unknown;
    source_field: string;
    source_upload_id: string;
    source_filename: string;
    confidence: number;
    pdf_ref: string;
  }[];
  imported_count: number;
  skipped_count: number;
  upload_id: string;
};

export type I485CaseDataImportResponse = {
  state: I485IngestionState;
  proposals: {
    question_id: string;
    page_id: string;
    label: string;
    value: unknown;
    source_field: string;
    confidence: number;
    pdf_ref: string;
  }[];
  imported_count: number;
  skipped_count: number;
};

export type I485FormFillPreview = {
  case_id: string;
  generation_status: string;
  ready_for_pdf_generation: boolean;
  questionnaire_version: string;
  field_count: number;
  missing_required_count: number;
  blocking_flag_count: number;
  outside_niche_flag_count: number;
  low_confidence_count: number;
  fields: {
    target_key: string;
    question_id: string;
    page_id: string;
    label: string;
    pdf_ref: string;
    answer_type: string;
    value: unknown;
    source: I485IngestionState["answer_sources"][string] | Record<string, never>;
    needs_review: boolean;
  }[];
  missing_required: {
    question_id: string;
    page_id: string;
    label: string;
    pdf_ref: string;
  }[];
  blocking_flags: I485Flag[];
  outside_niche_flags: I485Flag[];
  low_confidence_fields: {
    target_key: string;
    question_id: string;
    page_id: string;
    label: string;
    pdf_ref: string;
    value: unknown;
  }[];
  recommendations: string[];
};

export type I485PdfGenerateResponse = {
  case_id: string;
  generated_pdf: string;
  download_url: string;
  template_pdf: string;
  generation_status: string;
  ready_for_pdf_generation: boolean;
  field_count: number;
  text_field_count: number;
  checkbox_field_count: number;
  mapped_question_count: number;
  unmapped_answer_count: number;
  missing_required_count: number;
  blocking_flag_count: number;
  outside_niche_flag_count: number;
  low_confidence_count: number;
  warnings: string[];
  mapped_questions: { question_id: string; label: string; pdf_fields: string[] }[];
  unmapped_answered_questions: { question_id: string; label: string; pdf_ref: string }[];
  missing_template_fields: string[];
};

export type FormQuestion = I485Question;

export type FormQuestionnairePage = I485QuestionnairePage;

export type FormQuestionnaire = {
  form_key: string;
  form_code: string;
  title: string;
  version: string;
  verified_on: string;
  official_url: string;
  official_pdf_url: string;
  local_template_pdf: string;
  sources: { label: string; url: string; verified_on: string; notes: string }[];
  pages: FormQuestionnairePage[];
};

export type FormFlag = I485Flag;

export type FormEvaluation = I485Evaluation;

export type FormIngestionState = {
  case_id: string;
  form_key: string;
  answers: Record<string, unknown>;
  answer_sources: I485IngestionState["answer_sources"];
  manual_flags: Record<string, unknown>;
  evaluation: FormEvaluation;
  saved_pages: string[];
};

export type FormImportResponse = {
  state: FormIngestionState;
  proposals: {
    question_id: string;
    page_id: string;
    label: string;
    value: unknown;
    source_field: string;
    confidence: number;
    pdf_ref: string;
  }[];
  imported_count: number;
  skipped_count: number;
};

export type FormFillPreview = Omit<I485FormFillPreview, "case_id"> & {
  case_id: string;
  form_key: string;
};

export type FormPdfGenerateResponse = I485PdfGenerateResponse & {
  form_key: string;
};

export type PacketAssemblyDocument = {
  label: string;
  source_type: string;
  section: string | null;
  form_key: string | null;
  checklist_item_code: string | null;
  upload_id: string | null;
  filename: string | null;
  path: string | null;
  page_count: number;
};

export type PacketAssemblySkippedDocument = Omit<PacketAssemblyDocument, "page_count"> & {
  reason: string;
};

export type PacketMailingRecommendation = {
  location_code: string;
  location_label: string;
  carrier: string;
  lockbox: string;
  address_lines: string[];
  usps_address_lines: string[];
  private_carrier_address_lines: string[];
  source_url: string;
  related_source_urls: string[];
  source_last_reviewed: string;
  verified_on: string;
  note: string;
};

export type PacketAssemblyResponse = {
  case_id: string;
  generated_pdf: string;
  download_url: string;
  manifest_json: string;
  manifest_download_url: string;
  total_page_count: number;
  included_documents: PacketAssemblyDocument[];
  skipped_documents: PacketAssemblySkippedDocument[];
  warnings: string[];
  mailing_recommendation: PacketMailingRecommendation | null;
};

export type FilingValidationIssue = {
  form_code: string;
  severity: string;
  code: string;
  title: string;
  description: string;
  source: string;
  field_key?: string | null;
  question_id?: string | null;
  pdf_ref?: string | null;
  pdf_fields: string[];
  expected: unknown;
  actual: unknown;
};

export type FilingValidationFormResult = {
  form_code: string;
  label: string;
  status: string;
  issue_counts: Record<string, number>;
  field_count: number;
  required_field_count: number;
  missing_required_count: number;
  template_field_count: number;
  template_path?: string | null;
  source: Record<string, unknown>;
  metadata: Record<string, unknown>;
  issues: FilingValidationIssue[];
};

export type FilingValidationResponse = {
  case_id: string;
  generated_at: string;
  validation_scope: string[];
  summary: {
    status: string;
    issue_counts: Record<string, number>;
    form_count: number;
    forms_passed: number;
    blocking_forms: string[];
  };
  assumptions: Record<string, unknown>;
  forms: FilingValidationFormResult[];
  roadmap: Record<string, unknown>[];
};

export type G1450PaymentOption = {
  checklist_code: string;
  form_code: string;
  label: string;
  filing_category: string;
  paper_fee: string;
  source_url: string;
  verified_on: string;
  source_edition: string;
  is_payable: boolean;
};

export type G1450PaymentOptions = {
  case_id: string;
  template_pdf: string;
  template_exists: boolean;
  payment_note: string;
  options: G1450PaymentOption[];
};

export type G1450GeneratePayload = {
  cardholder_name: string;
  credit_card_type: string;
  credit_card_number: string;
  expiration_month: string;
  expiration_year: string;
  security_code: string;
  billing_address: {
    street_1: string;
    street_2: string;
    city: string;
    state: string;
    postal_code: string;
  };
  daytime_phone_number: string;
  email: string;
  selected_checklist_codes: string[];
};

export type G1450GenerateResponse = {
  case_id: string;
  generated: {
    checklist_code: string | null;
    form_code: string | null;
    filing_category: string | null;
    authorized_amount: string;
    generated_pdf: string;
    download_url: string;
  }[];
  skipped: Record<string, unknown>[];
  total_authorized_amount: string;
  payment_note: string;
};

export type IntakeFormValues = {
  petitioner_first_name: string;
  petitioner_middle_name: string;
  petitioner_last_name: string;
  petitioner_date_of_birth: string;
  petitioner_phone: string;
  petitioner_email: string;
  petitioner_current_address: string;
  beneficiary_first_name: string;
  beneficiary_middle_name: string;
  beneficiary_last_name: string;
  beneficiary_date_of_birth: string;
  beneficiary_email: string;
  beneficiary_phone: string;
  beneficiary_a_number: string;
  beneficiary_i94_number: string;
  beneficiary_passport_number: string;
  beneficiary_passport_country: string;
  beneficiary_passport_expiration: string;
  marriage_date: string;
  beneficiary_country_of_birth: string;
  beneficiary_country_of_citizenship: string;
  beneficiary_location: "usa" | "abroad";
  beneficiary_entered_us_legally: boolean;
  beneficiary_current_immigration_status: string;
  beneficiary_current_address: string;
  beneficiary_current_address_since: string;
  beneficiary_prior_address_1: string;
  beneficiary_prior_address_1_from: string;
  beneficiary_prior_address_1_to: string;
  beneficiary_prior_address_2: string;
  beneficiary_prior_address_2_from: string;
  beneficiary_prior_address_2_to: string;
  beneficiary_employment_history: string;
  first_marriage_for_both: boolean;
  wants_i765: boolean;
  wants_i131: boolean;
  needs_translation: boolean;
  household_size: number;
  annual_income: number;
  employment_status: string;
  has_children: boolean;
  has_joint_lease: boolean;
  has_joint_bank_account: boolean;
  has_relationship_photos: boolean;
  has_affidavits: boolean;
  reviewed_current_fees: boolean;
  reviewed_current_form_editions: boolean;
  prior_immigration_denials: boolean;
  criminal_history: boolean;
  removal_history: boolean;
  identity_inconsistencies: boolean;
};

export const DEFAULT_INTAKE_VALUES: IntakeFormValues = {
  petitioner_first_name: "",
  petitioner_middle_name: "",
  petitioner_last_name: "",
  petitioner_date_of_birth: "",
  petitioner_phone: "",
  petitioner_email: "",
  petitioner_current_address: "",
  beneficiary_first_name: "",
  beneficiary_middle_name: "",
  beneficiary_last_name: "",
  beneficiary_date_of_birth: "",
  beneficiary_email: "",
  beneficiary_phone: "",
  beneficiary_a_number: "",
  beneficiary_i94_number: "",
  beneficiary_passport_number: "",
  beneficiary_passport_country: "",
  beneficiary_passport_expiration: "",
  marriage_date: "",
  beneficiary_country_of_birth: "Colombia",
  beneficiary_country_of_citizenship: "Colombia",
  beneficiary_location: "usa",
  beneficiary_entered_us_legally: true,
  beneficiary_current_immigration_status: "B-2 visitor",
  beneficiary_current_address: "",
  beneficiary_current_address_since: "",
  beneficiary_prior_address_1: "",
  beneficiary_prior_address_1_from: "",
  beneficiary_prior_address_1_to: "",
  beneficiary_prior_address_2: "",
  beneficiary_prior_address_2_from: "",
  beneficiary_prior_address_2_to: "",
  beneficiary_employment_history: "",
  first_marriage_for_both: true,
  wants_i765: true,
  wants_i131: false,
  needs_translation: true,
  household_size: 2,
  annual_income: 0,
  employment_status: "employed",
  has_children: false,
  has_joint_lease: true,
  has_joint_bank_account: false,
  has_relationship_photos: true,
  has_affidavits: false,
  reviewed_current_fees: false,
  reviewed_current_form_editions: false,
  prior_immigration_denials: false,
  criminal_history: false,
  removal_history: false,
  identity_inconsistencies: false,
};

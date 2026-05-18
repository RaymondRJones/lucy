import type {
  CaseSummary,
  ChecklistResponse,
  CountryGuidance,
  ExplanationContent,
  FormFillPreview,
  FormImportResponse,
  FormIngestionState,
  FormPdfGenerateResponse,
  FormQuestionnaire,
  FilingValidationResponse,
  G1450GeneratePayload,
  G1450GenerateResponse,
  G1450PaymentOptions,
  I485CaseDataImportResponse,
  I485IngestionState,
  I485FormFillPreview,
  I485PdfGenerateResponse,
  I485PdfImportResponse,
  I485Questionnaire,
  IntakeState,
  PacketAssemblyResponse,
  PrescreenQuestionnaire,
  PrescreenState,
  QaResults,
  UploadRecord,
  UploadRequestResponse,
  UscisRequirementsPayload,
} from "./types";

const STATIC_API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const API_PORT = process.env.NEXT_PUBLIC_API_PORT ?? "8000";

function apiBaseUrl() {
  if (STATIC_API_BASE_URL === "__LAN__" && typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:${API_PORT}`;
  }
  return STATIC_API_BASE_URL;
}

export function apiUrl(path: string) {
  return `${apiBaseUrl()}${path}`;
}

function formatFieldPath(location: unknown) {
  if (!Array.isArray(location)) {
    return "field";
  }
  return location
    .filter((part) => part !== "body")
    .map((part) => String(part).replaceAll("_", " "))
    .join(" ");
}

function apiErrorMessage(payload: unknown) {
  const detail = payload && typeof payload === "object" && "detail" in payload ? payload.detail : undefined;
  if (typeof detail === "string") {
    return detail;
  }
  if (detail && typeof detail === "object" && !Array.isArray(detail) && "message" in detail) {
    return String(detail.message);
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((issue) => {
        if (!issue || typeof issue !== "object") {
          return null;
        }
        const location = "loc" in issue ? formatFieldPath(issue.loc) : "field";
        const message = "msg" in issue ? String(issue.msg) : "Invalid value";
        return `${location}: ${message}`;
      })
      .filter((value): value is string => Boolean(value));
    if (messages.length) {
      return messages.slice(0, 4).join("; ") + (messages.length > 4 ? `; plus ${messages.length - 4} more` : "");
    }
  }
  return "Something went wrong while talking to the API.";
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(payload));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function createCase(payload: {
  case_name: string;
  petitioner_email?: string;
  beneficiary_email?: string;
  country_of_focus?: string;
}) {
  return apiFetch<CaseSummary>("/api/v1/cases", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listCases() {
  return apiFetch<CaseSummary[]>("/api/v1/cases");
}

export function getCase(caseId: string) {
  return apiFetch<CaseSummary>(`/api/v1/cases/${caseId}`);
}

export function saveIntake(caseId: string, payload: Record<string, unknown>) {
  return apiFetch<IntakeState>(`/api/v1/cases/${caseId}/intake/step`, {
    method: "POST",
    body: JSON.stringify({
      step_key: "baseline",
      payload,
    }),
  });
}

export function getIntake(caseId: string) {
  return apiFetch<IntakeState>(`/api/v1/cases/${caseId}/intake`);
}

export function getPrescreenQuestionnaire() {
  return apiFetch<PrescreenQuestionnaire>("/api/v1/content/prescreen");
}

export function getPrescreenState(caseId: string) {
  return apiFetch<PrescreenState>(`/api/v1/cases/${caseId}/prescreen`);
}

export function savePrescreenAnswers(caseId: string, answers: Record<string, unknown>) {
  return apiFetch<PrescreenState>(`/api/v1/cases/${caseId}/prescreen`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
}

export function submitIntake(caseId: string) {
  return apiFetch<{ facts: Record<string, unknown>; generated_items: number; status: string }>(
    `/api/v1/cases/${caseId}/intake/submit`,
    {
      method: "POST",
    },
  );
}

export function generateChecklist(caseId: string) {
  return apiFetch<ChecklistResponse>(`/api/v1/cases/${caseId}/checklist/generate`, {
    method: "POST",
  });
}

export function getChecklist(caseId: string) {
  return apiFetch<ChecklistResponse>(`/api/v1/cases/${caseId}/checklist`);
}

export function updateChecklistItem(itemId: string, completionStatus: string) {
  return apiFetch(`/api/v1/checklist-items/${itemId}`, {
    method: "PATCH",
    body: JSON.stringify({
      completion_status: completionStatus,
    }),
  });
}

export function requestUpload(
  caseId: string,
  payload: {
    checklist_item_code: string;
    original_filename: string;
    mime_type: string;
    document_language: string;
    has_translation: boolean;
    extracted_fields?: Record<string, unknown>;
  },
) {
  return apiFetch<UploadRequestResponse>(`/api/v1/cases/${caseId}/uploads/request`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function uploadBinary(uploadUrl: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${apiBaseUrl()}${uploadUrl}`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload?.detail || "Binary upload failed.");
  }
  return response.json();
}

export function confirmUpload(
  uploadId: string,
  payload: {
    document_type: string;
    document_language: string;
    has_translation: boolean;
    extracted_fields?: Record<string, unknown>;
    extraction_confidence?: number;
  },
) {
  return apiFetch<UploadRecord>(`/api/v1/uploads/${uploadId}/confirm`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listUploads(caseId: string) {
  return apiFetch<UploadRecord[]>(`/api/v1/cases/${caseId}/uploads`);
}

export function deleteUpload(uploadId: string) {
  return apiFetch<void>(`/api/v1/uploads/${uploadId}`, {
    method: "DELETE",
  });
}

export function runQa(caseId: string) {
  return apiFetch<QaResults>(`/api/v1/cases/${caseId}/qa/run`, {
    method: "POST",
  });
}

export function getQa(caseId: string) {
  return apiFetch<QaResults>(`/api/v1/cases/${caseId}/qa`);
}

export function runFilingValidation(caseId: string, formCodes?: string[]) {
  return apiFetch<FilingValidationResponse>(`/api/v1/cases/${caseId}/filing-validation`, {
    method: "POST",
    body: JSON.stringify(formCodes?.length ? { form_codes: formCodes } : {}),
  });
}

export function getG1450PaymentOptions(caseId: string) {
  return apiFetch<G1450PaymentOptions>(`/api/v1/cases/${caseId}/g1450/payment-options`);
}

export function generateG1450PaymentForms(caseId: string, payload: G1450GeneratePayload) {
  return apiFetch<G1450GenerateResponse>(`/api/v1/cases/${caseId}/g1450/generate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getCountryGuidance(countryCode: string) {
  return apiFetch<CountryGuidance>(`/api/v1/content/countries/${countryCode}`);
}

export function getExplanations() {
  return apiFetch<ExplanationContent>("/api/v1/content/explanations");
}

export function getUscisRequirements() {
  return apiFetch<UscisRequirementsPayload>("/api/v1/content/uscis-requirements");
}

export function getI485Questionnaire() {
  return apiFetch<I485Questionnaire>("/api/v1/content/i485-questionnaire");
}

export function getI485IngestionState(caseId: string) {
  return apiFetch<I485IngestionState>(`/api/v1/cases/${caseId}/i485-ingestion`);
}

export function saveI485Page(
  caseId: string,
  pageId: string,
  answers: Record<string, unknown>,
  manualFlags?: Record<string, unknown>,
) {
  return apiFetch<I485IngestionState>(`/api/v1/cases/${caseId}/i485-ingestion/page`, {
    method: "POST",
    body: JSON.stringify({
      page_id: pageId,
      answers,
      manual_flags: manualFlags ?? {},
    }),
  });
}

export function importI485FromUpload(caseId: string, payload?: { upload_id?: string; overwrite?: boolean }) {
  return apiFetch<I485PdfImportResponse>(`/api/v1/cases/${caseId}/i485-ingestion/import-from-upload`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export function importI485FromCaseData(caseId: string, payload?: { overwrite?: boolean }) {
  return apiFetch<I485CaseDataImportResponse>(`/api/v1/cases/${caseId}/i485-ingestion/import-from-case`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export function getI485FormFillPreview(caseId: string) {
  return apiFetch<I485FormFillPreview>(`/api/v1/cases/${caseId}/i485-ingestion/form-fill-preview`);
}

export function generateI485Pdf(caseId: string, payload?: { allow_incomplete?: boolean }) {
  return apiFetch<I485PdfGenerateResponse>(`/api/v1/cases/${caseId}/i485-ingestion/generate-pdf`, {
    method: "POST",
    body: JSON.stringify(payload ?? { allow_incomplete: true }),
  });
}

export function getFormQuestionnaire(formKey: string) {
  return apiFetch<FormQuestionnaire>(`/api/v1/content/forms/${formKey}/questionnaire`);
}

export function getFormIngestionState(caseId: string, formKey: string) {
  return apiFetch<FormIngestionState>(`/api/v1/cases/${caseId}/forms/${formKey}/ingestion`);
}

export function saveFormPage(
  caseId: string,
  formKey: string,
  pageId: string,
  answers: Record<string, unknown>,
  manualFlags?: Record<string, unknown>,
) {
  return apiFetch<FormIngestionState>(`/api/v1/cases/${caseId}/forms/${formKey}/ingestion/page`, {
    method: "POST",
    body: JSON.stringify({
      page_id: pageId,
      answers,
      manual_flags: manualFlags ?? {},
    }),
  });
}

export function importFormFromCaseData(caseId: string, formKey: string, payload?: { overwrite?: boolean }) {
  return apiFetch<FormImportResponse>(`/api/v1/cases/${caseId}/forms/${formKey}/ingestion/import-from-case`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export function getFormFillPreview(caseId: string, formKey: string) {
  return apiFetch<FormFillPreview>(`/api/v1/cases/${caseId}/forms/${formKey}/ingestion/form-fill-preview`);
}

export function generateFormPdf(caseId: string, formKey: string, payload?: { allow_incomplete?: boolean }) {
  return apiFetch<FormPdfGenerateResponse>(`/api/v1/cases/${caseId}/forms/${formKey}/ingestion/generate-pdf`, {
    method: "POST",
    body: JSON.stringify(payload ?? { allow_incomplete: true }),
  });
}

export function generatePacketAssembly(
  caseId: string,
  payload: {
    state_code?: string | null;
    carrier?: "usps" | "private";
    include_upload_ids?: string[] | null;
    include_supporting_evidence?: boolean;
    include_generated_forms?: boolean;
    allow_incomplete?: boolean;
    g1450_payment?: Omit<G1450GeneratePayload, "selected_checklist_codes">;
    g1450_selected_checklist_codes?: string[] | null;
  },
) {
  return apiFetch<PacketAssemblyResponse>(`/api/v1/cases/${caseId}/packet-assembly/generate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

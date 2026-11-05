import type { ChecklistItem, UploadRecord } from "@/lib/types";

// Lucy generates these forms, so an upload is never needed for them.
export const GENERATED_ONLY_UPLOAD_CODES = new Set([
  "form_g1145",
  "form_i130",
  "form_i130a",
  "form_i485",
  "form_i864",
  "form_i765",
  "form_i131",
]);

// Checklist statuses that mean the user has marked an item done.
export const DONE_STATUSES = new Set(["uploaded", "almost_done", "approved", "complete"]);

// The payment row is filled from the Payment section, so it is not counted as evidence.
export const NOT_EVIDENCE_CODES = new Set(["payment_g1450"]);

export function getSatisfiedChecklistCodes(upload: UploadRecord) {
  const extraCodes = Array.isArray(upload.extracted_fields.satisfies_checklist_codes)
    ? upload.extracted_fields.satisfies_checklist_codes.filter((value): value is string => typeof value === "string" && value.length > 0)
    : [];
  return Array.from(new Set([...(upload.checklist_item_code ? [upload.checklist_item_code] : []), ...extraCodes]));
}

export function isEvidenceItem(item: ChecklistItem) {
  return (
    item.applicability !== "not_applicable" &&
    !item.code.startsWith("review_") &&
    !GENERATED_ONLY_UPLOAD_CODES.has(item.code) &&
    !NOT_EVIDENCE_CODES.has(item.code)
  );
}

// Which evidence items have at least one uploaded PDF. This counts files, not checklist ticks.
export function evidenceAttachment(items: ChecklistItem[], uploads: UploadRecord[]) {
  const attachedCodes = new Set(uploads.flatMap(getSatisfiedChecklistCodes));
  const evidence = items.filter(isEvidenceItem);
  return {
    attached: evidence.filter((item) => attachedCodes.has(item.code)),
    missing: evidence.filter((item) => !attachedCodes.has(item.code)),
  };
}

const CASE_STORAGE_KEY = "lucy-case-id";
const LEGACY_CASE_STORAGE_KEY = "green-card-packet-case-id";

export function getSavedCaseId() {
  const savedCaseId = window.localStorage.getItem(CASE_STORAGE_KEY);
  if (savedCaseId) {
    return savedCaseId;
  }
  const legacyCaseId = window.localStorage.getItem(LEGACY_CASE_STORAGE_KEY);
  if (legacyCaseId) {
    window.localStorage.setItem(CASE_STORAGE_KEY, legacyCaseId);
  }
  return legacyCaseId;
}

export function rememberCaseId(caseId: string) {
  window.localStorage.setItem(CASE_STORAGE_KEY, caseId);
}

export function clearSavedCaseId() {
  window.localStorage.removeItem(CASE_STORAGE_KEY);
  window.localStorage.removeItem(LEGACY_CASE_STORAGE_KEY);
}

"use client";

import { useEffect, useMemo, useState } from "react";

import { listCases } from "@/lib/api";
import type { CaseSummary } from "@/lib/types";

const SHORT_ID_LENGTH = 8;

function compactName(...parts: Array<string | null | undefined>) {
  return parts.map((part) => part?.trim()).filter(Boolean).join(" ");
}

function casePersonLabel(caseSummary: CaseSummary) {
  const beneficiaryName = compactName(caseSummary.beneficiary?.first_name, caseSummary.beneficiary?.last_name);
  const petitionerName = compactName(caseSummary.petitioner?.first_name, caseSummary.petitioner?.last_name);
  const firstNames = compactName(caseSummary.beneficiary?.first_name, caseSummary.petitioner?.first_name);

  if (beneficiaryName && petitionerName) {
    return `${beneficiaryName} + ${petitionerName}`;
  }
  if (firstNames) {
    return firstNames;
  }
  return caseSummary.case_name;
}

export function formatCaseSelectLabel(caseSummary: CaseSummary) {
  const personLabel = casePersonLabel(caseSummary);
  const context = [
    caseSummary.country_of_focus,
    caseSummary.readiness_label && caseSummary.readiness_label !== "Not started"
      ? caseSummary.readiness_label
      : null,
  ]
    .filter(Boolean)
    .join(" · ");
  const shortId = caseSummary.id.slice(0, SHORT_ID_LENGTH);

  return [personLabel, context, shortId].filter(Boolean).join(" · ");
}

export function CaseSelector({
  selectedCaseId,
  onSelect,
  disabled = false,
  label = "Saved cases",
  emptyLabel = "No saved cases found",
}: {
  selectedCaseId: string;
  onSelect: (caseSummary: CaseSummary) => void;
  disabled?: boolean;
  label?: string;
  emptyLabel?: string;
}) {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    listCases()
      .then((payload) => {
        if (!cancelled) {
          setCases(payload);
          setErrorMessage(null);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : "Could not load saved cases.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const selectedValue = useMemo(() => {
    return cases.some((caseSummary) => caseSummary.id === selectedCaseId) ? selectedCaseId : "";
  }, [cases, selectedCaseId]);

  function handleSelect(caseId: string) {
    const selectedCase = cases.find((caseSummary) => caseSummary.id === caseId);
    if (selectedCase) {
      onSelect(selectedCase);
    }
  }

  return (
    <label className="block">
      <span className="text-sm font-semibold">{label}</span>
      <select
        value={selectedValue}
        onChange={(event) => handleSelect(event.target.value)}
        disabled={disabled || isLoading || !cases.length}
        className="mt-2 h-11 w-full rounded-lg border border-ink/15 bg-white px-3 text-sm text-ink disabled:opacity-55"
      >
        <option value="">{isLoading ? "Loading cases..." : cases.length ? "Choose a case" : emptyLabel}</option>
        {cases.map((caseSummary) => (
          <option key={caseSummary.id} value={caseSummary.id}>
            {formatCaseSelectLabel(caseSummary)}
          </option>
        ))}
      </select>
      {errorMessage ? <span className="mt-2 block text-xs text-red-700">{errorMessage}</span> : null}
    </label>
  );
}

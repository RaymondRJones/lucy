"use client";

import { useEffect, useMemo, useState } from "react";

import { inputClass, labelClass } from "@/components/ui";
import { listCases } from "@/lib/api";
import type { CaseSummary } from "@/lib/types";

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

function displayCountry(value: string | null) {
  if (!value) {
    return null;
  }
  if (/^[A-Z]{2}$/.test(value)) {
    try {
      return new Intl.DisplayNames(["en"], { type: "region" }).of(value) ?? value;
    } catch {
      return value;
    }
  }
  if (value === value.toUpperCase()) {
    return value.toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
  }
  return value;
}

export function formatCaseSelectLabel(caseSummary: CaseSummary) {
  const personLabel = casePersonLabel(caseSummary);
  const context = [
    displayCountry(caseSummary.country_of_focus),
    caseSummary.readiness_label && caseSummary.readiness_label !== "Not started"
      ? caseSummary.readiness_label
      : null,
  ]
    .filter(Boolean)
    .join(" \u00b7 ");
  return [personLabel, context].filter(Boolean).join(" \u00b7 ");
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
    <label className="grid gap-1.5">
      <span className={labelClass}>{label}</span>
      <select
        value={selectedValue}
        onChange={(event) => handleSelect(event.target.value)}
        disabled={disabled || isLoading || !cases.length}
        className={inputClass}
      >
        <option value="">{isLoading ? "Loading cases..." : cases.length ? "Choose a case" : emptyLabel}</option>
        {cases.map((caseSummary) => (
          <option key={caseSummary.id} value={caseSummary.id}>
            {formatCaseSelectLabel(caseSummary)}
          </option>
        ))}
      </select>
      {errorMessage ? <span role="alert" className="text-xs text-red-800">
          Could not load saved cases. Check that the Lucy API is running. ({errorMessage})
        </span> : null}
    </label>
  );
}

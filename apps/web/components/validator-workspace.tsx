"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState, useTransition } from "react";

import { getCase, getUscisRequirements, listCases, listUploads, runFilingValidation } from "@/lib/api";
import { getSavedCaseId, rememberCaseId } from "@/lib/case-storage";
import type {
  CaseSummary,
  FilingValidationResponse,
  UploadRecord,
  UscisRequirementsPayload,
} from "@/lib/types";

const FORM_OPTIONS = [
  { code: "form_i485", label: "I-485" },
  { code: "form_i765", label: "I-765" },
  { code: "form_i131", label: "I-131" },
  { code: "form_i864", label: "I-864" },
  { code: "form_i130", label: "I-130" },
  { code: "form_i130a", label: "I-130A" },
  { code: "form_g1145", label: "G-1145" },
];

function classNames(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

function formatStatus(value: string) {
  return value.replaceAll("_", " ");
}

function issueTone(severity: string) {
  if (severity === "blocking") {
    return "border-red-200 bg-red-50 text-red-950";
  }
  if (severity === "important") {
    return "border-amber-200 bg-amber-50 text-amber-950";
  }
  return "border-ink/10 bg-white text-ink";
}

function getSatisfiedChecklistCodes(upload: UploadRecord) {
  const extraCodes = Array.isArray(upload.extracted_fields.satisfies_checklist_codes)
    ? upload.extracted_fields.satisfies_checklist_codes
        .filter((value): value is string => typeof value === "string" && value.length > 0)
    : [];
  return Array.from(
    new Set([...(upload.checklist_item_code ? [upload.checklist_item_code] : []), ...extraCodes]),
  );
}

export function ValidatorWorkspace() {
  const [caseSummary, setCaseSummary] = useState<CaseSummary | null>(null);
  const [caseIdInput, setCaseIdInput] = useState("");
  const [knownCases, setKnownCases] = useState<CaseSummary[]>([]);
  const [uploads, setUploads] = useState<UploadRecord[]>([]);
  const [requirements, setRequirements] = useState<UscisRequirementsPayload | null>(null);
  const [selectedForm, setSelectedForm] = useState(FORM_OPTIONS[0].code);
  const [result, setResult] = useState<FilingValidationResponse | null>(null);
  const [message, setMessage] = useState("Loading the current case.");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    let cancelled = false;

    async function loadInitialState() {
      const searchParams = new URLSearchParams(window.location.search);
      const explicitCaseId = searchParams.get("caseId");
      const savedCaseId = explicitCaseId || getSavedCaseId();

      try {
        const [cases, loadedRequirements] = await Promise.all([listCases(), getUscisRequirements()]);
        const activeCase = savedCaseId ? cases.find((entry) => entry.id === savedCaseId) || null : null;
        if (cancelled) {
          return;
        }
        setKnownCases(cases);
        setRequirements(loadedRequirements);
        setCaseSummary(activeCase ?? null);
        setCaseIdInput(savedCaseId ?? "");
        if (activeCase) {
          const loadedUploads = await listUploads(activeCase.id).catch(() => []);
          if (cancelled) {
            return;
          }
          setUploads(loadedUploads);
          setMessage("Choose a form and run validation.");
        } else {
          setMessage("Paste current case case ID or choose a case below before validating.");
        }
      } catch (error) {
        if (!cancelled) {
          setMessage(error instanceof Error ? error.message : "Could not load case list.");
        }
      }
    }

    void loadInitialState();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedLabel = useMemo(
    () => FORM_OPTIONS.find((option) => option.code === selectedForm)?.label ?? selectedForm,
    [selectedForm],
  );
  const caseQuery = caseSummary ? `?caseId=${encodeURIComponent(caseSummary.id)}` : "";

  const filteredCases = useMemo(() => {
    const query = caseIdInput.trim().toLowerCase();
    if (!query) {
      return knownCases.slice(0, 6);
    }
    return knownCases
      .filter((entry) => {
        const haystack = [entry.id, entry.case_name, entry.petitioner_email, entry.beneficiary_email]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return haystack.includes(query);
      })
      .slice(0, 6);
  }, [caseIdInput, knownCases]);

  const selectedRequirement = useMemo(
    () => requirements?.forms.find((form) => form.code === selectedForm) ?? null,
    [requirements, selectedForm],
  );

  const selectedChecklistCodes = useMemo(() => {
    const codes = new Set<string>(selectedRequirement?.related_checklist_codes ?? []);
    for (const evidence of selectedRequirement?.initial_evidence ?? []) {
      codes.add(evidence.checklist_code);
    }
    return codes;
  }, [selectedRequirement]);

  const selectedFormUploads = useMemo(() => {
    if (!selectedChecklistCodes.size) {
      return [];
    }
    return uploads.filter((upload) =>
      getSatisfiedChecklistCodes(upload).some((code) => selectedChecklistCodes.has(code)),
    );
  }, [selectedChecklistCodes, uploads]);

  function setActiveCase(nextCase: CaseSummary, nextUploads: UploadRecord[]) {
    setCaseSummary(nextCase);
    setCaseIdInput(nextCase.id);
    setUploads(nextUploads);
    setResult(null);
    rememberCaseId(nextCase.id);
    const url = new URL(window.location.href);
    url.searchParams.set("caseId", nextCase.id);
    window.history.replaceState({}, "", url);
    setMessage(`Loaded ${nextCase.case_name}. Validation and ingestion pages will use this case ID.`);
  }

  function loadCaseById(caseId: string) {
    const trimmedCaseId = caseId.trim();
    if (!trimmedCaseId) {
      setMessage("Paste a case ID first.");
      return;
    }

    startTransition(() => {
      Promise.all([getCase(trimmedCaseId), listUploads(trimmedCaseId).catch(() => [])])
        .then(([loadedCase, loadedUploads]) => {
          setActiveCase(loadedCase, loadedUploads);
        })
        .catch((error) => {
          setMessage(error instanceof Error ? error.message : "Could not load that case ID.");
        });
    });
  }

  function handleCaseSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    loadCaseById(caseIdInput);
  }

  function runValidation(formCodes?: string[]) {
    if (!caseSummary) {
      setMessage("Open or create a case before validating packet forms.");
      return;
    }

    startTransition(() => {
      runFilingValidation(caseSummary.id, formCodes)
        .then((payload) => {
          setResult(payload);
          setMessage(`Validation finished for ${payload.validation_scope.length} form area(s).`);
        })
        .catch((error) => {
          setMessage(error instanceof Error ? error.message : "Could not run filing validation.");
        });
    });
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 py-6 text-ink md:px-8 md:py-8">
      <nav className="flex flex-col gap-3 border-b border-ink/10 pb-5 md:flex-row md:items-center md:justify-between">
        <Link href="/landing" className="font-display text-2xl">
          Lucy
        </Link>
        <div className="flex flex-wrap gap-2">
          <Link className="rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm font-semibold" href="/">
            Current case
          </Link>
          <Link className="rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm font-semibold" href={`/prescreen${caseQuery}`}>
            Prescreen
          </Link>
          <Link className="rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm font-semibold" href={`/manage-tasks${caseQuery}`}>
            Manage tasks
          </Link>
          <Link className="rounded-lg border border-pine bg-pine px-3 py-2 text-sm font-semibold text-white" href={`/packet-assembly${caseQuery}`}>
            Generate full packet
          </Link>
        </div>
      </nav>

      <section className="grid gap-5 border-b border-ink/10 py-6 lg:grid-cols-[1fr_auto] lg:items-end">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-pine">Validate packet</p>
          <h1 className="mt-3 font-display text-4xl leading-tight md:text-5xl">
            Check one document area at a time.
          </h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-ink/70">
            Validation uses the backend filing preflight for missing required fields, cross-form conflicts,
            source-backed form metadata, and blank-PDF coverage where the MVP supports it.
          </p>
        </div>
        <div className="rounded-lg border border-ink/10 bg-white px-4 py-3 text-sm">
          <p className="text-xs uppercase tracking-[0.16em] text-ink/50">Current case</p>
          <p className="mt-1 font-semibold">{caseSummary?.case_name ?? "None loaded"}</p>
          {caseSummary ? <p className="mt-1 max-w-80 break-all text-xs text-ink/55">{caseSummary.id}</p> : null}
        </div>
      </section>

      <section className="rounded-lg border border-ink/10 bg-white p-5">
        <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
          <form onSubmit={handleCaseSearch}>
            <h2 className="text-lg font-semibold">Load current case case</h2>
            <p className="mt-2 text-sm leading-6 text-ink/65">
              Paste the case ID here to make validation use that case. This also saves the case ID in this
              browser so the ingestion pages pull from the same workspace.
            </p>
            <div className="mt-4 flex flex-col gap-2 sm:flex-row">
              <input
                value={caseIdInput}
                onChange={(event) => setCaseIdInput(event.target.value)}
                placeholder="Paste case ID"
                className="min-h-11 flex-1 rounded-lg border border-ink/15 bg-white px-3 text-sm text-ink"
              />
              <button
                type="submit"
                disabled={isPending}
                className="rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-white disabled:opacity-55"
              >
                {isPending ? "Loading..." : "Use this case"}
              </button>
            </div>
          </form>

          <div>
            <h2 className="text-lg font-semibold">Matching cases</h2>
            <div className="mt-4 grid gap-2">
              {filteredCases.length ? (
                filteredCases.map((entry) => (
                  <button
                    key={entry.id}
                    type="button"
                    onClick={() => loadCaseById(entry.id)}
                    className={classNames(
                      "rounded-lg border px-3 py-3 text-left text-sm transition hover:border-pine/40",
                      caseSummary?.id === entry.id ? "border-pine bg-mist" : "border-ink/10 bg-paper/55",
                    )}
                  >
                    <span className="block font-semibold">{entry.case_name}</span>
                    <span className="mt-1 block break-all text-xs text-ink/55">{entry.id}</span>
                  </button>
                ))
              ) : (
                <p className="rounded-lg border border-ink/10 bg-paper/55 p-3 text-sm text-ink/65">
                  No cases match the text currently in the case ID field.
                </p>
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-ink/10 bg-white p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="text-lg font-semibold">Select a form</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {FORM_OPTIONS.map((option) => (
                <button
                  key={option.code}
                  type="button"
                  onClick={() => setSelectedForm(option.code)}
                  className={classNames(
                    "rounded-lg border px-4 py-2 text-sm font-semibold",
                    selectedForm === option.code
                      ? "border-ink bg-ink text-white"
                      : "border-ink/15 bg-white text-ink",
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => runValidation([selectedForm])}
              disabled={!caseSummary || isPending}
              className="rounded-lg bg-pine px-4 py-2 text-sm font-semibold text-white disabled:opacity-55"
            >
              {isPending ? "Checking..." : `Validate ${selectedLabel}`}
            </button>
            <button
              type="button"
              onClick={() => runValidation(FORM_OPTIONS.map((option) => option.code))}
              disabled={!caseSummary || isPending}
              className="rounded-lg border border-ink/15 bg-white px-4 py-2 text-sm font-semibold disabled:opacity-55"
            >
              Validate all
            </button>
          </div>
        </div>
        <p className="mt-4 rounded-lg border border-ink/10 bg-paper/65 px-4 py-3 text-sm text-ink/70">{message}</p>
      </section>

      <section className="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
        <div className="rounded-lg border border-ink/10 bg-white p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-pine">Selected form files</p>
              <h2 className="mt-1 text-lg font-semibold">{selectedLabel}</h2>
            </div>
            <span className="rounded-full bg-paper px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em]">
              {selectedFormUploads.length} linked
            </span>
          </div>
          <div className="mt-4 grid gap-2">
            {selectedFormUploads.length ? (
              selectedFormUploads.map((upload) => (
                <div key={upload.id} className="rounded-lg border border-ink/10 bg-paper/55 p-3 text-sm">
                  <p className="font-semibold">{upload.original_filename}</p>
                  <p className="mt-1 text-xs text-ink/55">
                    {getSatisfiedChecklistCodes(upload).join(", ") || "No checklist code"} · {upload.upload_status}
                  </p>
                </div>
              ))
            ) : (
              <p className="rounded-lg border border-ink/10 bg-paper/55 p-3 text-sm leading-6 text-ink/65">
                No uploaded files are linked to {selectedLabel} checklist codes yet. Validation can still check
                saved case data and form answers, but no filenames are tied to this form area.
              </p>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-ink/10 bg-white p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-pine">All uploaded files for this case</p>
              <h2 className="mt-1 text-lg font-semibold">{caseSummary?.case_name ?? "No case loaded"}</h2>
            </div>
            <span className="rounded-full bg-paper px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em]">
              {uploads.length} total
            </span>
          </div>
          <div className="mt-4 grid gap-2">
            {uploads.length ? (
              uploads.map((upload) => (
                <div key={upload.id} className="rounded-lg border border-ink/10 bg-paper/55 p-3 text-sm">
                  <p className="font-semibold">{upload.original_filename}</p>
                  <p className="mt-1 text-xs text-ink/55">
                    {upload.document_type || "supporting document"} · {upload.document_language} ·{" "}
                    {upload.review_status}
                  </p>
                </div>
              ))
            ) : (
              <p className="rounded-lg border border-ink/10 bg-paper/55 p-3 text-sm leading-6 text-ink/65">
                No uploads were found for the currently selected case.
              </p>
            )}
          </div>
        </div>
      </section>

      {result ? (
        <>
          <section className="grid gap-3 rounded-lg border border-ink/10 bg-white p-5 md:grid-cols-4">
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-ink/50">Status</p>
              <p className="mt-2 text-2xl font-semibold capitalize">{formatStatus(result.summary.status)}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-ink/50">Forms passed</p>
              <p className="mt-2 text-2xl font-semibold">
                {result.summary.forms_passed}/{result.summary.form_count}
              </p>
            </div>
            {["blocking", "important"].map((severity) => (
              <div key={severity}>
                <p className="text-xs uppercase tracking-[0.16em] text-ink/50">{severity}</p>
                <p className="mt-2 text-2xl font-semibold">{result.summary.issue_counts[severity] ?? 0}</p>
              </div>
            ))}
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            {result.forms.map((form) => (
              <div key={form.form_code} className="rounded-lg border border-ink/10 bg-white p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.16em] text-pine">{form.form_code}</p>
                    <h2 className="mt-1 text-lg font-semibold">{form.label}</h2>
                  </div>
                  <span className="rounded-full bg-paper px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em]">
                    {formatStatus(form.status)}
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
                  <div className="rounded-lg bg-paper/65 p-3">
                    <p className="text-xs uppercase tracking-[0.14em] text-ink/50">Missing</p>
                    <p className="mt-1 font-semibold">{form.missing_required_count}</p>
                  </div>
                  <div className="rounded-lg bg-paper/65 p-3">
                    <p className="text-xs uppercase tracking-[0.14em] text-ink/50">Fields</p>
                    <p className="mt-1 font-semibold">{form.field_count}</p>
                  </div>
                  <div className="rounded-lg bg-paper/65 p-3">
                    <p className="text-xs uppercase tracking-[0.14em] text-ink/50">PDF fields</p>
                    <p className="mt-1 font-semibold">{form.template_field_count}</p>
                  </div>
                </div>
                <div className="mt-4 grid gap-2">
                  {form.issues.length ? (
                    form.issues.slice(0, 6).map((issue) => (
                      <div
                        key={`${issue.form_code}-${issue.code}-${issue.field_key ?? issue.question_id ?? issue.title}`}
                        className={classNames("rounded-lg border p-3 text-sm", issueTone(issue.severity))}
                      >
                        <p className="font-semibold">{issue.title}</p>
                        <p className="mt-1 leading-6">{issue.description}</p>
                        {issue.pdf_ref ? <p className="mt-1 text-xs opacity-75">{issue.pdf_ref}</p> : null}
                      </div>
                    ))
                  ) : (
                    <p className="rounded-lg border border-pine/20 bg-mist p-3 text-sm text-pine">
                      No issues returned for this validation pass.
                    </p>
                  )}
                </div>
              </div>
            ))}
          </section>
        </>
      ) : null}
    </main>
  );
}

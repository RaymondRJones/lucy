"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

import { CaseSelector } from "@/components/case-selector";
import { Badge, cx } from "@/components/ui";
import { getCase, getChecklist, getPrescreenState, listUploads } from "@/lib/api";
import { DONE_STATUSES, evidenceAttachment } from "@/lib/evidence";
import { loadFormStatuses } from "@/lib/form-status";
import { clearSavedCaseId, rememberCaseId } from "@/lib/case-storage";
import type { CaseSummary } from "@/lib/types";

export type WorkflowStep = "prescreen" | "forms" | "checklist" | "review" | "packet";
type StepStatus = { state: "done" | "attention" | "progress"; note: string };
type StepStatuses = Partial<Record<WorkflowStep, StepStatus>>;


const STEPS: Array<{ id: WorkflowStep; label: string; href: string }> = [
  { id: "prescreen", label: "Prescreen", href: "/prescreen" },
  { id: "forms", label: "Forms", href: "/i485-ingestion" },
  { id: "checklist", label: "Checklist", href: "/manage-tasks" },
  { id: "review", label: "Review", href: "/review" },
  { id: "packet", label: "Print packet", href: "/packet-assembly" },
];

function withCase(href: string, caseId?: string | null) {
  if (!caseId) {
    return href;
  }
  const separator = href.includes("?") ? "&" : "?";
  return `${href}${separator}caseId=${encodeURIComponent(caseId)}`;
}

function readinessTone(label?: string | null) {
  if (!label) {
    return "neutral" as const;
  }
  if (label.startsWith("Ready to print")) {
    return "success" as const;
  }
  if (label.startsWith("Not ready")) {
    return "danger" as const;
  }
  return "warning" as const;
}

export function AppShell({
  step,
  caseId,
  caseName,
  readinessLabel,
  children,
}: {
  step: WorkflowStep;
  caseId?: string | null;
  caseName?: string | null;
  readinessLabel?: string | null;
  children: ReactNode;
}) {
  const activeIndex = STEPS.findIndex((entry) => entry.id === step);
  const [fetchedCase, setFetchedCase] = useState<{ id: string; name: string; readiness: string } | null>(null);

  const [statuses, setStatuses] = useState<{ caseId: string; value: StepStatuses } | null>(null);
  const [caseLoadFailed, setCaseLoadFailed] = useState<string | null>(null);

  // Loads the case name for pages that only know the ID, and step marks from saved case state.
  useEffect(() => {
    if (!caseId) {
      return;
    }
    let cancelled = false;
    Promise.all([
      getCase(caseId),
      getPrescreenState(caseId).catch(() => null),
      getChecklist(caseId).catch(() => null),
      listUploads(caseId).catch(() => []),
      loadFormStatuses(caseId).catch(() => ({})),
    ])
      .then(([loaded, prescreen, checklist, uploads, forms]) => {
        if (cancelled) {
          return;
        }
        setFetchedCase({ id: loaded.id, name: loaded.case_name, readiness: loaded.readiness_label });
        const value: StepStatuses = {};
        const flagCount = prescreen?.evaluation.flags.length ?? 0;
        if (flagCount) {
          value.prescreen = { state: "attention", note: `${flagCount} ${flagCount === 1 ? "answer" : "answers"} outside the standard path` };
        } else if (prescreen?.evaluation.completion_pct === 100) {
          value.prescreen = { state: "done", note: "complete" };
        }
        const formEntries = Object.values(forms);
        const formsMissing = formEntries.reduce((sum, form) => sum + (form?.missing ?? 0), 0);
        if (formEntries.length && !formsMissing) {
          value.forms = { state: "done", note: "every form has its required answers" };
        } else if (formsMissing) {
          value.forms = { state: "progress", note: `${formsMissing} required ${formsMissing === 1 ? "answer" : "answers"} left` };
        }
        const required = checklist?.items.filter((item) => item.applicability === "required") ?? [];
        if (required.length && required.every((item) => DONE_STATUSES.has(item.completion_status))) {
          value.checklist = { state: "done", note: "all required items done" };
        }
        // Required files, and items ticked done without a file, are both missing from the printed packet.
        const missingFiles = evidenceAttachment(checklist?.items ?? [], uploads).missing.filter(
          (item) => item.applicability === "required" || DONE_STATUSES.has(item.completion_status),
        ).length;
        if (loaded.counts.qa_issues) {
          value.review = { state: "attention", note: `${loaded.counts.qa_issues} open ${loaded.counts.qa_issues === 1 ? "issue" : "issues"}` };
        } else if (missingFiles) {
          value.review = { state: "attention", note: `${missingFiles} ${missingFiles === 1 ? "file" : "files"} not attached` };
        } else if (loaded.readiness_label.startsWith("Ready to print")) {
          value.review = { state: "done", note: "no open issues" };
        }
        setStatuses({ caseId, value });
      })
      .catch(() => {
        if (!cancelled) {
          setCaseLoadFailed(caseId);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);
  const stepStatuses = statuses && statuses.caseId === caseId ? statuses.value : {};

  const fallback = fetchedCase && fetchedCase.id === caseId ? fetchedCase : null;
  const shownName = caseName ?? fallback?.name ?? null;
  const shownReadiness = readinessLabel ?? fallback?.readiness ?? null;
  return (
    <div className="min-h-screen bg-canvas text-ink">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:shadow-pop"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-30 border-b border-line bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/85">
        <div className="mx-auto flex max-w-shell items-center gap-4 px-4 py-2.5 md:px-8 lg:grid lg:grid-cols-[auto_minmax(0,1fr)_auto]">
          <Link href="/" className="font-display text-2xl font-semibold leading-none text-ink">
            Lucy
          </Link>
          <nav aria-label="Packet steps" className="hidden justify-center lg:flex">
            <StepList activeIndex={activeIndex} caseId={caseId} statuses={stepStatuses} />
          </nav>
          <div className="ml-auto flex min-w-0 items-center justify-end gap-2 lg:ml-0">
            <CaseSwitcher caseId={caseId} name={shownName} readiness={shownReadiness} caseUnavailable={caseLoadFailed === caseId} />
          </div>
        </div>
        <MobileSteps activeIndex={activeIndex} caseId={caseId} statuses={stepStatuses} />
      </header>
      <main id="main" className="mx-auto flex w-full max-w-shell flex-col gap-6 px-4 pb-16 pt-6 md:px-8 md:pt-8">
        {children}
      </main>
    </div>
  );
}

function StepMarker({ index, isActive, isPast, status }: { index: number; isActive: boolean; isPast: boolean; status?: StepStatus }) {
  return (
    <span className="relative flex h-5 w-5 shrink-0" aria-hidden="true">
      <span
        className={cx(
          "flex h-5 w-5 items-center justify-center rounded-full text-[0.6875rem] font-bold tabular-nums",
          isActive
            ? "bg-pine text-white"
            : status?.state === "done"
              ? "bg-pine/15 text-pine-strong"
              : isPast
                ? "bg-pine/10 text-pine-strong"
                : "border border-line-strong text-muted",
        )}
      >
        {status?.state === "done" && !isActive ? "\u2713" : index + 1}
      </span>
      {status?.state === "attention" ? (
        <span className="absolute -right-1.5 -top-1.5 flex h-3.5 w-3.5 items-center justify-center rounded-full border-2 border-white bg-amber-500 text-[0.5rem] font-bold leading-none text-white">
          !
        </span>
      ) : null}
    </span>
  );
}

function switchToCase(nextCase: CaseSummary) {
  rememberCaseId(nextCase.id);
  const url = new URL(window.location.href);
  url.searchParams.set("caseId", nextCase.id);
  window.location.assign(url.toString());
}

// The one place to see and change which case is open.
function CaseSwitcher({
  caseId,
  name,
  readiness,
  caseUnavailable,
}: {
  caseId?: string | null;
  name: string | null;
  readiness: string | null;
  caseUnavailable: boolean;
}) {
  return (
    <details className="group relative min-w-0">
      <summary
        className="flex min-w-0 cursor-pointer list-none items-center gap-2 rounded-lg border border-line bg-paper px-3 py-1.5 hover:border-line-strong [&::-webkit-details-marker]:hidden"
        aria-label={name ? `Case: ${name}. Change case` : "Open a case"}
      >
        <span className="hidden text-xs font-semibold text-muted sm:inline">Case</span>
        <span className="max-w-[9rem] truncate text-sm font-semibold text-ink sm:max-w-[14rem] xl:max-w-[18rem]">{name ?? (caseId ? (caseUnavailable ? "Case unavailable" : "Loading...") : "No case open")}</span>
        <span aria-hidden="true" className="text-muted transition-transform group-open:rotate-180">
          {"\u25BE"}
        </span>
      </summary>
      <div className="absolute right-0 z-40 mt-2 grid w-80 max-w-[calc(100vw-2rem)] gap-3 rounded-lg border border-line bg-white p-4 shadow-pop">
        {name ? (
          <div>
            <p className="text-xs font-semibold text-muted">Open case</p>
            <p className="mt-0.5 text-sm font-semibold text-ink">{name}</p>
            {readiness ? (
              <Badge tone={readinessTone(readiness)} className="mt-1.5">
                Readiness check: {readiness}
              </Badge>
            ) : null}
          </div>
        ) : null}
        <CaseSelector selectedCaseId={caseId ?? ""} onSelect={switchToCase} label="Switch to another case" />
        <button
          type="button"
          onClick={() => {
            clearSavedCaseId();
            window.location.assign("/prescreen");
          }}
          className="w-fit text-sm font-semibold text-pine underline-offset-4 hover:underline"
        >
          Start a new case
        </button>
      </div>
    </details>
  );
}

function MobileSteps({ activeIndex, caseId, statuses }: { activeIndex: number; caseId?: string | null; statuses: StepStatuses }) {
  const current = STEPS[activeIndex];
  // Always the adjacent step, so the shortcut never skips Checklist or Review.
  const next = STEPS[activeIndex + 1];
  return (
    <nav aria-label="Packet steps" className="border-t border-line lg:hidden">
      <div className="mx-auto flex max-w-shell items-center justify-between gap-3 px-4 py-1.5 md:px-8">
        <details className="group relative">
          <summary className="flex cursor-pointer list-none items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-paper [&::-webkit-details-marker]:hidden">
            <span className="text-muted">
              Step {activeIndex + 1} of {STEPS.length}
            </span>
            <span className="font-semibold text-ink">{current?.label}</span>
            <span aria-hidden="true" className="text-muted transition-transform group-open:rotate-180">
              {"\u25BE"}
            </span>
          </summary>
          <ol className="absolute left-0 z-40 mt-1 grid w-64 gap-0.5 rounded-lg border border-line bg-white p-1.5 shadow-pop">
            {STEPS.map((entry, index) => (
              <li key={entry.id}>
                <Link
                  href={withCase(entry.href, caseId)}
                  aria-current={index === activeIndex ? "step" : undefined}
                  className={cx(
                    "flex items-center gap-2 rounded-md px-2.5 py-2 text-sm font-semibold",
                    index === activeIndex ? "bg-pine-soft text-pine-strong" : "text-ink hover:bg-paper",
                  )}
                >
                  <StepMarker index={index} isActive={index === activeIndex} isPast={index < activeIndex} status={statuses[entry.id]} />
                  {entry.label}
                  {statuses[entry.id] ? (
                    <span className={cx("ml-auto text-xs font-medium", statuses[entry.id]?.state === "attention" ? "text-amber-800" : "text-muted")}>
                      {statuses[entry.id]?.note}
                    </span>
                  ) : null}
                </Link>
              </li>
            ))}
          </ol>
        </details>
        {next && caseId ? (
          <Link href={withCase(next.href, caseId)} className="rounded-lg px-2 py-1.5 text-sm font-semibold text-pine hover:bg-pine-soft">
            Next: {next.label} <span aria-hidden="true">{"\u2192"}</span>
          </Link>
        ) : null}
      </div>
    </nav>
  );
}

function StepList({ activeIndex, caseId, statuses }: { activeIndex: number; caseId?: string | null; statuses: StepStatuses }) {
  return (
    <ol className="flex items-center gap-1">
      {STEPS.map((entry, index) => {
        const isActive = index === activeIndex;
        const isPast = index < activeIndex;
        return (
          <li key={entry.id} className="flex items-center">
            {index > 0 ? <span aria-hidden="true" className="mx-1 h-px w-4 bg-line-strong" /> : null}
            <Link
              href={withCase(entry.href, caseId)}
              aria-current={isActive ? "step" : undefined}
              title={statuses[entry.id]?.note ? `${entry.label}: ${statuses[entry.id]?.note}` : undefined}
              className={cx(
                "flex items-center gap-2 whitespace-nowrap rounded-lg px-2.5 py-1.5 text-sm font-semibold transition-colors",
                isActive ? "bg-pine-soft text-pine-strong" : "text-muted hover:bg-paper hover:text-ink",
              )}
            >
              <StepMarker index={index} isActive={isActive} isPast={isPast} status={statuses[entry.id]} />
              {entry.label}
              {statuses[entry.id] ? <span className="sr-only">, {statuses[entry.id]?.note}</span> : null}
            </Link>
          </li>
        );
      })}
    </ol>
  );
}

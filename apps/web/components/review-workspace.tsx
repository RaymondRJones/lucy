"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, useTransition } from "react";

import { AppShell } from "@/components/app-shell";
import { CaseSelector } from "@/components/case-selector";
import {
  Badge,
  Card,
  Notice,
  PageHeader,
  ProgressBar,
  SectionHeader,
  Stat,
  StatusMessage,
  buttonClass,
  cx,
} from "@/components/ui";
import { generateChecklist, getCase, getChecklist, getPrescreenState, getQa, listUploads, runQa } from "@/lib/api";
import { getSavedCaseId, rememberCaseId } from "@/lib/case-storage";
import type { CaseSummary, ChecklistItem, PrescreenState, QaIssue, QaResults, UploadRecord } from "@/lib/types";

const DONE_STATUSES = new Set(["uploaded", "almost_done", "approved", "complete"]);
const SEVERITY_ORDER = ["blocking", "critical", "important", "recommended"];

function actionHref(baseHref: string, caseId: string) {
  const separator = baseHref.includes("?") ? "&" : "?";
  return `${baseHref}${separator}caseId=${encodeURIComponent(caseId)}`;
}

function isDone(item: ChecklistItem) {
  return DONE_STATUSES.has(item.completion_status);
}

function severityTone(severity: string) {
  if (severity === "blocking" || severity === "critical") {
    return "danger" as const;
  }
  if (severity === "important") {
    return "warning" as const;
  }
  return "neutral" as const;
}

function severityRank(severity: string) {
  const index = SEVERITY_ORDER.indexOf(severity);
  return index < 0 ? SEVERITY_ORDER.length : index;
}

function readinessTone(label: string) {
  if (label.startsWith("Ready to print")) {
    return "success" as const;
  }
  if (label.startsWith("Not ready")) {
    return "danger" as const;
  }
  return "warning" as const;
}

export function ReviewWorkspace() {
  const [caseSummary, setCaseSummary] = useState<CaseSummary | null>(null);
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [uploads, setUploads] = useState<UploadRecord[]>([]);
  const [qa, setQa] = useState<QaResults | null>(null);
  const [prescreen, setPrescreen] = useState<PrescreenState | null>(null);
  const [message, setMessage] = useState<string | null>("Choose a case to review the packet.");
  const [isLoaded, setIsLoaded] = useState(false);
  const [isPending, startTransition] = useTransition();

  const loadCase = useCallback(async (caseId: string, successMessage: string | null) => {
    try {
      const [loadedCase, loadedChecklist, loadedUploads, loadedQa, loadedPrescreen] = await Promise.all([
        getCase(caseId),
        getChecklist(caseId).catch(() => null),
        listUploads(caseId).catch(() => []),
        getQa(caseId).catch(() => null),
        getPrescreenState(caseId).catch(() => null),
      ]);
      rememberCaseId(caseId);
      const url = new URL(window.location.href);
      url.searchParams.set("caseId", caseId);
      window.history.replaceState({}, "", url);
      setCaseSummary(loadedCase);
      setChecklist(loadedChecklist?.items ?? []);
      setUploads(loadedUploads);
      setQa(loadedQa);
      setPrescreen(loadedPrescreen);
      setMessage(successMessage);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not load this case.");
    } finally {
      setIsLoaded(true);
    }
  }, []);

  useEffect(() => {
    const caseId = new URLSearchParams(window.location.search).get("caseId") || getSavedCaseId();
    if (caseId) {
      void loadCase(caseId, null);
    } else {
      setIsLoaded(true);
    }
  }, [loadCase]);

  const requiredItems = checklist.filter((item) => item.applicability === "required");
  const completedRequired = requiredItems.filter(isDone).length;
  const checklistPct = requiredItems.length ? Math.round((completedRequired / requiredItems.length) * 100) : 0;
  const flags = prescreen?.evaluation.flags ?? [];
  const missingRequired = requiredItems.filter((item) => !isDone(item));
  const openIssues: QaIssue[] = (qa?.issues ?? [])
    .filter((issue) => !issue.is_resolved)
    .sort((left, right) => severityRank(left.severity) - severityRank(right.severity));
  const blockingCount = openIssues.filter((issue) => severityTone(issue.severity) === "danger").length;
  const readinessLabel = qa?.summary.label || caseSummary?.readiness_label || "Not started";

  function handleCaseSelect(nextCase: CaseSummary) {
    startTransition(() => {
      void loadCase(nextCase.id, `Opened ${nextCase.case_name}.`);
    });
  }

  function handleGenerateChecklist() {
    if (!caseSummary) {
      return;
    }
    startTransition(() => {
      void (async () => {
        try {
          const generated = await generateChecklist(caseSummary.id);
          setChecklist(generated.items);
          setMessage("Checklist rebuilt from the saved answers.");
        } catch (error) {
          setMessage(error instanceof Error ? error.message : "Could not generate the checklist.");
        }
      })();
    });
  }

  function handleRunQa() {
    if (!caseSummary) {
      return;
    }
    startTransition(() => {
      void (async () => {
        try {
          const results = await runQa(caseSummary.id);
          setQa(results);
          setCaseSummary((current) =>
            current ? { ...current, readiness_label: results.summary.label, readiness_score: results.summary.score } : current,
          );
          setMessage("Review checks finished.");
        } catch (error) {
          setMessage(error instanceof Error ? error.message : "Could not run review checks.");
        }
      })();
    });
  }

  return (
    <AppShell step="review" caseId={caseSummary?.id} caseName={caseSummary?.case_name} readinessLabel={caseSummary?.readiness_label}>
      <PageHeader
        eyebrow="Step 4"
        title="Review the packet"
        description="See what still needs attention before you print. Fix open issues here, then continue to the print packet."
        actions={
          <div className="w-full min-w-64 sm:w-80">
            <CaseSelector selectedCaseId={caseSummary?.id ?? ""} onSelect={handleCaseSelect} disabled={isPending} label="Case" />
          </div>
        }
      />

      <StatusMessage message={message} />

      {!caseSummary ? (
        isLoaded ? (
          <Notice
            title="No case open"
            actions={
              <Link href="/prescreen" className={buttonClass("primary", "sm")}>
                Start a case
              </Link>
            }
          >
            Choose a saved case above, or start a new one from the prescreen.
          </Notice>
        ) : null
      ) : (
        <>
          <Card className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-muted">Packet readiness</p>
              <div className="mt-1 flex flex-wrap items-center gap-3">
                <h2 className="font-display text-3xl text-ink">{readinessLabel}</h2>
                {qa ? <Badge tone={readinessTone(readinessLabel)}>Score {qa.summary.score}</Badge> : null}
              </div>
              {qa?.summary.explanation ? <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{qa.summary.explanation}</p> : null}
              <div className="mt-4 max-w-xl">
                <div className="flex items-center justify-between text-xs font-semibold text-muted">
                  <span>Required checklist items</span>
                  <span className="tabular-nums">
                    {completedRequired} of {requiredItems.length}
                  </span>
                </div>
                <ProgressBar value={checklistPct} label="Required checklist items done" className="mt-1.5" />
              </div>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row lg:flex-col">
              <Link
                href={actionHref("/packet-assembly", caseSummary.id)}
                className={buttonClass(blockingCount ? "secondary" : "primary", "lg")}
              >
                Continue to print packet
              </Link>
              <button type="button" onClick={handleRunQa} disabled={isPending} className={buttonClass("secondary", "md")}>
                {isPending ? "Checking..." : "Run review checks again"}
              </button>
            </div>
          </Card>

          <section aria-label="Summary" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Required items done" value={`${checklistPct}%`} detail={`${completedRequired} of ${requiredItems.length}`} />
            <Stat
              label="Open issues"
              value={openIssues.length}
              detail={blockingCount ? `${blockingCount} must be fixed first` : "None blocking"}
              tone={blockingCount ? "danger" : "neutral"}
            />
            <Stat label="Prescreen flags" value={flags.length} detail="From your prescreen answers" tone={flags.length ? "warning" : "neutral"} />
            <Stat label="Files uploaded" value={uploads.length} detail="Linked to checklist items" />
          </section>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div className="grid content-start gap-6">
              <Card aria-labelledby="issues-heading">
                <SectionHeader
                  id="issues-heading"
                  title="Open issues"
                  description={
                    qa
                      ? "From the latest review checks. Issues marked Blocking must be fixed before the packet is ready."
                      : "Review checks have not run for this case yet."
                  }
                />
                {openIssues.length ? (
                  <ul className="mt-4 divide-y divide-line overflow-hidden rounded-lg border border-line">
                    {openIssues.map((issue) => (
                      <li key={issue.id} className="grid gap-1 bg-white px-4 py-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone={severityTone(issue.severity)} className="capitalize">
                            {issue.severity}
                          </Badge>
                          <p className="text-sm font-semibold text-ink">{issue.title}</p>
                        </div>
                        <p className="text-sm leading-6 text-muted">{issue.description}</p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <Notice tone="success" className="mt-4">
                    {qa ? "No open issues from the latest review checks." : "Run review checks to look for issues."}
                  </Notice>
                )}
              </Card>

              {flags.length ? (
                <Card aria-labelledby="flags-heading">
                  <SectionHeader
                    id="flags-heading"
                    title="Prescreen flags"
                    description="These answers fall outside the standard path. Review them before relying on the generated forms."
                    actions={
                      <Link href={actionHref("/prescreen", caseSummary.id)} className={buttonClass("secondary", "sm")}>
                        Edit prescreen
                      </Link>
                    }
                  />
                  <ul className="mt-4 grid gap-2">
                    {flags.map((flag) => (
                      <li
                        key={flag.code}
                        className={cx(
                          "rounded-lg border px-4 py-3",
                          flag.severity === "critical" ? "border-red-200 bg-red-50" : "border-amber-200 bg-amber-50",
                        )}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone={flag.severity === "critical" ? "danger" : "warning"} className="capitalize">
                            {flag.severity}
                          </Badge>
                          <p className="text-sm font-semibold text-ink">{flag.title}</p>
                        </div>
                        <p className="mt-1 text-sm leading-6 text-ink/80">{flag.description}</p>
                      </li>
                    ))}
                  </ul>
                </Card>
              ) : null}

              <Card aria-labelledby="missing-heading">
                <SectionHeader
                  id="missing-heading"
                  title="Required items still missing"
                  actions={
                    <Link href={actionHref("/manage-tasks", caseSummary.id)} className={buttonClass("secondary", "sm")}>
                      Open checklist
                    </Link>
                  }
                />
                {!checklist.length ? (
                  <Notice
                    tone="warning"
                    className="mt-4"
                    title="No checklist yet"
                    actions={
                      <button type="button" onClick={handleGenerateChecklist} disabled={isPending} className={buttonClass("primary", "sm")}>
                        Build checklist
                      </button>
                    }
                  >
                    Build the checklist from your saved answers to see what to collect.
                  </Notice>
                ) : missingRequired.length ? (
                  <ul className="mt-4 divide-y divide-line overflow-hidden rounded-lg border border-line">
                    {missingRequired.map((item) => (
                      <li key={item.id} className="bg-white px-4 py-3">
                        <p className="text-sm font-semibold text-ink">{item.label}</p>
                        {item.what_to_save_now ? <p className="mt-0.5 text-sm leading-6 text-muted">{item.what_to_save_now}</p> : null}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <Notice tone="success" className="mt-4">
                    Every required checklist item is done.
                  </Notice>
                )}
              </Card>
            </div>

            <aside className="grid content-start gap-4">
              <Card>
                <SectionHeader title="Go back and edit" level={3} />
                <nav aria-label="Edit sections" className="mt-3 grid gap-2">
                  <Link href={actionHref("/prescreen", caseSummary.id)} className={buttonClass("secondary", "md", "justify-start")}>
                    Prescreen answers
                  </Link>
                  <Link href={actionHref("/i485-ingestion", caseSummary.id)} className={buttonClass("secondary", "md", "justify-start")}>
                    Form answers
                  </Link>
                  <Link href={actionHref("/manage-tasks", caseSummary.id)} className={buttonClass("secondary", "md", "justify-start")}>
                    Checklist
                  </Link>
                  <Link href={actionHref("/packet-assembly", caseSummary.id)} className={buttonClass("secondary", "md", "justify-start")}>
                    Evidence uploads
                  </Link>
                </nav>
              </Card>
              <Card>
                <SectionHeader
                  title="Rebuild the checklist"
                  level={3}
                  description="Use this after changing prescreen or form answers so the checklist matches."
                />
                <button
                  type="button"
                  onClick={handleGenerateChecklist}
                  disabled={isPending}
                  className={buttonClass("secondary", "md", "mt-3 w-full")}
                >
                  Rebuild checklist
                </button>
              </Card>
            </aside>
          </div>
        </>
      )}
    </AppShell>
  );
}

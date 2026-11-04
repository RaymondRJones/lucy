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
  StatusMessage,
  buttonClass,
  cx,
} from "@/components/ui";
import { generateChecklist, getCase, getChecklist, getPrescreenState, getQa, listUploads, runQa } from "@/lib/api";
import { getSavedCaseId, rememberCaseId } from "@/lib/case-storage";
import { evidenceAttachment } from "@/lib/evidence";
import { packetFormHref, packetFormOptionForKey, type PacketFormKey } from "@/lib/packet-form-flow";
import type { CaseSummary, ChecklistItem, PrescreenState, QaIssue, QaResults, UploadRecord } from "@/lib/types";

const DONE_STATUSES = new Set(["uploaded", "almost_done", "approved", "complete"]);
const SEVERITY_ORDER = ["blocking", "critical", "important", "recommended"];

function actionHref(baseHref: string, caseId: string) {
  const separator = baseHref.includes("?") ? "&" : "?";
  return `${baseHref}${separator}caseId=${encodeURIComponent(caseId)}`;
}

const FORM_KEYS_BY_CODE: Record<string, PacketFormKey> = {
  form_i130: "i130",
  form_i130a: "i130a",
  form_i485: "i485",
  form_i864: "i864",
  form_i765: "i765",
  form_i131: "i131",
};

// Where the user goes to fix an issue: the form it came from, otherwise the checklist.
function issueFix(issue: QaIssue, caseId: string) {
  const formKey = issue.checklist_item_code ? FORM_KEYS_BY_CODE[issue.checklist_item_code] : undefined;
  if (formKey) {
    const option = packetFormOptionForKey(formKey);
    return { href: packetFormHref(formKey, caseId), label: `Open ${option?.label ?? "form"}` };
  }
  if (issue.checklist_item_code) {
    return { href: actionHref("/manage-tasks", caseId), label: "Open checklist" };
  }
  return null;
}

function factValue(value: string | number | boolean | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split("-").map(Number);
    return new Date(year, month - 1, day).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
  }
  return String(value).replaceAll("_", " ");
}

// Some saved facts hold a two-letter country code; show the country name instead.
function countryValue(value: string | null | undefined) {
  if (value && /^[A-Z]{2}$/.test(value)) {
    try {
      return new Intl.DisplayNames(["en"], { type: "region" }).of(value) ?? value;
    } catch {
      return value;
    }
  }
  return factValue(value);
}

function fullName(person?: { first_name: string | null; last_name: string | null } | null) {
  return [person?.first_name, person?.last_name].filter(Boolean).join(" ") || null;
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

export function ReviewWorkspace() {
  const [caseSummary, setCaseSummary] = useState<CaseSummary | null>(null);
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [uploads, setUploads] = useState<UploadRecord[]>([]);
  const [qa, setQa] = useState<QaResults | null>(null);
  const [prescreen, setPrescreen] = useState<PrescreenState | null>(null);
  const [message, setMessage] = useState<string | null>("Choose a case to review the packet.");
  const [isLoaded, setIsLoaded] = useState(false);
  const [acknowledgedIssues, setAcknowledgedIssues] = useState(false);
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
  const evidence = evidenceAttachment(checklist, uploads);
  const requiredEvidenceMissing = evidence.missing.filter((item) => item.applicability === "required");
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
      />

      <StatusMessage message={message} />

      {!caseSummary ? (
        isLoaded ? (
          <Card className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,22rem)] md:items-end">
            <SectionHeader title="No case open" description="Open a saved case to review it, or start a new one from the prescreen." />
            <div className="grid gap-3">
              <CaseSelector selectedCaseId="" onSelect={handleCaseSelect} disabled={isPending} label="Saved cases" />
              <Link href="/prescreen" className={buttonClass("secondary", "md")}>
                Start a new case
              </Link>
            </div>
          </Card>
        ) : null
      ) : (
        <>
          <Card className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-muted">Packet readiness</p>
              <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h2 className="font-display text-3xl text-ink">{readinessLabel}</h2>
                {qa ? (
                  <span className="text-sm tabular-nums text-muted" title="A rough guide from completed items and open issues. It is not legal approval.">
                    Score {qa.summary.score} of 100
                  </span>
                ) : null}
              </div>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
                {openIssues.length
                  ? `${openIssues.length} open ${openIssues.length === 1 ? "issue needs" : "issues need"} your attention before you print.`
                  : qa?.summary.explanation || "Run the review checks to look for missing answers and mismatches."}{" "}
                Payment and the mailing address are added on the Print packet step.
              </p>
              <div className="mt-4 grid max-w-2xl gap-4 sm:grid-cols-2">
                <div>
                  <div className="flex items-center justify-between gap-3 text-xs font-semibold text-muted">
                    <span>Checklist items marked done</span>
                    <span className="tabular-nums">
                      {completedRequired} of {requiredItems.length}
                    </span>
                  </div>
                  <ProgressBar value={checklistPct} label="Required checklist items marked done" className="mt-1.5" />
                </div>
                <div>
                  <div className="flex items-center justify-between gap-3 text-xs font-semibold text-muted">
                    <span>Evidence files attached</span>
                    <span className="tabular-nums">
                      {evidence.attached.length} of {evidence.attached.length + evidence.missing.length}
                    </span>
                  </div>
                  <ProgressBar
                    value={evidence.attached.length + evidence.missing.length ? (evidence.attached.length / (evidence.attached.length + evidence.missing.length)) * 100 : 0}
                    label="Evidence files attached"
                    className="mt-1.5"
                  />
                </div>
              </div>
              {evidence.missing.length ? (
                <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
                  <span className={cx("font-semibold", requiredEvidenceMissing.length ? "text-amber-900" : "text-ink")}>
                    No file attached yet:
                  </span>{" "}
                  {evidence.missing.map((item) => item.label).join(", ")}.{" "}
                  <Link href={actionHref("/packet-assembly", caseSummary.id)} className="font-semibold text-pine underline-offset-4 hover:underline">
                    Attach on the Print packet step
                  </Link>
                  . A ticked checklist item without a file is not included in the printed PDF.
                </p>
              ) : null}
            </div>
            <div className="flex flex-col gap-2 sm:flex-row lg:w-80 lg:flex-col">
              {openIssues.length ? (
                <a href="#issues-heading" className={buttonClass("primary", "lg")}>
                  Review {openIssues.length} open {openIssues.length === 1 ? "issue" : "issues"}
                </a>
              ) : null}
              {openIssues.length ? (
                <div className="grid gap-2 rounded-lg border border-line bg-paper p-3">
                  <label className="flex items-start gap-2 text-sm text-ink">
                    <input
                      type="checkbox"
                      checked={acknowledgedIssues}
                      onChange={(event) => setAcknowledgedIssues(event.target.checked)}
                      className="mt-0.5 h-4 w-4"
                    />
                    <span>
                      {blockingCount
                        ? "I understand the blocking issues mean this packet is not ready, and I want to see the print step anyway."
                        : "I have read the open issues and want to continue anyway."}
                    </span>
                  </label>
                  {acknowledgedIssues ? (
                    <Link href={actionHref("/packet-assembly", caseSummary.id)} className={buttonClass("secondary", "md")}>
                      Continue to print packet
                    </Link>
                  ) : (
                    <span aria-disabled="true" className={buttonClass("secondary", "md", "cursor-not-allowed opacity-50")}>
                      Continue to print packet
                    </span>
                  )}
                </div>
              ) : (
                <Link href={actionHref("/packet-assembly", caseSummary.id)} className={buttonClass("primary", "lg")}>
                  Continue to print packet
                </Link>
              )}
              <button type="button" onClick={handleRunQa} disabled={isPending} className={buttonClass(openIssues.length ? "ghost" : "secondary", "md")}>
                {isPending ? "Checking..." : "Run review checks again"}
              </button>
            </div>
          </Card>


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
                    {openIssues.map((issue) => {
                      const fix = issueFix(issue, caseSummary.id);
                      return (
                        <li key={issue.id} className="grid gap-3 bg-white px-4 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge tone={severityTone(issue.severity)} className="capitalize">
                                {issue.severity}
                              </Badge>
                              <p className="text-sm font-semibold text-ink">{issue.title}</p>
                            </div>
                            <p className="mt-1 text-sm leading-6 text-muted">{issue.description}</p>
                          </div>
                          {fix ? (
                            <Link href={fix.href} className={buttonClass("secondary", "sm", "w-fit")}>
                              {fix.label}
                            </Link>
                          ) : null}
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <Notice tone="success" className="mt-4">
                    {qa ? "No open issues from the latest review checks." : "Run review checks to look for issues."}
                  </Notice>
                )}
              </Card>

              <Card aria-labelledby="facts-heading">
                <SectionHeader
                  id="facts-heading"
                  title="Check your key details"
                  description="These facts print on several forms. If one is wrong, change it on the form shown."
                />
                <dl className="mt-4 divide-y divide-line overflow-hidden rounded-lg border border-line">
                  {[
                    { label: "Petitioner (U.S. citizen spouse)", value: fullName(caseSummary.petitioner), form: "i130" as const },
                    { label: "Beneficiary (applying spouse)", value: fullName(caseSummary.beneficiary), form: "i485" as const },
                    { label: "Beneficiary's country of birth", value: countryValue(caseSummary.beneficiary?.country_of_birth), form: "i485" as const },
                    {
                      label: "Beneficiary's current status",
                      value: factValue(caseSummary.beneficiary?.current_immigration_status),
                      form: "i485" as const,
                    },
                    { label: "Date of marriage", value: factValue(caseSummary.marriage?.marriage_date), form: "i130" as const },
                    { label: "First marriage for both", value: factValue(caseSummary.marriage?.first_marriage_for_both), form: "i130" as const },
                    { label: "Household size", value: factValue(caseSummary.marriage?.household_size), form: "i864" as const },
                  ].map((fact) => (
                    <div key={fact.label} className="grid gap-1 bg-white px-4 py-3 text-sm sm:grid-cols-[minmax(0,15rem)_minmax(0,1fr)_auto] sm:items-center sm:gap-4">
                      <dt className="text-muted">{fact.label}</dt>
                      <dd className={cx("font-semibold capitalize", fact.value ? "text-ink" : "text-amber-800")}>{fact.value ?? "Not entered"}</dd>
                      <dd>
                        <Link
                          href={packetFormHref(fact.form, caseSummary.id)}
                          className="font-semibold text-pine underline-offset-4 hover:underline"
                        >
                          Change<span className="sr-only"> {fact.label.toLowerCase()}</span>
                        </Link>
                      </dd>
                    </div>
                  ))}
                </dl>
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

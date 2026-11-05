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
  SectionHeader,
  StatusMessage,
  buttonClass,
  cardClass,
  cx,
} from "@/components/ui";
import { generateChecklist, getCase, getChecklist, getPrescreenState, getQa, listUploads, runQa } from "@/lib/api";
import { getSavedCaseId, rememberCaseId } from "@/lib/case-storage";
import { DONE_STATUSES, evidenceAttachment } from "@/lib/evidence";
import { loadFormStatuses, type FormStatuses } from "@/lib/form-status";
import { packetFormHref, packetFormOptionForKey, type PacketFormKey } from "@/lib/packet-form-flow";
import type { CaseSummary, ChecklistItem, PrescreenState, QaIssue, QaResults, UploadRecord } from "@/lib/types";

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
  if (value && value === value.toUpperCase()) {
    return value.toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
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

type OpenItem = {
  key: string;
  tone: "danger" | "warning" | "neutral";
  tag: string;
  title: string;
  body: string;
  chips?: string[];
  units?: number;
  unitLabel?: string;
  links?: Array<{ href: string; label: string }>;
  action: { href: string; label: string } | null;
};

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
  const [formStatuses, setFormStatuses] = useState<FormStatuses>({});
  const [message, setMessage] = useState<string | null>(null);
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
      // Asked only once the case exists; the result is shared with the step bar.
      const loadedFormStatuses = await loadFormStatuses(caseId).catch(() => ({}) as FormStatuses);
      rememberCaseId(caseId);
      const url = new URL(window.location.href);
      url.searchParams.set("caseId", caseId);
      window.history.replaceState({}, "", url);
      setCaseSummary(loadedCase);
      setChecklist(loadedChecklist?.items ?? []);
      setUploads(loadedUploads);
      setQa(loadedQa);
      setPrescreen(loadedPrescreen);
      setFormStatuses(loadedFormStatuses);
      setMessage(successMessage);
    } catch (error) {
      const reason = error instanceof Error ? error.message : "";
      setMessage(
        /not found/i.test(reason)
          ? "Could not find that case on this computer. It may have been deleted, or the link came from another computer. Open a saved case below."
          : reason || "Could not load this case.",
      );
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
  const evidence = evidenceAttachment(checklist, uploads);
  const requiredEvidenceMissing = evidence.missing.filter((item) => item.applicability === "required");
  // A ticked item with no file reads as done but is left out of the printed PDF, so it counts as open.
  const tickedWithoutFile = evidence.missing.filter((item) => item.applicability !== "required" && isDone(item));
  const otherEvidenceMissing = evidence.missing.filter((item) => item.applicability !== "required" && !isDone(item));
  const readinessLabel = qa?.summary.label || caseSummary?.readiness_label || "Not started";
  // With no checklist there is nothing to review yet, so the page must not read as "all clear".
  const notStarted = !checklist.length;
  const prescreenDone = prescreen?.evaluation.completion_pct === 100;
  const startHref = caseSummary ? actionHref(prescreenDone ? "/i485-ingestion" : "/prescreen", caseSummary.id) : "/prescreen";
  const startLabel = prescreenDone ? "Continue to forms" : "Continue prescreen";

  // Required answers still empty on the forms themselves; a ticked "Completed Form" checklist row does not fill them in.
  const formsMissing = (Object.entries(formStatuses) as Array<[PacketFormKey, { missing: number } | undefined]>).filter(
    (entry): entry is [PacketFormKey, { missing: number }] => Boolean(entry[1]?.missing),
  );
  const formAnswersMissing = formsMissing.reduce((sum, [, status]) => sum + status.missing, 0);

  // Every count on this page comes from this one list, so the headline always matches the rows below it.
  const openItems: OpenItem[] = notStarted
    ? []
    : [
        ...(formsMissing.length && caseSummary
          ? [
              {
                key: "answers",
                tone: "danger" as const,
                tag: "Blocking",
                title: `${formAnswersMissing} required form ${formAnswersMissing === 1 ? "answer is" : "answers are"} still empty`,
                body: "The printed forms would have blank required fields. Answer them on each form page.",
                units: formAnswersMissing,
                unitLabel: formAnswersMissing === 1 ? "form answer" : "form answers",
                links: formsMissing.map(([key, status]) => ({
                  href: packetFormHref(key, caseSummary.id),
                  label: `${packetFormOptionForKey(key)?.label ?? key}: ${status.missing} left`,
                })),
                action: null,
              },
            ]
          : []),
        ...openIssues.map((issue): OpenItem => {
          const fix = caseSummary ? issueFix(issue, caseSummary.id) : null;
          return {
            key: issue.id,
            tone: severityTone(issue.severity),
            tag: issue.severity.charAt(0).toUpperCase() + issue.severity.slice(1),
            title: issue.title,
            body: issue.description,
            action: fix,
          };
        }),
        ...flags.map(
          (flag): OpenItem => ({
            key: `flag-${flag.code}`,
            tone: flag.severity === "critical" ? "danger" : "warning",
            tag: flag.severity === "critical" ? "Critical" : "Important",
            title: flag.title,
            body: `From your prescreen answers. ${flag.description}`,
            action: caseSummary ? { href: actionHref("/prescreen", caseSummary.id), label: "Edit prescreen" } : null,
          }),
        ),
        ...(missingRequired.length
          ? [
              {
                key: "checklist",
                tone: "danger" as const,
                tag: "Blocking",
                title: `${missingRequired.length} required checklist ${missingRequired.length === 1 ? "item is" : "items are"} not done`,
                body: "Tick each one off on the checklist once you have it.",
                units: missingRequired.length,
                unitLabel: missingRequired.length === 1 ? "checklist item" : "checklist items",
                chips: missingRequired.map((item) => item.label),
                action: caseSummary ? { href: actionHref("/manage-tasks", caseSummary.id), label: "Open checklist" } : null,
              },
            ]
          : []),
        ...(requiredEvidenceMissing.length
          ? [
              {
                key: "files",
                tone: "danger" as const,
                tag: "Blocking",
                title: `${requiredEvidenceMissing.length} required ${requiredEvidenceMissing.length === 1 ? "file is" : "files are"} not attached`,
                body: "These will be missing from the printed packet unless you attach them or add paper copies yourself.",
                units: requiredEvidenceMissing.length,
                unitLabel: requiredEvidenceMissing.length === 1 ? "required file" : "required files",
                chips: requiredEvidenceMissing.map((item) => item.label),
                action: caseSummary ? { href: actionHref("/packet-assembly", caseSummary.id), label: "Attach files" } : null,
              },
            ]
          : []),
        ...(tickedWithoutFile.length
          ? [
              {
                key: "ticked",
                tone: "warning" as const,
                tag: "Important",
                title: `${tickedWithoutFile.length} ticked ${tickedWithoutFile.length === 1 ? "item has" : "items have"} no file attached`,
                body: "You marked these done on the checklist, but they will not be in the printed packet unless you attach a file or add paper copies. If one does not apply to your case, untick it.",
                units: tickedWithoutFile.length,
                unitLabel: tickedWithoutFile.length === 1 ? "ticked item without a file" : "ticked items without a file",
                chips: tickedWithoutFile.map((item) => item.label),
                action: caseSummary ? { href: actionHref("/packet-assembly", caseSummary.id), label: "Attach files" } : null,
              },
            ]
          : []),
      ];
  // The headline counts tasks (one per row below); the summary spells out how much each task holds.
  const attentionCount = openItems.length;
  const taskBreakdown = openItems
    .filter((item) => item.units && item.unitLabel)
    .map((item) => `${item.units} ${item.unitLabel}`)
    .join(", ");
  const blockingCount = openItems.filter((item) => item.tone === "danger").length;
  const qaBlockingCount = openIssues.filter((issue) => severityTone(issue.severity) === "danger").length;
  // Blocking review issues and unfinished required checklist items lock the way to print. Missing files are
  // attached on the Print packet step itself, which will not assemble without them unless the user confirms paper copies.
  const hardBlocked = qaBlockingCount > 0 || missingRequired.length > 0 || formAnswersMissing > 0;
  const onlyFilesOpen = openItems.every((item) => item.key === "files" || item.key === "ticked") && attentionCount > 0;
  const canContinue = !notStarted && !attentionCount && !/^not (ready|started)/i.test(readinessLabel);
  const headline = notStarted
    ? "Nothing to review yet"
    : blockingCount
      ? `Not ready to print: ${attentionCount} ${attentionCount === 1 ? "thing" : "things"} to finish`
      : attentionCount
        ? `${attentionCount} ${attentionCount === 1 ? "thing" : "things"} to ${hardBlocked ? "finish" : "check"}`
        : otherEvidenceMissing.length
          ? `Ready, with ${otherEvidenceMissing.length} optional ${otherEvidenceMissing.length === 1 ? "file" : "files"} not attached`
          : readinessLabel.startsWith("Ready to print")
            ? "Forms and evidence are ready"
            : readinessLabel;
  const summary = notStarted
    ? "Lucy builds the checklist from your prescreen and form answers. Finish those first, then come back to check the packet."
    : attentionCount
      ? hardBlocked
        ? `Finish the blocking items below before you print${taskBreakdown ? `: ${taskBreakdown}` : ""}.`
        : onlyFilesOpen
          ? `Attach the ${requiredEvidenceMissing.length + tickedWithoutFile.length === 1 ? "missing file" : "missing files"} on the Print packet step, where you also add payment and the mailing address. Or add paper copies.`
          : "Check each item below before you print."
      : qa?.summary.explanation || "Run the review checks to look for missing answers and mismatches.";
  const statusTone: "danger" | "warning" | "success" | "neutral" = notStarted
    ? "neutral"
    : blockingCount
      ? "danger"
      : attentionCount
        ? "warning"
        : canContinue
          ? "success"
          : "neutral";
  const evidenceTotal = evidence.attached.length + evidence.missing.length;

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
          <Card className="max-w-xl">
            <SectionHeader title="Open a case to review" description="Choose a saved case, or start a new one from the prescreen." />
            <div className="mt-4 grid gap-3">
              <CaseSelector selectedCaseId="" onSelect={handleCaseSelect} disabled={isPending} label="Saved cases" />
              <Link href="/prescreen" className={buttonClass("ghost", "md", "-ml-3 w-fit")}>
                Start a new case <span aria-hidden="true">{"\u2192"}</span>
              </Link>
            </div>
          </Card>
        ) : null
      ) : (
        <>
          <section className={cx(cardClass, "overflow-hidden")} aria-labelledby="readiness-heading">
            <div className="flex flex-col gap-5 p-5 md:flex-row md:items-start md:justify-between md:p-6">
              <div className="flex min-w-0 gap-4">
                <StatusGlyph tone={statusTone} />
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-muted">
                    {attentionCount ? (
                      "Before you print"
                    ) : (
                      <>
                        Lucy&apos;s readiness check <span aria-hidden="true">&middot;</span> <span className="text-ink">{readinessLabel}</span>
                      </>
                    )}
                  </p>
                  <h2 id="readiness-heading" className="mt-1 font-display text-2xl leading-tight text-ink sm:text-[1.75rem]">
                    {headline}
                  </h2>
                  <p className="mt-1.5 max-w-2xl text-sm leading-6 text-muted">
                    {summary}
                    {onlyFilesOpen ? "" : " Payment and the mailing address are added on the Print packet step."}
                  </p>
                </div>
              </div>
              <div className="flex shrink-0 flex-col gap-2 sm:flex-row md:flex-col lg:flex-row">
                {notStarted ? (
                  <Link href={startHref} className={buttonClass("primary", "md")}>
                    {startLabel} <span aria-hidden="true">{"→"}</span>
                  </Link>
                ) : onlyFilesOpen ? (
                  <Link href={actionHref("/packet-assembly", caseSummary.id)} className={buttonClass("primary", "md")}>
                    Continue to print packet <span aria-hidden="true">{"\u2192"}</span>
                  </Link>
                ) : attentionCount ? (
                  <a href="#issues-heading" className={buttonClass("primary", "md")}>
                    See what to finish
                  </a>
                ) : canContinue ? (
                  <Link href={actionHref("/packet-assembly", caseSummary.id)} className={buttonClass("primary", "md")}>
                    Continue to print packet <span aria-hidden="true">{"→"}</span>
                  </Link>
                ) : null}
                {notStarted ? null : (
                  <button type="button" onClick={handleRunQa} disabled={isPending} className={buttonClass("secondary", "md")}>
                    {isPending ? "Checking..." : "Run checks again"}
                  </button>
                )}
              </div>
            </div>
            <dl className="grid grid-cols-3 divide-x divide-line border-t border-line">
              <Meter
                label="Required checklist items"
                value={notStarted ? "No checklist yet" : `${completedRequired} of ${requiredItems.length} done`}
                pct={notStarted ? undefined : checklistPct}
                tone={notStarted ? "neutral" : completedRequired === requiredItems.length ? "pine" : "warning"}
              />
              <Meter
                label="Evidence files attached"
                value={evidenceTotal ? `${evidence.attached.length} of ${evidenceTotal}` : "None needed yet"}
                pct={evidenceTotal ? (evidence.attached.length / evidenceTotal) * 100 : undefined}
                tone={!evidenceTotal ? "neutral" : requiredEvidenceMissing.length ? "warning" : evidence.missing.length ? "neutral" : "pine"}
              />
              <Meter
                label="Open items"
                value={notStarted ? "Not checked yet" : attentionCount ? `${attentionCount} to ${hardBlocked ? "finish" : "check"}` : "None open"}
                tone={notStarted ? "neutral" : blockingCount ? "danger" : attentionCount ? "warning" : "pine"}
              />
            </dl>
            {attentionCount && !onlyFilesOpen ? (
              hardBlocked ? (
                <div className="flex items-start gap-3 border-t border-line bg-paper px-5 py-4 text-sm leading-6 text-ink md:px-6">
                  <span aria-hidden="true" className="mt-0.5 font-bold text-red-700">
                    !
                  </span>
                  <p className="max-w-3xl">
                    <span className="font-semibold">Print is locked until the required items are done. </span>
                    {qaBlockingCount ? "Blocking review issues must be fixed first." : "Finish the blocking items below, then come back here."}{" "}
                    You can still attach files on the Print packet step.
                  </p>
                </div>
              ) : (
                <div className="grid gap-3 border-t border-amber-200 bg-amber-50/70 px-5 py-4 md:px-6">
                  <p className="max-w-3xl text-sm leading-6 text-amber-950">
                    <span className="font-semibold">Before you continue: </span>
                    some items may mean this case is outside what Lucy is built for. If you are unsure, talk to an immigration attorney or
                    accredited representative before mailing.
                  </p>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <label className="flex cursor-pointer items-start gap-3 text-sm text-ink">
                      <input
                        type="checkbox"
                        checked={acknowledgedIssues}
                        onChange={(event) => setAcknowledgedIssues(event.target.checked)}
                        className="mt-0.5 h-5 w-5 shrink-0"
                      />
                      <span>I have read every open item and want to continue anyway.</span>
                    </label>
                    {acknowledgedIssues ? (
                      <Link href={actionHref("/packet-assembly", caseSummary.id)} className={buttonClass("secondary", "md", "shrink-0")}>
                        Continue to print packet <span aria-hidden="true">{"→"}</span>
                      </Link>
                    ) : (
                      <span className="flex shrink-0 flex-col items-start gap-1 sm:items-end">
                        <span
                          aria-disabled="true"
                          className="inline-flex min-h-10 cursor-not-allowed items-center justify-center rounded-lg border border-line-strong bg-paper px-4 py-2 text-sm font-semibold text-muted"
                        >
                          Continue to print packet
                        </span>
                        <span className="text-xs text-amber-950">Tick the box to continue</span>
                      </span>
                    )}
                  </div>
                </div>
              )
            ) : null}
          </section>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div className="grid content-start gap-6">
              <Card aria-labelledby="issues-heading">
                <SectionHeader
                  id="issues-heading"
                  title="Open items"
                  description={
                    notStarted
                      ? "Review checks run once the checklist is built from your answers."
                      : "From the review checks, your prescreen answers, the checklist, and your attached files."
                  }
                />
                {openItems.length ? (
                  <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                    <span>
                      <span className="font-semibold text-red-800">Blocking</span>: must be done before you print
                    </span>
                    <span>
                      <span className="font-semibold text-amber-900">Important</span>: check before you mail
                    </span>
                  </p>
                ) : null}
                {openItems.length ? (
                  <ol className="mt-3 divide-y divide-line overflow-hidden rounded-lg border border-line">
                    {openItems.map((item) => (
                      <li key={item.key} className="grid gap-3 bg-white px-4 py-3.5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge tone={item.tone}>{item.tag}</Badge>
                            <p className="text-sm font-semibold text-ink">{item.title}</p>
                          </div>
                          <p className="mt-1 text-sm leading-6 text-muted">{item.body}</p>
                          {item.chips ? <FileChips labels={item.chips} /> : null}
                          {item.links ? (
                            <ul className="mt-2 flex flex-wrap gap-2">
                              {item.links.map((link) => (
                                <li key={link.href}>
                                  <Link href={link.href} className={buttonClass("secondary", "sm")}>
                                    {link.label} <span aria-hidden="true">{"\u2192"}</span>
                                  </Link>
                                </li>
                              ))}
                            </ul>
                          ) : null}
                        </div>
                        {item.action ? (
                          <Link href={item.action.href} className={buttonClass("secondary", "sm", "w-fit")}>
                            {item.action.label}
                          </Link>
                        ) : null}
                      </li>
                    ))}
                  </ol>
                ) : notStarted ? (
                  <Notice
                    className="mt-4"
                    title="No checklist yet"
                    actions={
                      <button type="button" onClick={handleGenerateChecklist} disabled={isPending} className={buttonClass("secondary", "sm")}>
                        Build checklist now
                      </button>
                    }
                  >
                    Nothing to check yet. Lucy builds the checklist on its own as you save prescreen and form answers.
                  </Notice>
                ) : (
                  <Notice tone={qa ? "success" : "neutral"} className="mt-4">
                    {qa ? "Nothing open. The review checks found no issues and every required file is attached." : "Run review checks to look for issues."}
                  </Notice>
                )}
                {otherEvidenceMissing.length ? (
                  <div className="mt-4 rounded-lg border border-line bg-paper px-4 py-3.5">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-ink">
                          Worth a look: {otherEvidenceMissing.length} recommended or conditional{" "}
                          {otherEvidenceMissing.length === 1 ? "file has" : "files have"} no upload
                        </p>
                        <p className="mt-1 text-sm leading-6 text-muted">
                          Not counted as open. Attach any that apply to your case; a ticked item without a file is not in the printed PDF.
                        </p>
                        <FileChips labels={otherEvidenceMissing.map((item) => item.label)} />
                      </div>
                      <Link href={actionHref("/packet-assembly", caseSummary.id)} className={buttonClass("ghost", "sm", "w-fit shrink-0")}>
                        Attach files
                      </Link>
                    </div>
                  </div>
                ) : null}
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
                    <div key={fact.label} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-0.5 bg-white px-4 py-3 text-sm sm:grid-cols-[minmax(0,15rem)_minmax(0,1fr)_auto] sm:items-center">
                      <dt className="col-span-2 text-muted sm:col-span-1">{fact.label}</dt>
                      <dd className={cx(fact.value ? "font-semibold capitalize text-ink" : "text-muted")}>{fact.value ?? "Not entered yet"}</dd>
                      <dd>
                        <Link
                          href={packetFormHref(fact.form, caseSummary.id)}
                          className="font-semibold text-pine underline-offset-4 hover:underline"
                        >
                          {fact.value ? "Change" : "Enter"}
                          <span className="sr-only"> {fact.label.toLowerCase()}</span>
                        </Link>
                      </dd>
                    </div>
                  ))}
                </dl>
              </Card>


            </div>

            <aside className="grid content-start gap-4 xl:sticky xl:top-20 xl:h-fit">
              <nav aria-labelledby="edit-heading" className={cx(cardClass, "overflow-hidden")}>
                <div className="px-5 pb-3 pt-4">
                  <h3 id="edit-heading" className="text-sm font-semibold text-ink">
                    Go back and edit
                  </h3>
                  <p className="mt-0.5 text-xs leading-5 text-muted">The checklist updates on its own when you save answers.</p>
                </div>
                <ul className="divide-y divide-line border-t border-line">
                  {[
                    { href: "/prescreen", label: "Prescreen answers", detail: "Which forms you need" },
                    { href: "/i485-ingestion", label: "Form answers", detail: "I-130, I-485, I-864 and more" },
                    { href: "/manage-tasks", label: "Checklist", detail: "What to collect" },
                    { href: "/packet-assembly", label: "Evidence uploads", detail: "Files in the printed packet" },
                  ].map((entry) => (
                    <li key={entry.href}>
                      <Link
                        href={actionHref(entry.href, caseSummary.id)}
                        className="group flex items-center justify-between gap-3 px-5 py-3 text-sm transition-colors hover:bg-paper"
                      >
                        <span className="min-w-0">
                          <span className="block font-semibold text-ink">{entry.label}</span>
                          <span className="block text-xs text-muted">{entry.detail}</span>
                        </span>
                        <span aria-hidden="true" className="text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-pine">
                          {"\u2192"}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </nav>
            </aside>
          </div>

        </>
      )}
    </AppShell>
  );
}

function StatusGlyph({ tone }: { tone: "danger" | "warning" | "success" | "neutral" }) {
  const styles = {
    danger: "bg-red-50 text-red-700 ring-red-200",
    warning: "bg-amber-50 text-amber-700 ring-amber-200",
    success: "bg-pine-soft text-pine-strong ring-pine/25",
    neutral: "bg-paper text-muted ring-line",
  }[tone];
  const glyph = { danger: "!", warning: "!", success: "\u2713", neutral: "\u2026" }[tone];
  return (
    <span aria-hidden="true" className={cx("mt-1 hidden h-10 w-10 shrink-0 sm:flex items-center justify-center rounded-full text-lg font-bold ring-1", styles)}>
      {glyph}
    </span>
  );
}

function Meter({
  label,
  value,
  pct,
  tone,
}: {
  label: string;
  value: string;
  pct?: number;
  tone: "pine" | "warning" | "danger" | "neutral";
}) {
  const bar = { pine: "bg-pine", warning: "bg-amber-500", danger: "bg-red-600", neutral: "bg-line-strong" }[tone];
  const text = { pine: "text-ink", warning: "text-amber-900", danger: "text-red-800", neutral: "text-muted" }[tone];
  return (
    <div className="min-w-0 px-3 py-3 sm:px-5 sm:py-4 md:px-6">
      <dt className="text-xs font-semibold leading-4 text-muted">{label}</dt>
      <dd className={cx("mt-1 text-sm font-semibold tabular-nums sm:text-base", text)}>{value}</dd>
      {pct !== undefined ? (
        <dd className="mt-2 h-1.5 overflow-hidden rounded-full bg-line" aria-hidden="true">
          <span className={cx("block h-full rounded-full", bar)} style={{ width: `${Math.max(0, Math.min(100, Math.round(pct)))}%` }} />
        </dd>
      ) : null}
    </div>
  );
}

function FileChips({ labels }: { labels: string[] }) {
  return (
    <ul className="mt-2 grid gap-x-6 gap-y-1 text-sm text-ink sm:grid-cols-2">
      {labels.map((label) => (
        <li key={label} className="flex items-baseline gap-2">
          <span aria-hidden="true" className="h-1 w-1 shrink-0 translate-y-[-2px] rounded-full bg-line-strong" />
          {label}
        </li>
      ))}
    </ul>
  );
}

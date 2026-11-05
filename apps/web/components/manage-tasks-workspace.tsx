"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, useTransition } from "react";

import { AppShell } from "@/components/app-shell";
import { CaseSelector } from "@/components/case-selector";
import { Badge, Card, Notice, PageHeader, ProgressBar, SectionHeader, StatusMessage, buttonClass } from "@/components/ui";
import { getChecklist, getUscisRequirements, listCases, listUploads, updateChecklistItem } from "@/lib/api";
import { getSatisfiedChecklistCodes, isEvidenceItem } from "@/lib/evidence";
import { getSavedCaseId, rememberCaseId } from "@/lib/case-storage";
import type {
  CaseSummary,
  ChecklistItem,
  ChecklistWorkflowStatus,
  UscisRequirementsPayload,
} from "@/lib/types";

const FORM_FILTERS = [
  { code: "form_i130", label: "I-130" },
  { code: "form_i130a", label: "I-130A" },
  { code: "form_i485", label: "I-485" },
  { code: "form_i864", label: "I-864" },
  { code: "form_i765", label: "I-765" },
  { code: "form_i131", label: "I-131" },
  { code: "form_g1145", label: "G-1145" },
];

const DONE_STATUSES = new Set<ChecklistWorkflowStatus>(["uploaded", "almost_done", "approved", "complete"]);

function classNames(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

function formatStatus(value: string) {
  return value.replaceAll("_", " ");
}

function isDone(item?: ChecklistItem) {
  return item ? DONE_STATUSES.has(item.completion_status) : false;
}

export function ManageTasksWorkspace() {
  const [caseSummary, setCaseSummary] = useState<CaseSummary | null>(null);
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [attachedCodes, setAttachedCodes] = useState<Set<string>>(new Set());
  const [requirements, setRequirements] = useState<UscisRequirementsPayload | null>(null);
  const [selectedForm, setSelectedForm] = useState("form_i485");
  const [message, setMessage] = useState<string | null>("Loading tasks.");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const searchParams = new URLSearchParams(window.location.search);
        const explicitCaseId = searchParams.get("caseId");
        const savedCaseId = explicitCaseId || getSavedCaseId();
        const [cases, loadedRequirements] = await Promise.all([listCases(), getUscisRequirements()]);
        const activeCase = cases.find((entry) => entry.id === savedCaseId) || cases[0] || null;

        if (cancelled) {
          return;
        }

        setCaseSummary(activeCase);
        setRequirements(loadedRequirements);

        if (!activeCase) {
          setMessage(null);
          return;
        }

        rememberCaseId(activeCase.id);
        const [loadedChecklist, loadedUploads] = await Promise.all([
          getChecklist(activeCase.id).catch(() => null),
          listUploads(activeCase.id).catch(() => []),
        ]);
        setAttachedCodes(new Set(loadedUploads.flatMap(getSatisfiedChecklistCodes)));
        if (cancelled) {
          return;
        }
        setChecklist(loadedChecklist?.items ?? []);
        setMessage(null);
      } catch (error) {
        if (!cancelled) {
          setMessage(error instanceof Error ? error.message : "Could not load task data.");
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const checklistByCode = useMemo(() => {
    return Object.fromEntries(checklist.map((item) => [item.code, item] as const));
  }, [checklist]);

  const formPlans = useMemo(() => {
    return (requirements?.forms ?? [])
      .filter((form) => FORM_FILTERS.some((filter) => filter.code === form.code))
      .map((form) => {
        const tasks = form.initial_evidence
          .map((entry) => ({
            ...entry,
            item: checklistByCode[entry.checklist_code],
          }))
          .filter((entry) => entry.item?.applicability !== "not_applicable");
        const requiredTasks = tasks.filter((task) => task.necessity === "required" || task.item?.applicability === "required");
        const doneRequired = requiredTasks.filter((task) => isDone(task.item)).length;
        return {
          ...form,
          tasks,
          requiredCount: requiredTasks.length,
          doneRequired,
        };
      });
  }, [checklistByCode, requirements]);

  const selectedPlan =
    formPlans.find((plan) => plan.code === selectedForm) || formPlans[0] || null;

  function toggleTask(item: ChecklistItem | undefined) {
    if (!caseSummary || !item) {
      return;
    }

    const nextStatus: ChecklistWorkflowStatus = isDone(item) ? "not_started" : "complete";
    const previousChecklist = checklist;

    setChecklist((current) =>
      current.map((entry) => (entry.id === item.id ? { ...entry, completion_status: nextStatus } : entry)),
    );

    startTransition(() => {
      updateChecklistItem(item.id, nextStatus)
        .then(() => getChecklist(caseSummary.id))
        .then((payload) => {
          setChecklist(payload.items);
          setMessage("Task status updated.");
        })
        .catch((error) => {
          setChecklist(previousChecklist);
          setMessage(error instanceof Error ? error.message : "Could not update task status.");
        });
    });
  }

  // Count each checklist item once, even when several forms need it.
  const requiredItems = checklist.filter((item) => item.applicability === "required");
  const totalRequired = requiredItems.length;
  const totalDone = requiredItems.filter((item) => isDone(item)).length;
  const tickedWithoutFile = checklist.filter((item) => isDone(item) && isEvidenceItem(item) && !attachedCodes.has(item.code)).length;

  return (
    <AppShell step="checklist" caseId={caseSummary?.id} caseName={caseSummary?.case_name} readinessLabel={caseSummary?.readiness_label}>
      <PageHeader
        eyebrow="Step 3"
        title="Checklist"
        description="Everything each form needs, from the checklist Lucy built for your answers. Tick items off as you collect them. Only attached files go into the printed packet, so attach each one on the Print packet step."
      />

      <StatusMessage message={message} />

      {caseSummary && !checklist.length ? (
        <Notice
          tone="warning"
          title="No checklist yet"
          actions={
            <Link href={`/review?caseId=${encodeURIComponent(caseSummary.id)}`} className={buttonClass("primary", "sm")}>
              Build it on the Review page
            </Link>
          }
        >
          Finish the prescreen, then build the checklist from your saved answers.
        </Notice>
      ) : null}

      {!caseSummary && message !== "Loading tasks." ? (
        <Notice
          title="No case open"
          actions={
            <Link href="/prescreen" className={buttonClass("primary", "sm")}>
              Start a case
            </Link>
          }
        >
          <p>Open a saved case, or start a new one from the prescreen to get a checklist.</p>
          <div className="mt-3 max-w-sm">
            <CaseSelector
              selectedCaseId=""
              onSelect={(nextCase) => window.location.assign(`/manage-tasks?caseId=${encodeURIComponent(nextCase.id)}`)}
              label="Saved cases"
            />
          </div>
        </Notice>
      ) : null}

      {formPlans.length ? (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
          <Card as="aside" className="h-fit p-3 md:p-3">
            <div className="px-2 pb-3 pt-1">
              <div className="flex items-center justify-between text-xs font-semibold text-muted">
                <span>Required items done</span>
                <span className="whitespace-nowrap tabular-nums">
                  {totalDone} of {totalRequired}
                </span>
              </div>
              <ProgressBar
                value={totalRequired ? (totalDone / totalRequired) * 100 : 0}
                label="All required checklist items done"
                className="mt-1.5"
              />
            </div>
            <div role="tablist" aria-label="Forms" aria-orientation="vertical" className="grid grid-cols-2 gap-1 sm:grid-cols-3 lg:flex lg:flex-col">
              {FORM_FILTERS.map((form) => {
                const plan = formPlans.find((entry) => entry.code === form.code);
                const isSelected = selectedForm === form.code;
                const complete = plan ? plan.requiredCount > 0 && plan.doneRequired === plan.requiredCount : false;
                return (
                  <button
                    key={form.code}
                    type="button"
                    role="tab"
                    aria-selected={isSelected}
                    onClick={() => setSelectedForm(form.code)}
                    className={classNames(
                      "flex items-center justify-between gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors",
                      isSelected ? "bg-pine-soft text-pine-strong" : "text-ink hover:bg-paper",
                    )}
                  >
                    <span className="font-semibold">{form.label}</span>
                    <span className="whitespace-nowrap text-xs font-semibold tabular-nums text-muted">
                      {plan?.requiredCount ? (
                        complete ? (
                          <span className="text-pine">Done</span>
                        ) : (
                          `${plan.doneRequired}/${plan.requiredCount}`
                        )
                      ) : (
                        "Optional"
                      )}
                    </span>
                  </button>
                );
              })}
            </div>
          </Card>

          {selectedPlan ? (
            <Card aria-labelledby="plan-heading">
              <SectionHeader
                id="plan-heading"
                title={selectedPlan.label}
                description={selectedPlan.summary}
                actions={
                  selectedPlan.requiredCount ? (
                    <Badge tone={selectedPlan.doneRequired === selectedPlan.requiredCount ? "success" : "neutral"}>
                      {selectedPlan.doneRequired} of {selectedPlan.requiredCount} required done
                    </Badge>
                  ) : null
                }
              />

              {selectedPlan.tasks.length ? (
                <ul className="mt-5 divide-y divide-line overflow-hidden rounded-lg border border-line">
                  {selectedPlan.tasks.map((task) => {
                    const checked = isDone(task.item);
                    const necessity = task.item ? task.item.applicability : task.necessity;
                    return (
                      <li key={`${selectedPlan.code}-${task.checklist_code}`}>
                        <label
                          className={classNames(
                            "grid cursor-pointer grid-cols-[auto_1fr] items-start gap-3 px-4 py-3.5 transition-colors hover:bg-paper",
                            !task.item || isPending ? "cursor-not-allowed" : "",
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={!task.item || isPending}
                            onChange={() => toggleTask(task.item)}
                            className="mt-0.5 h-5 w-5 rounded border-line-strong"
                          />
                          <span className="min-w-0">
                            <span className="flex flex-wrap items-center gap-2">
                              <span className="font-semibold text-ink">
                                {task.label}
                              </span>
                              <Badge tone={necessity === "required" ? "strong" : "neutral"} className="capitalize">
                                {formatStatus(necessity)}
                              </Badge>
                              {task.item && isEvidenceItem(task.item) && !attachedCodes.has(task.item.code) ? (
                                <>
                                  <Badge tone={checked ? "warning" : "neutral"}>{checked ? "Ticked, no file attached" : "No file yet"}</Badge>
                                  <Link
                                    href={`/packet-assembly?caseId=${encodeURIComponent(caseSummary?.id ?? "")}#evidence-heading`}
                                    className="text-xs font-semibold text-pine underline-offset-4 hover:underline"
                                  >
                                    Attach file
                                  </Link>
                                </>
                              ) : null}
                              {task.item && !checked && task.item.completion_status !== "not_started" ? (
                                <Badge className="capitalize">{formatStatus(task.item.completion_status)}</Badge>
                              ) : null}
                            </span>
                            <span className="mt-1 block text-sm leading-6 text-muted">
                              {task.item?.what_to_save_now || task.notes || "Review and collect this item for the selected form."}
                            </span>
                          </span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <Notice className="mt-5">No checklist tasks are available for this form yet.</Notice>
              )}
            </Card>
          ) : null}
        </div>
      ) : null}

      {caseSummary && checklist.length ? (
        <div className="flex flex-col items-start justify-between gap-3 border-t border-line pt-6 sm:flex-row sm:items-center">
          <p className="text-sm text-muted">
            {totalDone === totalRequired ? "Every required item is ticked." : `${totalRequired - totalDone} required items left to tick.`}
            {tickedWithoutFile
              ? ` ${tickedWithoutFile} ticked ${tickedWithoutFile === 1 ? "item has" : "items have"} no file yet; attach ${tickedWithoutFile === 1 ? "it" : "them"} on the Print packet step.`
              : ""}{" "}
            Next, review the packet for issues.
          </p>
          <Link href={`/review?caseId=${encodeURIComponent(caseSummary.id)}`} className={buttonClass("primary", "md")}>
            Continue to review <span aria-hidden="true">{"\u2192"}</span>
          </Link>
        </div>
      ) : null}
    </AppShell>
  );
}

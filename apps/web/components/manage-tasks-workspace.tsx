"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, useTransition } from "react";

import { getChecklist, getUscisRequirements, listCases, updateChecklistItem } from "@/lib/api";
import { getSavedCaseId, rememberCaseId } from "@/lib/case-storage";
import type {
  CaseSummary,
  ChecklistItem,
  ChecklistWorkflowStatus,
  UscisRequirementsPayload,
} from "@/lib/types";

const FORM_FILTERS = [
  { code: "form_i485", label: "I-485" },
  { code: "form_i765", label: "I-765" },
  { code: "form_i131", label: "I-131" },
  { code: "form_i864", label: "I-864" },
  { code: "form_i130", label: "I-130" },
  { code: "form_i130a", label: "I-130A" },
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
  const [requirements, setRequirements] = useState<UscisRequirementsPayload | null>(null);
  const [selectedForm, setSelectedForm] = useState(FORM_FILTERS[0].code);
  const [message, setMessage] = useState("Loading tasks.");
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
          setMessage("No case exists yet. Open the current case workspace and create one first.");
          return;
        }

        rememberCaseId(activeCase.id);
        const loadedChecklist = await getChecklist(activeCase.id).catch(() => null);
        if (cancelled) {
          return;
        }
        setChecklist(loadedChecklist?.items ?? []);
        setMessage(
          loadedChecklist?.items.length
            ? "Use the checkboxes to manually track what is done."
            : "No generated checklist was found yet. Generate it from the current case workspace first.",
        );
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

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 py-6 text-ink md:px-8 md:py-8">
      <nav className="flex flex-col gap-3 border-b border-ink/10 pb-5 md:flex-row md:items-center md:justify-between">
        <Link href="/" className="font-display text-2xl">
          Lucy
        </Link>
        <div className="flex flex-wrap gap-2">
          <Link className="rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm font-semibold" href="/prescreen">
            Prescreen
          </Link>
          <Link className="rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm font-semibold" href="/packet-assembly">
            Packet assembly
          </Link>
        </div>
      </nav>

      <section className="grid gap-5 border-b border-ink/10 py-6 lg:grid-cols-[1fr_auto] lg:items-end">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-pine">Manage tasks</p>
          <h1 className="mt-3 font-display text-4xl leading-tight md:text-5xl">
            A simple form-by-form checklist.
          </h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-ink/70">
            This page hides the larger board-style workspace and gives you direct checkboxes for the form,
            document, and supporting evidence tasks already generated by the backend checklist.
          </p>
        </div>
        <div className="rounded-lg border border-ink/10 bg-white px-4 py-3 text-sm">
          <p className="text-xs uppercase tracking-[0.16em] text-ink/50">Selected case</p>
          <p className="mt-1 font-semibold">{caseSummary?.case_name ?? "None loaded"}</p>
        </div>
      </section>

      <section className="rounded-lg border border-ink/10 bg-white p-5">
        <div className="flex flex-wrap gap-2">
          {FORM_FILTERS.map((form) => {
            const plan = formPlans.find((entry) => entry.code === form.code);
            const pct = plan?.requiredCount ? Math.round((plan.doneRequired / plan.requiredCount) * 100) : 0;
            return (
              <button
                key={form.code}
                type="button"
                onClick={() => setSelectedForm(form.code)}
                className={classNames(
                  "rounded-lg border px-4 py-3 text-left text-sm font-semibold",
                  selectedForm === form.code ? "border-ink bg-ink text-white" : "border-ink/15 bg-white text-ink",
                )}
              >
                <span className="block">{form.label}</span>
                <span className={classNames("mt-1 block text-xs", selectedForm === form.code ? "text-white/70" : "text-ink/55")}>
                  {pct}% required
                </span>
              </button>
            );
          })}
        </div>
        <p className="mt-4 rounded-lg border border-ink/10 bg-paper/65 px-4 py-3 text-sm text-ink/70">{message}</p>
      </section>

      {selectedPlan ? (
        <section className="rounded-lg border border-ink/10 bg-white p-5">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-pine">{selectedPlan.code}</p>
              <h2 className="mt-1 text-2xl font-semibold">{selectedPlan.label}</h2>
              <p className="mt-2 max-w-3xl text-sm leading-7 text-ink/68">{selectedPlan.summary}</p>
            </div>
            <div className="rounded-lg bg-paper px-4 py-3 text-sm">
              <p className="text-xs uppercase tracking-[0.16em] text-ink/50">Required done</p>
              <p className="mt-1 text-xl font-semibold">
                {selectedPlan.doneRequired}/{selectedPlan.requiredCount}
              </p>
            </div>
          </div>

          <div className="mt-5 grid gap-3">
            {selectedPlan.tasks.length ? (
              selectedPlan.tasks.map((task) => {
                const checked = isDone(task.item);
                return (
                  <label
                    key={`${selectedPlan.code}-${task.checklist_code}`}
                    className="grid gap-3 rounded-lg border border-ink/10 bg-paper/45 p-4 md:grid-cols-[auto_1fr] md:items-start"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={!task.item || isPending}
                      onChange={() => toggleTask(task.item)}
                      className="mt-1 h-5 w-5 rounded border-ink/30 text-pine"
                    />
                    <span>
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold">{task.label}</span>
                        <span className="rounded-full bg-white px-2 py-1 text-xs uppercase tracking-[0.12em] text-ink/55">
                          {task.item ? formatStatus(task.item.applicability) : task.necessity}
                        </span>
                        {task.item ? (
                          <span className="rounded-full bg-white px-2 py-1 text-xs uppercase tracking-[0.12em] text-ink/55">
                            {formatStatus(task.item.completion_status)}
                          </span>
                        ) : null}
                      </span>
                      <span className="mt-2 block text-sm leading-7 text-ink/68">
                        {task.item?.what_to_save_now || task.notes || "Review and collect this item for the selected form."}
                      </span>
                    </span>
                  </label>
                );
              })
            ) : (
              <p className="rounded-lg border border-ink/10 bg-paper/65 p-4 text-sm text-ink/70">
                No checklist tasks are available for this form yet.
              </p>
            )}
          </div>
        </section>
      ) : null}
    </main>
  );
}

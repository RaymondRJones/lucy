"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, useTransition } from "react";

import { CaseSelector } from "@/components/case-selector";
import { generateChecklist, getCase, getChecklist, getPrescreenState, getQa, listUploads, runQa } from "@/lib/api";
import { getSavedCaseId, rememberCaseId } from "@/lib/case-storage";
import type { CaseSummary, ChecklistItem, PrescreenState, QaResults, UploadRecord } from "@/lib/types";
const DONE_STATUSES = new Set(["uploaded", "almost_done", "approved", "complete"]);

function classNames(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

function actionHref(baseHref: string, caseId: string) {
  const separator = baseHref.includes("?") ? "&" : "?";
  return `${baseHref}${separator}caseId=${encodeURIComponent(caseId)}`;
}

function isDone(item: ChecklistItem) {
  return DONE_STATUSES.has(item.completion_status);
}

export function ReviewWorkspace() {
  const [caseSummary, setCaseSummary] = useState<CaseSummary | null>(null);
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [uploads, setUploads] = useState<UploadRecord[]>([]);
  const [qa, setQa] = useState<QaResults | null>(null);
  const [prescreen, setPrescreen] = useState<PrescreenState | null>(null);
  const [message, setMessage] = useState("Load a case to review the packet.");
  const [isPending, startTransition] = useTransition();

  const loadCase = useCallback(async (caseId: string, successMessage: string) => {
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
    }
  }, []);

  useEffect(() => {
    const caseId = new URLSearchParams(window.location.search).get("caseId") || getSavedCaseId();
    if (caseId) {
      void loadCase(caseId, "Review state loaded.");
    }
  }, [loadCase]);

  const requiredItems = checklist.filter((item) => item.applicability === "required");
  const completedRequired = requiredItems.filter(isDone).length;
  const checklistPct = requiredItems.length ? Math.round((completedRequired / requiredItems.length) * 100) : 0;
  const flags = prescreen?.evaluation.flags ?? [];
  const criticalFlags = flags.filter((flag) => flag.severity === "critical");
  const missingRequired = requiredItems.filter((item) => !isDone(item)).slice(0, 6);

  const reviewStatus = useMemo(() => {
    if (!caseSummary) {
      return "No case";
    }
    if (criticalFlags.length) {
      return "Review needed";
    }
    if (!checklist.length) {
      return "Checklist not generated";
    }
    if (checklistPct < 100) {
      return "Collecting evidence";
    }
    return "Ready for final check";
  }, [caseSummary, checklist.length, checklistPct, criticalFlags.length]);

  function handleCaseSelect(nextCase: CaseSummary) {
    startTransition(() => {
      void loadCase(nextCase.id, `Loaded ${nextCase.case_name}.`);
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
          setMessage("Checklist regenerated from the saved intake branch.");
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
          setMessage("Review checks finished.");
        } catch (error) {
          setMessage(error instanceof Error ? error.message : "Could not run review checks.");
        }
      })();
    });
  }

  return (
    <main className="min-h-screen bg-[#f7f7f2] text-zinc-950">
      <div className="mx-auto grid w-full max-w-7xl gap-6 px-4 py-5 lg:grid-cols-[280px_1fr]">
        <aside className="rounded-lg border border-zinc-200 bg-white p-4">
          <Link href="/" className="block text-lg font-bold">
            Lucy
          </Link>
          <p className="mt-1 text-sm text-zinc-600">Checklist, review, and document handoff</p>
          <div className="mt-4 grid gap-2 text-sm font-semibold">
            <Link href="/" className="rounded-lg border border-zinc-200 px-3 py-2 text-zinc-700 hover:border-emerald-700">
              Landing
            </Link>
            <Link
              href={caseSummary ? actionHref("/prescreen", caseSummary.id) : "/prescreen"}
              className="rounded-lg border border-zinc-200 px-3 py-2 text-zinc-700 hover:border-emerald-700"
            >
              Prescreen
            </Link>
            <Link href="/review" className="rounded-lg border border-emerald-700 bg-emerald-50 px-3 py-2 text-emerald-900">
              Checklist + review
            </Link>
          </div>
          <div className="mt-5">
            <CaseSelector selectedCaseId={caseSummary?.id ?? ""} onSelect={handleCaseSelect} disabled={isPending} label="Case" />
          </div>
          <div className="mt-5 rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-700">
            <p className="font-semibold text-zinc-950">Saved progress</p>
            <p className="mt-1">{caseSummary ? "This case is saved locally and can be resumed from the landing page." : "No case loaded yet."}</p>
          </div>
        </aside>

        <section className="grid gap-6">
          <section className="rounded-lg border border-zinc-200 bg-white p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-700">Checklist + review</p>
                <h1 className="mt-2 text-3xl font-bold tracking-normal md:text-4xl">Review the packet before generation.</h1>
                <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-600">
                  Check the branch flags, required evidence, uploads, and QA results before opening packet assembly.
                </p>
              </div>
              <div className="min-w-56 rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-zinc-500">Status</p>
                <p className="mt-2 text-2xl font-bold">{reviewStatus}</p>
                <p className="mt-2 text-xs text-zinc-600">{completedRequired}/{requiredItems.length} required checklist items done</p>
              </div>
            </div>
            <div className="mt-4 rounded-lg border border-zinc-200 bg-[#fbfbf8] px-3 py-2 text-sm text-zinc-700">
              {message}
            </div>
          </section>

          <section className="grid gap-4 md:grid-cols-4">
            {[
              { label: "Checklist", value: `${checklistPct}%`, detail: "required evidence done" },
              { label: "Uploads", value: String(uploads.length), detail: "files linked" },
              { label: "QA issues", value: String(qa?.issues.filter((issue) => !issue.is_resolved).length ?? 0), detail: "open review items" },
              { label: "Branch flags", value: String(flags.length), detail: criticalFlags.length ? "critical review present" : "from intake" },
            ].map((metric) => (
              <div key={metric.label} className="rounded-lg border border-zinc-200 bg-white p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-zinc-500">{metric.label}</p>
                <p className="mt-2 text-2xl font-bold">{metric.value}</p>
                <p className="mt-1 text-sm text-zinc-600">{metric.detail}</p>
              </div>
            ))}
          </section>

          <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className="grid gap-6">
              {flags.length ? (
                <section className="rounded-lg border border-amber-200 bg-amber-50 p-5">
                  <h2 className="text-xl font-bold text-amber-950">Review flags</h2>
                  <div className="mt-4 grid gap-3">
                    {flags.map((flag) => (
                      <div key={flag.code} className="rounded-lg border border-amber-200 bg-white p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold text-amber-950">{flag.title}</p>
                          <span
                            className={classNames(
                              "rounded-lg px-2 py-1 text-xs font-semibold uppercase tracking-[0.12em]",
                              flag.severity === "critical" ? "bg-red-100 text-red-800" : "bg-amber-100 text-amber-900",
                            )}
                          >
                            {flag.severity}
                          </span>
                        </div>
                        <p className="mt-1 text-xs leading-5 text-amber-900">{flag.description}</p>
                      </div>
                    ))}
                  </div>
                </section>
              ) : null}

              <section className="rounded-lg border border-zinc-200 bg-white p-5">
                <h2 className="text-xl font-bold">Required checklist items</h2>
                <div className="mt-4 h-2 overflow-hidden rounded bg-zinc-200">
                  <div className="h-full rounded bg-emerald-700" style={{ width: `${checklistPct}%` }} />
                </div>
                <div className="mt-4 grid gap-3">
                  {missingRequired.length ? (
                    missingRequired.map((item) => (
                      <div key={item.id} className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
                        <p className="text-sm font-semibold">{item.label}</p>
                        <p className="mt-1 text-xs leading-5 text-zinc-600">{item.what_to_save_now}</p>
                      </div>
                    ))
                  ) : (
                    <p className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-600">
                      Required checklist items are either done or not generated yet.
                    </p>
                  )}
                </div>
              </section>
            </div>

            <aside className="grid gap-4">
              <section className="rounded-lg border border-zinc-200 bg-white p-4">
                <h2 className="font-bold">Review actions</h2>
                <div className="mt-3 grid gap-2">
                  <button
                    type="button"
                    onClick={handleGenerateChecklist}
                    disabled={!caseSummary || isPending}
                    className="rounded-lg bg-zinc-950 px-4 py-3 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:opacity-60"
                  >
                    Generate checklist
                  </button>
                  <button
                    type="button"
                    onClick={handleRunQa}
                    disabled={!caseSummary || isPending}
                    className="rounded-lg border border-zinc-200 px-4 py-3 text-sm font-semibold transition hover:border-emerald-700 disabled:opacity-60"
                  >
                    Run review checks
                  </button>
                  <Link
                    href={caseSummary ? actionHref("/packet-assembly", caseSummary.id) : "/packet-assembly"}
                    className="rounded-lg border border-zinc-200 px-4 py-3 text-sm font-semibold transition hover:border-emerald-700"
                  >
                    Generate documents
                  </Link>
                </div>
              </section>

              <section className="rounded-lg border border-zinc-200 bg-white p-4">
                <h2 className="font-bold">Continue collecting</h2>
                <div className="mt-3 grid gap-2">
                  <Link
                    href={caseSummary ? actionHref("/prescreen", caseSummary.id) : "/prescreen"}
                    className="rounded-lg border border-zinc-200 px-4 py-3 text-sm font-semibold transition hover:border-emerald-700"
                  >
                    Back to questions
                  </Link>
                  <Link
                    href={caseSummary ? actionHref("/manage-tasks", caseSummary.id) : "/manage-tasks"}
                    className="rounded-lg border border-zinc-200 px-4 py-3 text-sm font-semibold transition hover:border-emerald-700"
                  >
                    Detailed task board
                  </Link>
                </div>
              </section>
            </aside>
          </section>
        </section>
      </div>
    </main>
  );
}

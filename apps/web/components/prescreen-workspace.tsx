"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState, useTransition } from "react";

import { CaseSelector } from "@/components/case-selector";
import {
  createCase,
  generateChecklist,
  getCase,
  getPrescreenQuestionnaire,
  getPrescreenState,
  savePrescreenAnswers,
} from "@/lib/api";
import { getSavedCaseId, rememberCaseId } from "@/lib/case-storage";
import { packetFormHref, packetFormsForIncluded } from "@/lib/packet-form-flow";
import type { CaseSummary, PrescreenFlag, PrescreenQuestion, PrescreenQuestionnaire, PrescreenState } from "@/lib/types";

const DEFAULT_CASE_FORM = {
  case_name: "Lucy marriage packet",
  petitioner_email: "",
  beneficiary_email: "",
  country_of_focus: "Colombia",
};

const FORM_ACTIONS: Record<string, { label: string; href: string; detail: string; phase: string }> = {
  form_i130: { label: "I-130", href: "/form-ingestion?form=i130", detail: "Spouse petition", phase: "Petition" },
  form_i130a: {
    label: "I-130A",
    href: "/form-ingestion?form=i130a",
    detail: "Spouse biographic supplement",
    phase: "Petition",
  },
  form_i485: { label: "I-485", href: "/i485-ingestion", detail: "Adjustment application", phase: "Green card" },
  form_i864: { label: "I-864", href: "/form-ingestion?form=i864", detail: "Sponsor support", phase: "Financial" },
  form_g1145: { label: "G-1145", href: "/review", detail: "Optional e-notification", phase: "Packet" },
  form_i765: { label: "I-765", href: "/form-ingestion?form=i765", detail: "Work authorization", phase: "Optional" },
  form_i131: { label: "I-131", href: "/form-ingestion?form=i131", detail: "Advance parole", phase: "Optional" },
};

type PrescreenPage = {
  id: string;
  title: string;
  questions: PrescreenQuestion[];
  answered: number;
  total: number;
};

function classNames(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

function fieldValue(value: unknown) {
  if (typeof value === "string" || typeof value === "number") {
    return String(value);
  }
  return "";
}

function hasAnswer(value: unknown): boolean {
  if (value === null || value === undefined) {
    return false;
  }
  if (typeof value === "string") {
    return value.trim() !== "";
  }
  if (Array.isArray(value)) {
    return value.length > 0;
  }
  if (typeof value === "object") {
    return Object.values(value).some(hasAnswer);
  }
  return true;
}

function questionHasAnswer(question: PrescreenQuestion, value: unknown) {
  if (question.answer_type !== "field_group") {
    return hasAnswer(value);
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  const requiredFields = (question.fields ?? []).filter((field) => field.required !== false);
  if (!requiredFields.length) {
    return hasAnswer(value);
  }
  const groupedValue = value as Record<string, unknown>;
  return requiredFields.every((field) => hasAnswer(groupedValue[field.key]));
}

function normalizeAnswer(question: PrescreenQuestion, value: unknown) {
  if (question.answer_type === "number" && value !== "") {
    return Number(value);
  }
  if (question.answer_type === "field_group" && value && typeof value === "object" && !Array.isArray(value)) {
    return Object.fromEntries(
      Object.entries(value).map(([key, entry]) => {
        const field = question.fields?.find((candidate) => candidate.key === key);
        if (field?.type === "number" && entry !== "") {
          return [key, Number(entry)];
        }
        return [key, entry];
      }),
    );
  }
  return value;
}

function formatStatus(value: string) {
  return value.replaceAll("_", " ");
}

function actionHref(baseHref: string, caseId: string) {
  const separator = baseHref.includes("?") ? "&" : "?";
  return `${baseHref}${separator}caseId=${encodeURIComponent(caseId)}`;
}

function sourceLabel(source: string | undefined) {
  if (!source) {
    return null;
  }
  if (source === "legacy_case_fact") {
    return "Smart default from saved case facts";
  }
  return `Smart default from ${source.replaceAll("_", " ")}`;
}

function flagTone(flag: PrescreenFlag) {
  if (flag.severity === "critical") {
    return "border-red-200 bg-red-50 text-red-950";
  }
  if (flag.category === "packet_readiness") {
    return "border-sand/60 bg-sand/15 text-ink";
  }
  return "border-amber-200 bg-amber-50 text-amber-950";
}

function QuestionHelpButton({ question }: { question: PrescreenQuestion }) {
  if (!question.why && !question.help_text) {
    return null;
  }
  return (
    <span className="group/help relative inline-flex">
      <button
        type="button"
        aria-label={`More context for ${question.label}`}
        className="flex h-6 w-6 items-center justify-center rounded-full border border-pine/35 bg-white text-xs font-bold text-pine transition hover:border-pine focus:border-pine"
      >
        ?
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute right-0 top-8 z-20 hidden w-80 max-w-[calc(100vw-3rem)] rounded-lg border border-ink/15 bg-white p-3 text-left text-xs font-normal leading-5 text-ink shadow-lg group-focus-within/help:block group-hover/help:block"
      >
        <span className="block font-semibold text-ink">Why we ask this</span>
        <span className="mt-1 block">{question.why || question.help_text}</span>
      </span>
    </span>
  );
}

function QuestionControl({
  question,
  value,
  onChange,
}: {
  question: PrescreenQuestion;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  function groupValue() {
    return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
  }

  function updateGroupField(fieldKey: string, nextValue: unknown) {
    onChange({ ...groupValue(), [fieldKey]: nextValue });
  }

  function renderBooleanButtons(currentValue: unknown, onValueChange: (nextValue: boolean) => void) {
    return (
      <div className="grid gap-2 sm:grid-cols-2">
        {[
          { value: true, label: "Yes" },
          { value: false, label: "No" },
        ].map((option) => (
          <button
            key={option.label}
            type="button"
            onClick={() => onValueChange(option.value)}
            className={classNames(
              "min-h-11 rounded-lg border px-3 py-2 text-left text-sm font-semibold transition",
              currentValue === option.value
                ? "border-pine bg-pine text-white"
                : "border-ink/15 bg-white text-ink hover:border-pine/45",
            )}
          >
            {option.label}
          </button>
        ))}
      </div>
    );
  }

  if (question.answer_type === "boolean") {
    return renderBooleanButtons(value, onChange);
  }

  if (question.answer_type === "select") {
    return (
      <select
        value={fieldValue(value)}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 w-full rounded-lg border border-ink/15 bg-white px-3 text-sm text-ink focus:border-pine"
      >
        <option value="">Select</option>
        {question.options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    );
  }

  if (question.answer_type === "multi_select") {
    const selected = Array.isArray(value) ? value.map(String) : [];
    return (
      <div className="grid gap-2 sm:grid-cols-2">
        {question.options.map((option) => {
          const isSelected = selected.includes(option.value);
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => {
                const nextValue =
                  option.value === "none"
                    ? isSelected
                      ? []
                      : ["none"]
                    : isSelected
                      ? selected.filter((entry) => entry !== option.value)
                      : [...selected.filter((entry) => entry !== "none"), option.value];
                onChange(nextValue);
              }}
              className={classNames(
                "grid min-h-11 grid-cols-[auto_1fr] items-start gap-2 rounded-lg border px-3 py-2 text-left text-sm font-semibold transition",
                isSelected
                  ? "border-pine bg-mist text-ink"
                  : "border-ink/15 bg-white text-ink hover:border-pine/45",
              )}
            >
              <span className={classNames("mt-1 h-3.5 w-3.5 rounded border", isSelected ? "border-pine bg-pine" : "border-ink/25")} />
              <span>{option.label}</span>
            </button>
          );
        })}
      </div>
    );
  }

  if (question.answer_type === "textarea") {
    return (
      <textarea
        value={fieldValue(value)}
        onChange={(event) => onChange(event.target.value)}
        rows={5}
        className="min-h-28 w-full rounded-lg border border-ink/15 bg-white px-3 py-3 text-sm leading-6 text-ink focus:border-pine"
      />
    );
  }

  if (question.answer_type === "field_group") {
    const currentGroup = groupValue();
    return (
      <div className="grid gap-3 md:grid-cols-2">
        {(question.fields ?? []).map((field) => {
          const currentValue = currentGroup[field.key];
          if (field.type === "boolean") {
            return (
              <div key={field.key} className="grid gap-1 md:col-span-2">
                <span className="text-xs font-semibold text-ink/65">
                  {field.label}
                  {field.required === false ? <span className="font-normal text-ink/45"> optional</span> : null}
                </span>
                {renderBooleanButtons(currentValue, (nextValue) => updateGroupField(field.key, nextValue))}
              </div>
            );
          }

          if (field.type === "select") {
            return (
              <label key={field.key} className="grid gap-1">
                <span className="text-xs font-semibold text-ink/65">
                  {field.label}
                  {field.required === false ? <span className="font-normal text-ink/45"> optional</span> : null}
                </span>
                <select
                  value={fieldValue(currentValue)}
                  onChange={(event) => updateGroupField(field.key, event.target.value)}
                  className="h-10 w-full rounded-lg border border-ink/15 bg-white px-3 text-sm text-ink focus:border-pine"
                >
                  <option value="">Select</option>
                  {(field.options ?? []).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            );
          }

          if (field.type === "textarea") {
            return (
              <label key={field.key} className="grid gap-1 md:col-span-2">
                <span className="text-xs font-semibold text-ink/65">
                  {field.label}
                  {field.required === false ? <span className="font-normal text-ink/45"> optional</span> : null}
                </span>
                <textarea
                  value={fieldValue(currentValue)}
                  onChange={(event) => updateGroupField(field.key, event.target.value)}
                  rows={4}
                  className="min-h-24 w-full rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm leading-6 text-ink focus:border-pine"
                />
              </label>
            );
          }

          const inputType = field.type === "date" ? "date" : field.type === "number" ? "number" : "text";
          return (
            <label key={field.key} className="grid gap-1">
              <span className="text-xs font-semibold text-ink/65">
                {field.label}
                {field.required === false ? <span className="font-normal text-ink/45"> optional</span> : null}
              </span>
              <input
                type={inputType}
                value={fieldValue(currentValue)}
                placeholder={field.placeholder}
                onChange={(event) => updateGroupField(field.key, event.target.value)}
                className="h-10 w-full rounded-lg border border-ink/15 bg-white px-3 text-sm text-ink focus:border-pine"
              />
            </label>
          );
        })}
      </div>
    );
  }

  const inputType = question.answer_type === "date" ? "date" : question.answer_type === "number" ? "number" : "text";
  return (
    <input
      type={inputType}
      value={fieldValue(value)}
      onChange={(event) => onChange(event.target.value)}
      className="h-10 w-full rounded-lg border border-ink/15 bg-white px-3 text-sm text-ink focus:border-pine"
    />
  );
}

export function PrescreenWorkspace() {
  const [caseSummary, setCaseSummary] = useState<CaseSummary | null>(null);
  const [caseForm, setCaseForm] = useState(DEFAULT_CASE_FORM);
  const [questionnaire, setQuestionnaire] = useState<PrescreenQuestionnaire | null>(null);
  const [prescreen, setPrescreen] = useState<PrescreenState | null>(null);
  const [selectedPageId, setSelectedPageId] = useState("");
  const [draftAnswers, setDraftAnswers] = useState<Record<string, unknown>>({});
  const [message, setMessage] = useState<string | null>("Create or select a case to start the prescreen questions.");
  const [isPending, startTransition] = useTransition();

  const loadCase = useCallback(async (caseId: string, successMessage: string) => {
    try {
      const [loadedCase, loadedPrescreen] = await Promise.all([getCase(caseId), getPrescreenState(caseId)]);
      rememberCaseId(caseId);
      const url = new URL(window.location.href);
      url.searchParams.set("caseId", caseId);
      window.history.replaceState({}, "", url);
      setCaseSummary(loadedCase);
      setPrescreen(loadedPrescreen);
      setDraftAnswers(loadedPrescreen.answers);
      setMessage(successMessage);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not load this case.");
    }
  }, []);

  useEffect(() => {
    getPrescreenQuestionnaire()
      .then(setQuestionnaire)
      .catch((error) => setMessage(error instanceof Error ? error.message : "Could not load prescreen content."));
  }, []);

  useEffect(() => {
    const storedCaseId = new URLSearchParams(window.location.search).get("caseId") || getSavedCaseId();
    if (storedCaseId) {
      void loadCase(storedCaseId, "Loaded saved prescreen answers.");
    }
  }, [loadCase]);

  const visibleQuestions = useMemo(() => prescreen?.evaluation.visible_questions ?? [], [prescreen]);
  const flags = prescreen?.evaluation.flags ?? [];
  const eliminatedForms = prescreen?.evaluation.eliminated_forms ?? [];
  const includedForms = useMemo(() => prescreen?.evaluation.included_forms ?? [], [prescreen?.evaluation.included_forms]);
  const missingQuestions = visibleQuestions.filter((question) => !questionHasAnswer(question, draftAnswers[question.id]));
  const nextFormOptions = useMemo(() => packetFormsForIncluded(includedForms), [includedForms]);
  const suggestedFormCode = nextFormOptions[0]?.formCode ?? null;

  const pages = useMemo<PrescreenPage[]>(() => {
    const bySection = new Map<string, PrescreenQuestion[]>();
    for (const question of visibleQuestions) {
      bySection.set(question.section, [...(bySection.get(question.section) ?? []), question]);
    }
    return Array.from(bySection.entries()).map(([section, questions]) => ({
      id: section,
      title: section,
      questions,
      answered: questions.filter((question) => questionHasAnswer(question, draftAnswers[question.id])).length,
      total: questions.length,
    }));
  }, [draftAnswers, visibleQuestions]);

  useEffect(() => {
    if (!pages.length) {
      return;
    }
    if (selectedPageId && pages.some((page) => page.id === selectedPageId)) {
      return;
    }
    const firstIncomplete = pages.find((page) => page.answered < page.total);
    setSelectedPageId((firstIncomplete ?? pages[0]).id);
  }, [pages, selectedPageId]);

  const selectedPage = pages.find((page) => page.id === selectedPageId) ?? pages[0] ?? null;
  const selectedQuestionIds = new Set(selectedPage?.questions.map((question) => question.id) ?? []);
  const pageFlags = flags.filter((flag) => selectedQuestionIds.has(flag.question_id));

  function updateAnswer(questionId: string, value: unknown) {
    setDraftAnswers((current) => ({ ...current, [questionId]: value }));
  }

  function handleCaseSelect(nextCase: CaseSummary) {
    startTransition(() => {
      void loadCase(nextCase.id, `Loaded ${nextCase.case_name}.`);
    });
  }

  function handleCreateCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    startTransition(() => {
      void (async () => {
        try {
          const created = await createCase({
            case_name: caseForm.case_name.trim(),
            petitioner_email: caseForm.petitioner_email.trim() || undefined,
            beneficiary_email: caseForm.beneficiary_email.trim() || undefined,
            country_of_focus: caseForm.country_of_focus.trim() || undefined,
          });
          await loadCase(created.id, "Case created. Start with the first prescreen page.");
        } catch (error) {
          setMessage(error instanceof Error ? error.message : "Case creation failed.");
        }
      })();
    });
  }

  function saveCurrentPage(moveNext: boolean) {
    if (!caseSummary || !selectedPage) {
      setMessage("Create or open a case first, then save this prescreen page.");
      return;
    }
    const answers = Object.fromEntries(
      selectedPage.questions
        .map((question) => [question.id, normalizeAnswer(question, draftAnswers[question.id])])
        .filter(([, value]) => hasAnswer(value)),
    );
    startTransition(() => {
      void (async () => {
        try {
          const state = await savePrescreenAnswers(caseSummary.id, answers);
          setPrescreen(state);
          setDraftAnswers(state.answers);
          if (moveNext) {
            const nextPages = Array.from(new Set(state.evaluation.visible_questions.map((question) => question.section)));
            const currentIndex = nextPages.indexOf(selectedPage.id);
            setSelectedPageId(nextPages[Math.min(currentIndex + 1, Math.max(nextPages.length - 1, 0))] ?? selectedPage.id);
          }
          setMessage("Saved this prescreen page and recalculated the branch.");
        } catch (error) {
          setMessage(error instanceof Error ? error.message : "Could not save this prescreen page.");
        }
      })();
    });
  }

  function handleGenerateStarterChecklist() {
    if (!caseSummary) {
      setMessage("Create or open a case first.");
      return;
    }
    startTransition(() => {
      void (async () => {
        try {
          await generateChecklist(caseSummary.id);
          setMessage("Starter checklist generated from the current prescreen branch.");
        } catch (error) {
          setMessage(error instanceof Error ? error.message : "Could not generate the checklist.");
        }
      })();
    });
  }

  function renderQuestionCard(question: PrescreenQuestion) {
    const source = prescreen?.answer_sources?.[question.id];
    const fieldSourceCount = Object.keys(prescreen?.answer_sources ?? {}).filter((key) => key.startsWith(`${question.id}.`)).length;
    const missing = !questionHasAnswer(question, draftAnswers[question.id]);
    return (
      <div
        key={question.id}
        className={classNames(
          "grid gap-3 rounded-lg border p-4",
          missing ? "border-clay/30 bg-clay/5" : "border-ink/10 bg-paper/55",
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold leading-6 text-ink">
              {question.label}
              {missing ? <span className="text-clay"> *</span> : null}
            </p>
            {question.help_text ? <p className="mt-1 text-xs leading-5 text-ink/65">{question.help_text}</p> : null}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {missing ? <span className="rounded-full bg-clay/10 px-2.5 py-1 text-xs font-semibold text-clay">Missing</span> : null}
            <QuestionHelpButton question={question} />
          </div>
        </div>
        <QuestionControl question={question} value={draftAnswers[question.id]} onChange={(value) => updateAnswer(question.id, value)} />
        <div className="flex flex-wrap gap-2 text-xs text-ink/55">
          <span>{question.db_path ? `maps to ${question.db_path}` : "branch-only question"}</span>
          {sourceLabel(source) ? <span className="font-semibold text-pine">{sourceLabel(source)}</span> : null}
          {fieldSourceCount ? <span className="font-semibold text-pine">{fieldSourceCount} smart defaults</span> : null}
        </div>
      </div>
    );
  }

  if (!questionnaire) {
    return <main className="mx-auto max-w-5xl px-6 py-10 text-ink">Loading prescreen questions...</main>;
  }

  return (
    <main className="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-8 text-ink">
      <header className="flex flex-col gap-4 border-b border-ink/10 pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-pine/80">Packet prescreen</p>
          <h1 className="font-display text-4xl text-ink">Prescreen questions</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-ink/70">
            A standard source-dated question set that uses the same page-by-page intake pattern as the I-485,
            I-130, I-130A, I-765, I-131, and I-864 screens.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleGenerateStarterChecklist}
            disabled={!caseSummary || isPending}
            className="rounded-lg border border-ink/15 bg-white px-4 py-2 text-sm font-semibold text-ink disabled:opacity-55"
          >
            Generate checklist
          </button>
          <Link
            href={caseSummary ? actionHref("/review", caseSummary.id) : "/review"}
            className="rounded-lg border border-ink/15 bg-white px-4 py-2 text-sm font-semibold text-ink"
          >
            Review packet
          </Link>
          <Link href="/" className="rounded-lg border border-ink/15 bg-white px-4 py-2 text-sm font-semibold text-ink">
            Start / resume
          </Link>
          <a
            href={questionnaire.sources[0]?.url}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg border border-pine bg-pine px-4 py-2 text-sm font-semibold text-white"
          >
            USCIS source
          </a>
        </div>
      </header>

      {message ? <p className="rounded-lg border border-ink/10 bg-white p-3 text-sm text-ink/75">{message}</p> : null}

      {!caseSummary ? (
        <section className="grid gap-5 rounded-lg border border-amber-200 bg-amber-50 p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div>
            <h2 className="font-display text-2xl text-ink">Create or choose a case</h2>
            <p className="mt-2 text-sm leading-6 text-ink/70">
              Prescreen answers save into the case workspace so later form pages can reuse matching facts.
            </p>
            <div className="mt-4">
              <CaseSelector selectedCaseId="" onSelect={handleCaseSelect} disabled={isPending} label="Choose saved case" />
            </div>
          </div>
          <form onSubmit={handleCreateCase} className="grid gap-3 rounded-lg border border-ink/10 bg-white p-4">
            <label className="grid gap-1">
              <span className="text-xs font-semibold text-ink/65">Case name</span>
              <input
                value={caseForm.case_name}
                onChange={(event) => setCaseForm((current) => ({ ...current, case_name: event.target.value }))}
                className="h-10 rounded-lg border border-ink/15 px-3 text-sm"
              />
            </label>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="grid gap-1">
                <span className="text-xs font-semibold text-ink/65">Petitioner email</span>
                <input
                  type="email"
                  value={caseForm.petitioner_email}
                  onChange={(event) => setCaseForm((current) => ({ ...current, petitioner_email: event.target.value }))}
                  className="h-10 rounded-lg border border-ink/15 px-3 text-sm"
                />
              </label>
              <label className="grid gap-1">
                <span className="text-xs font-semibold text-ink/65">Beneficiary email</span>
                <input
                  type="email"
                  value={caseForm.beneficiary_email}
                  onChange={(event) => setCaseForm((current) => ({ ...current, beneficiary_email: event.target.value }))}
                  className="h-10 rounded-lg border border-ink/15 px-3 text-sm"
                />
              </label>
            </div>
            <label className="grid gap-1">
              <span className="text-xs font-semibold text-ink/65">Country of focus</span>
              <input
                value={caseForm.country_of_focus}
                onChange={(event) => setCaseForm((current) => ({ ...current, country_of_focus: event.target.value }))}
                className="h-10 rounded-lg border border-ink/15 px-3 text-sm"
              />
            </label>
            <button
              type="submit"
              disabled={isPending}
              className="rounded-lg bg-pine px-4 py-2 text-sm font-semibold text-white disabled:opacity-55"
            >
              {isPending ? "Creating..." : "Create case"}
            </button>
          </form>
        </section>
      ) : (
        <section className="grid gap-4 rounded-lg border border-ink/10 bg-white p-4 text-sm text-ink/70 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] md:items-end">
          <CaseSelector selectedCaseId={caseSummary.id} onSelect={handleCaseSelect} disabled={isPending} label="Switch case" />
          <p>
            <span className="font-semibold text-ink">Active case:</span> {caseSummary.case_name}
          </p>
        </section>
      )}

      {prescreen ? (
        <section className="grid gap-3 rounded-lg border border-ink/10 bg-white p-5 md:grid-cols-[1.2fr_repeat(4,minmax(0,1fr))]">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-pine/80">Prescreen status</p>
            <h2 className="font-display text-2xl text-ink">{formatStatus(prescreen.evaluation.status)}</h2>
            <p className="mt-1 text-sm leading-6 text-ink/65">Questionnaire version {prescreen.evaluation.version}</p>
          </div>
          {[
            ["Completion", `${prescreen.evaluation.completion_pct}%`],
            ["Visible", visibleQuestions.length],
            ["Missing", missingQuestions.length],
            ["Flags", flags.length],
          ].map(([label, value]) => (
            <div key={label} className="rounded-lg border border-ink/10 bg-paper/55 p-3">
              <p className="text-xs uppercase tracking-[0.16em] text-ink/45">{label}</p>
              <p className="mt-2 text-2xl font-semibold text-ink">{value}</p>
            </div>
          ))}
        </section>
      ) : null}

      {prescreen?.evaluation.completion_pct === 100 && caseSummary ? (
        <section className="rounded-lg border border-pine/20 bg-white p-5">
          <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-pine/80">Prescreen complete</p>
              <h2 className="font-display text-2xl text-ink">Select a form to complete next</h2>
              <p className="mt-1 text-sm leading-6 text-ink/65">
                Start with the suggested form. Each form opens prefilled from the saved case record and can be reviewed before you generate drafts.
              </p>
            </div>
            <Link
              href={actionHref("/review", caseSummary.id)}
              className="rounded-lg border border-ink/15 bg-white px-4 py-2 text-sm font-semibold text-ink"
            >
              Review checklist
            </Link>
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-3">
            {nextFormOptions.map((option, index) => {
              const isSuggested = index === 0;
              return (
                <Link
                  key={option.formKey}
                  href={packetFormHref(option.formKey, caseSummary.id)}
                  className={classNames(
                    "rounded-lg border p-3 text-sm transition hover:border-pine/35 hover:bg-white",
                    isSuggested ? "border-pine/45 bg-pine/5 shadow-sm ring-1 ring-pine/10" : "border-ink/10 bg-paper/55",
                  )}
                >
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold uppercase tracking-[0.14em] text-ink/45">{option.phase}</span>
                    {isSuggested ? (
                      <span className="rounded-full bg-pine px-2 py-0.5 text-[11px] font-semibold text-white">Suggested next</span>
                    ) : null}
                  </span>
                  <span className="mt-1 block font-semibold text-ink">Start {option.label}</span>
                  <span className="text-ink/62">{option.detail}</span>
                  <span className="mt-2 block text-xs font-semibold text-pine">Prefills from saved case data</span>
                </Link>
              );
            })}
          </div>
        </section>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <aside className="rounded-lg border border-ink/10 bg-white p-4">
          <div className="mb-4">
            <p className="text-sm font-semibold text-ink">Completion</p>
            <div className="mt-2 h-2 rounded-full bg-ink/10">
              <div className="h-2 rounded-full bg-pine" style={{ width: `${prescreen?.evaluation.completion_pct ?? 0}%` }} />
            </div>
            <p className="mt-2 text-xs uppercase tracking-[0.18em] text-ink/55">
              {prescreen?.evaluation.completion_pct ?? 0}% · {formatStatus(prescreen?.evaluation.status ?? "not loaded")}
            </p>
          </div>
          <div className="grid gap-2">
            {pages.map((page, index) => {
              const pageFlags = flags.filter((flag) => page.questions.some((question) => question.id === flag.question_id));
              const pageMissing = page.total - page.answered;
              return (
                <button
                  key={page.id}
                  type="button"
                  onClick={() => setSelectedPageId(page.id)}
                  className={classNames(
                    "rounded-lg border px-3 py-2 text-left text-sm",
                    selectedPage?.id === page.id ? "border-pine bg-mist text-ink" : "border-ink/10 bg-white text-ink/75",
                    pageMissing ? "border-clay/30" : "",
                  )}
                >
                  <span className="flex items-start justify-between gap-2">
                    <span className="font-semibold">
                      {index + 1}. {page.title}
                    </span>
                    <span className="flex shrink-0 flex-wrap justify-end gap-1">
                      {pageMissing ? (
                        <span className="rounded-full bg-clay/10 px-2 py-0.5 text-[11px] font-semibold text-clay">
                          {pageMissing} missing
                        </span>
                      ) : (
                        <span className="rounded-full bg-pine/10 px-2 py-0.5 text-[11px] font-semibold text-pine">
                          Done
                        </span>
                      )}
                      {pageFlags.length ? (
                        <span className="rounded-full bg-sand/55 px-2 py-0.5 text-[11px] font-semibold text-ink/70">
                          {pageFlags.length}
                        </span>
                      ) : null}
                    </span>
                  </span>
                  <span className="mt-1 block text-xs text-ink/55">
                    {page.answered}/{page.total} answered
                  </span>
                </button>
              );
            })}
          </div>
        </aside>

        <section className="rounded-lg border border-ink/10 bg-white p-5">
          {selectedPage ? (
            <>
              <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-pine/80">Prescreen page</p>
                  <h2 className="font-display text-2xl text-ink">{selectedPage.title}</h2>
                  <p className="mt-1 text-sm text-ink/60">
                    {selectedPage.answered}/{selectedPage.total} answered
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => saveCurrentPage(false)}
                    disabled={isPending || !caseSummary}
                    className="rounded-lg border border-ink/15 bg-white px-4 py-2 text-sm font-semibold text-ink disabled:opacity-55"
                  >
                    {isPending ? "Saving..." : "Save page"}
                  </button>
                  <button
                    type="button"
                    onClick={() => saveCurrentPage(true)}
                    disabled={isPending || !caseSummary}
                    className="rounded-lg bg-pine px-4 py-2 text-sm font-semibold text-white disabled:opacity-55"
                  >
                    Save and continue
                  </button>
                </div>
              </div>

              {pageFlags.length ? (
                <div className="mb-5 grid gap-2">
                  {pageFlags.map((flag) => (
                    <div key={`${flag.question_id}-${flag.code}`} className={classNames("rounded-lg border p-3 text-sm", flagTone(flag))}>
                      <p className="font-semibold">{flag.title}</p>
                      <p className="mt-1 leading-6">{flag.description}</p>
                    </div>
                  ))}
                </div>
              ) : null}

              <div className="grid gap-4">{selectedPage.questions.map((question) => renderQuestionCard(question))}</div>
            </>
          ) : (
            <p className="text-sm text-ink/65">Create or choose a case to load the prescreen questions.</p>
          )}
        </section>
      </section>

      {prescreen ? (
        <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="rounded-lg border border-ink/10 bg-white p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-pine/80">Packet path</p>
                <h2 className="font-display text-2xl text-ink">Select a form to complete</h2>
                <p className="mt-1 text-sm leading-6 text-ink/65">
                  Complete the next sections in order. The suggested form is highlighted and opens with saved case data applied.
                </p>
              </div>
              <span className="shrink-0 rounded-full bg-pine/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-pine">
                {includedForms.length} to complete
              </span>
            </div>
            <div className="mt-4 grid gap-2 md:grid-cols-2">
              {includedForms.map((formCode) => {
                const action = FORM_ACTIONS[formCode];
                if (!action || !caseSummary) {
                  return null;
                }
                const isSuggested = formCode === suggestedFormCode;
                const syncsFromCase = action.href.includes("ingestion");
                return (
                  <Link
                    key={formCode}
                    href={actionHref(action.href, caseSummary.id)}
                    className={classNames(
                      "rounded-lg border p-3 text-sm transition hover:border-pine/35 hover:bg-white",
                      isSuggested ? "border-pine/45 bg-pine/5 shadow-sm ring-1 ring-pine/10" : "border-ink/10 bg-paper/55",
                    )}
                  >
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-semibold uppercase tracking-[0.14em] text-ink/45">{action.phase}</span>
                      {isSuggested ? (
                        <span className="rounded-full bg-pine px-2 py-0.5 text-[11px] font-semibold text-white">Suggested next</span>
                      ) : null}
                    </span>
                    <span className="mt-1 block font-semibold text-ink">
                      {isSuggested ? `Start ${action.label}` : action.label}
                    </span>
                    <span className="text-ink/62">{action.detail}</span>
                    {syncsFromCase ? (
                      <span className="mt-2 block text-xs font-semibold text-pine">Syncs from saved case data on open</span>
                    ) : null}
                  </Link>
                );
              })}
            </div>
          </div>

          <div className="rounded-lg border border-ink/10 bg-white p-5">
            <h2 className="font-display text-2xl text-ink">Unnecessary forms and work based on your answers</h2>
            <div className="mt-4 grid gap-2">
              {[...eliminatedForms, ...(prescreen.evaluation.eliminated_questions ?? [])].slice(0, 8).map((item) => {
                const key = "form_code" in item ? item.form_code : item.question_id;
                return (
                  <div key={key} className="rounded-lg border border-ink/10 bg-paper/55 p-3 text-sm">
                    <p className="font-semibold text-ink">{"label" in item ? item.label : key}</p>
                    <p className="mt-1 leading-6 text-ink/65">{item.reason}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      ) : null}

      <section className="rounded-lg border border-ink/10 bg-white p-5">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-pine/80">Source control</p>
            <h2 className="font-display text-2xl">Questionnaire version {questionnaire.version}</h2>
          </div>
          <p className="text-sm text-ink/60">Verified {questionnaire.verified_on}</p>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {questionnaire.sources.map((source) => (
            <a
              key={source.label}
              href={source.url.startsWith("http") ? source.url : undefined}
              className="rounded-lg border border-ink/10 bg-paper/50 p-3 text-sm text-ink/75"
            >
              <span className="font-semibold text-ink">{source.label}</span>
              <span className="mt-1 block leading-6">{source.notes}</span>
            </a>
          ))}
        </div>
      </section>
    </main>
  );
}

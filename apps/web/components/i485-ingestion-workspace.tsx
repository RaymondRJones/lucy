"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";

import { CaseSelector } from "@/components/case-selector";
import {
  apiUrl,
  generateI485Pdf,
  getI485FormFillPreview,
  getI485IngestionState,
  getI485Questionnaire,
  getPrescreenState,
  importI485FromCaseData,
  importI485FromUpload,
  saveI485Page,
} from "@/lib/api";
import { getSavedCaseId, rememberCaseId } from "@/lib/case-storage";
import {
  manualFlagCountForPage,
  manualFlagsForPage,
  manualFlagSummaries,
  normalizeManualQuestionFlags,
  type ManualQuestionFlags,
} from "@/lib/manual-question-flags";
import {
  ensurePacketFormOption,
  nextPacketFormOption,
  packetFormHref,
  packetFormsForIncluded,
  type PacketFormFlowOption,
} from "@/lib/packet-form-flow";
import type {
  CaseSummary,
  I485Flag,
  I485FormFillPreview,
  I485IngestionState,
  I485PdfGenerateResponse,
  I485Question,
  I485Questionnaire,
  I485QuestionnairePage,
  PrescreenState,
} from "@/lib/types";
const MISSING_REQUIRED_DISPLAY_LIMIT = 5;

function classNames(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

function formatStatus(value: string) {
  return value.replaceAll("_", " ");
}

function fieldValue(value: unknown) {
  if (typeof value === "string" || typeof value === "number") {
    return String(value);
  }
  return "";
}

function isChecked(value: unknown, option: string) {
  return Array.isArray(value) && value.includes(option);
}

function normalizeInputValue(question: I485Question, rawValue: string | boolean | string[]) {
  if (question.answer_type === "number") {
    if (rawValue === "") {
      return "";
    }
    return Number(rawValue);
  }
  return rawValue;
}

function repeatableEntries(question: I485Question, value: unknown): Record<string, unknown>[] {
  if (Array.isArray(value)) {
    return value.filter((entry): entry is Record<string, unknown> => Boolean(entry) && typeof entry === "object" && !Array.isArray(entry));
  }
  if (typeof value === "string" && value.trim()) {
    const key = question.answer_type === "address_list" ? "line1" : "notes";
    return [{ [key]: value.trim() }];
  }
  return [];
}

function structuredEntry(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  if (typeof value === "string" && value.trim()) {
    return { line1: value.trim() };
  }
  return {};
}

function hasMeaningfulEntryValue(value: unknown) {
  if (value === null || value === undefined || value === "" || value === false) {
    return false;
  }
  if (Array.isArray(value)) {
    return value.length > 0;
  }
  if (typeof value === "object") {
    return Object.values(value).some(hasMeaningfulEntryValue);
  }
  return true;
}

function cleanQuestionAnswer(question: I485Question, value: unknown) {
  if (["address_list", "employment_history_list"].includes(question.answer_type)) {
    const entries = repeatableEntries(question, value).filter((entry) => Object.values(entry).some(hasMeaningfulEntryValue));
    return entries.length ? entries : undefined;
  }
  if (question.answer_type === "address" && question.entry_fields?.length) {
    const entry = structuredEntry(value);
    return Object.values(entry).some(hasMeaningfulEntryValue) ? entry : undefined;
  }
  return value;
}

function emptyRepeatableEntry(question: I485Question) {
  return Object.fromEntries((question.entry_fields ?? []).map((field) => [field.key, field.type === "boolean" ? false : ""]));
}

function firstForeignSchoolEntry(value: unknown) {
  const entries = Array.isArray(value)
    ? value.filter((entry): entry is Record<string, unknown> => Boolean(entry) && typeof entry === "object" && !Array.isArray(entry))
    : [];
  return entries.find((entry) => {
    const activityType = String(entry.activity_type ?? "").toLowerCase();
    const country = String(entry.country ?? "").toLowerCase();
    return activityType === "school" && country && !["united states", "united states of america", "usa", "us"].includes(country);
  });
}

function flagTone(flag: I485Flag) {
  if (flag.severity === "blocking") {
    return "border-red-200 bg-red-50 text-red-950";
  }
  if (flag.category === "outside_niche") {
    return "border-amber-200 bg-amber-50 text-amber-950";
  }
  return "border-ink/10 bg-white text-ink";
}

function sourceLabel(source: I485IngestionState["answer_sources"][string] | undefined) {
  if (!source) {
    return null;
  }
  if (source.source_type === "pdf_upload") {
    const confidence = typeof source.confidence === "number" ? ` · ${Math.round(source.confidence * 100)}%` : "";
    return `Pulled from ${source.filename ?? "uploaded PDF"}${confidence}`;
  }
  if (source.source_type === "user") {
    return "User entered";
  }
  return formatStatus(source.source_type);
}

function QuestionHelpButton({ question }: { question: I485Question }) {
  if (!question.deep_explanation) {
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
        <span className="block font-semibold text-ink">How to answer this</span>
        <span className="mt-1 block">{question.deep_explanation}</span>
        {question.teaching_source ? (
          <span className="mt-2 block border-t border-ink/10 pt-2 text-ink/55">
            Based on {question.teaching_source.label}, fetched {question.teaching_source.fetched_on}.
          </span>
        ) : null}
      </span>
    </span>
  );
}

function RepeatableHistoryControl({
  question,
  value,
  onChange,
}: {
  question: I485Question;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const fields = question.entry_fields ?? [];
  const entries = repeatableEntries(question, value);
  const visibleEntries = entries.length ? entries : [emptyRepeatableEntry(question)];
  const formEntryLimit = question.form_entry_limit ?? null;
  const overflowCount = formEntryLimit === null ? 0 : Math.max(0, visibleEntries.length - formEntryLimit);

  function updateEntry(index: number, key: string, nextValue: unknown) {
    const nextEntries = visibleEntries.map((entry, entryIndex) =>
      entryIndex === index ? { ...entry, [key]: nextValue } : entry,
    );
    onChange(nextEntries);
  }

  function removeEntry(index: number) {
    const nextEntries = visibleEntries.filter((_, entryIndex) => entryIndex !== index);
    onChange(nextEntries.length ? nextEntries : []);
  }

  return (
    <div className="grid gap-3">
      {overflowCount ? (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs font-semibold text-amber-950">
          {overflowCount} {overflowCount === 1 ? "entry" : "entries"} beyond the on-form slot should be reviewed for{" "}
          {question.overflow_pdf_ref ?? "additional information"}.
        </p>
      ) : null}
      {visibleEntries.map((entry, index) => {
        const isOverflow = formEntryLimit !== null && index >= formEntryLimit;
        return (
          <div key={index} className="grid gap-3 rounded-lg border border-ink/10 bg-white p-3">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink/55">
                Entry {index + 1}{isOverflow ? " · Part 14" : ""}
              </p>
              {visibleEntries.length > 1 ? (
                <button
                  type="button"
                  onClick={() => removeEntry(index)}
                  className="rounded-lg border border-ink/15 px-3 py-1 text-xs font-semibold text-ink/70"
                >
                  Remove
                </button>
              ) : null}
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {fields.map((field) => {
                const fieldLabel = `${field.label}${field.required ? " *" : ""}`;
                if (field.type === "textarea") {
                  return (
                    <label key={field.key} className="grid gap-1 md:col-span-2">
                      <span className="text-xs font-semibold text-ink/65">{fieldLabel}</span>
                      <textarea
                        value={fieldValue(entry[field.key])}
                        onChange={(event) => updateEntry(index, field.key, event.target.value)}
                        rows={2}
                        className="w-full rounded-lg border border-ink/15 bg-paper/35 px-3 py-2 text-sm leading-6 text-ink"
                      />
                    </label>
                  );
                }
                if (field.type === "select") {
                  return (
                    <label key={field.key} className="grid gap-1">
                      <span className="text-xs font-semibold text-ink/65">{fieldLabel}</span>
                      <select
                        value={fieldValue(entry[field.key])}
                        onChange={(event) => updateEntry(index, field.key, event.target.value)}
                        className="h-10 w-full rounded-lg border border-ink/15 bg-paper/35 px-3 text-sm text-ink"
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
                if (field.type === "boolean") {
                  return (
                    <label key={field.key} className="flex items-center gap-2 rounded-lg border border-ink/10 bg-paper/35 px-3 py-2 text-sm text-ink">
                      <input
                        type="checkbox"
                        checked={entry[field.key] === true}
                        onChange={(event) => updateEntry(index, field.key, event.target.checked)}
                        className="h-4 w-4 rounded border-ink/30 text-pine"
                      />
                      {fieldLabel}
                    </label>
                  );
                }
                return (
                  <label key={field.key} className="grid gap-1">
                    <span className="text-xs font-semibold text-ink/65">{fieldLabel}</span>
                    <input
                      type={field.type === "date" ? "date" : "text"}
                      value={fieldValue(entry[field.key])}
                      onChange={(event) => updateEntry(index, field.key, event.target.value)}
                      className="h-10 w-full rounded-lg border border-ink/15 bg-paper/35 px-3 text-sm text-ink"
                    />
                  </label>
                );
              })}
            </div>
          </div>
        );
      })}
      <button
        type="button"
        onClick={() => onChange([...visibleEntries, emptyRepeatableEntry(question)])}
        className="w-fit rounded-lg border border-pine px-3 py-2 text-xs font-semibold text-pine"
      >
        Add entry
      </button>
    </div>
  );
}

function StructuredAddressControl({
  question,
  value,
  onChange,
}: {
  question: I485Question;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const fields = question.entry_fields ?? [];
  const entry = structuredEntry(value);

  function updateField(key: string, nextValue: unknown) {
    onChange({ ...entry, [key]: nextValue });
  }

  return (
    <div className="grid gap-3 rounded-lg border border-ink/10 bg-white p-3 md:grid-cols-2">
      {fields.map((field) => {
        const fieldLabel = `${field.label}${field.required ? " *" : ""}`;
        if (field.type === "select") {
          return (
            <label key={field.key} className="grid gap-1">
              <span className="text-xs font-semibold text-ink/65">{fieldLabel}</span>
              <select
                value={fieldValue(entry[field.key])}
                onChange={(event) => updateField(field.key, event.target.value)}
                className="h-10 w-full rounded-lg border border-ink/15 bg-paper/35 px-3 text-sm text-ink"
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
        if (field.type === "boolean") {
          return (
            <label key={field.key} className="flex items-center gap-2 rounded-lg border border-ink/10 bg-paper/35 px-3 py-2 text-sm text-ink">
              <input
                type="checkbox"
                checked={entry[field.key] === true}
                onChange={(event) => updateField(field.key, event.target.checked)}
                className="h-4 w-4 rounded border-ink/30 text-pine"
              />
              {fieldLabel}
            </label>
          );
        }
        return (
          <label key={field.key} className="grid gap-1">
            <span className="text-xs font-semibold text-ink/65">{fieldLabel}</span>
            <input
              type={field.type === "date" ? "date" : "text"}
              value={fieldValue(entry[field.key])}
              onChange={(event) => updateField(field.key, event.target.value)}
              className="h-10 w-full rounded-lg border border-ink/15 bg-paper/35 px-3 text-sm text-ink"
            />
          </label>
        );
      })}
    </div>
  );
}

function QuestionControl({
  question,
  value,
  onChange,
}: {
  question: I485Question;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  if (question.answer_type === "address" && question.entry_fields?.length) {
    return <StructuredAddressControl question={question} value={value} onChange={onChange} />;
  }

  if (["address_list", "employment_history_list"].includes(question.answer_type) && question.entry_fields?.length) {
    return <RepeatableHistoryControl question={question} value={value} onChange={onChange} />;
  }

  if (question.answer_type === "boolean") {
    return (
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onChange(true)}
          className={classNames(
            "h-10 rounded-lg border px-4 text-sm font-semibold",
            value === true ? "border-pine bg-pine text-white" : "border-ink/15 bg-white text-ink",
          )}
        >
          Yes
        </button>
        <button
          type="button"
          onClick={() => onChange(false)}
          className={classNames(
            "h-10 rounded-lg border px-4 text-sm font-semibold",
            value === false ? "border-pine bg-pine text-white" : "border-ink/15 bg-white text-ink",
          )}
        >
          No
        </button>
      </div>
    );
  }

  if (question.answer_type === "select") {
    return (
      <select
        value={fieldValue(value)}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 w-full rounded-lg border border-ink/15 bg-white px-3 text-sm text-ink"
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
    return (
      <div className="grid gap-2 sm:grid-cols-2">
        {question.options.map((option) => (
          <label key={option.value} className="flex items-center gap-2 rounded-lg border border-ink/10 bg-white p-3 text-sm">
            <input
              type="checkbox"
              checked={isChecked(value, option.value)}
              onChange={(event) => {
                const current = Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === "string") : [];
                onChange(event.target.checked ? [...current, option.value] : current.filter((entry) => entry !== option.value));
              }}
              className="h-4 w-4 rounded border-ink/30 text-pine"
            />
            {option.label}
          </label>
        ))}
      </div>
    );
  }

  if (question.answer_type === "single_check") {
    return (
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {question.options.map((option) => (
          <label key={option.value} className="flex items-center gap-2 rounded-lg border border-ink/10 bg-white p-3 text-sm">
            <input
              type="checkbox"
              checked={value === option.value}
              onChange={(event) => onChange(event.target.checked ? option.value : "")}
              className="h-4 w-4 rounded border-ink/30 text-pine"
            />
            {option.label}
          </label>
        ))}
      </div>
    );
  }

  if (["textarea", "address", "address_list"].includes(question.answer_type)) {
    return (
      <textarea
        value={fieldValue(value)}
        onChange={(event) => onChange(event.target.value)}
        rows={3}
        className="w-full rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm leading-6 text-ink"
      />
    );
  }

  const inputType = question.answer_type === "date" ? "date" : question.answer_type === "number" ? "number" : "text";
  return (
    <input
      type={inputType}
      value={fieldValue(value)}
      onChange={(event) => onChange(normalizeInputValue(question, event.target.value))}
      className="h-11 w-full rounded-lg border border-ink/15 bg-white px-3 text-sm text-ink"
    />
  );
}

export function I485IngestionWorkspace({ initialCaseId }: { initialCaseId?: string }) {
  const [caseId, setCaseId] = useState<string | null>(null);
  const [questionnaire, setQuestionnaire] = useState<I485Questionnaire | null>(null);
  const [selectedPageId, setSelectedPageId] = useState<string>("");
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [answerSources, setAnswerSources] = useState<I485IngestionState["answer_sources"]>({});
  const [manualFlags, setManualFlags] = useState<ManualQuestionFlags>({});
  const [flags, setFlags] = useState<I485Flag[]>([]);
  const [fillPreview, setFillPreview] = useState<I485FormFillPreview | null>(null);
  const [generatedPdf, setGeneratedPdf] = useState<I485PdfGenerateResponse | null>(null);
  const [prescreen, setPrescreen] = useState<PrescreenState | null>(null);
  const [completionPct, setCompletionPct] = useState(0);
  const [readiness, setReadiness] = useState("not_loaded");
  const [message, setMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const [loadedCaseStateKey, setLoadedCaseStateKey] = useState<string | null>(null);
  const autoSyncKeyRef = useRef<string | null>(null);

  useEffect(() => {
    const storedCaseId = initialCaseId || getSavedCaseId();
    if (storedCaseId) {
      rememberCaseId(storedCaseId);
    }
    setCaseId(storedCaseId);
    getI485Questionnaire()
      .then((payload) => {
        setQuestionnaire(payload);
        setSelectedPageId(payload.pages[0]?.id ?? "");
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "Could not load I-485 questionnaire."));
    if (storedCaseId) {
      const stateKey = `${storedCaseId}:i485`;
      setLoadedCaseStateKey(null);
      getPrescreenState(storedCaseId)
        .then(setPrescreen)
        .catch(() => setPrescreen(null));
      getI485IngestionState(storedCaseId)
        .then((state) => {
          setAnswers(state.answers);
          setAnswerSources(state.answer_sources);
          setManualFlags(normalizeManualQuestionFlags(state.manual_flags));
          setFlags(state.evaluation.flags);
          setCompletionPct(state.evaluation.completion_pct);
          setReadiness(state.evaluation.readiness);
          return getI485FormFillPreview(storedCaseId);
        })
        .then((preview) => {
          setFillPreview(preview);
          setLoadedCaseStateKey(stateKey);
        })
        .catch((error) => setMessage(error instanceof Error ? error.message : "Could not load saved I-485 answers."));
    }
  }, [initialCaseId]);

  useEffect(() => {
    if (!caseId) {
      return;
    }
    const stateKey = `${caseId}:i485`;
    if (loadedCaseStateKey !== stateKey || autoSyncKeyRef.current === stateKey) {
      return;
    }
    autoSyncKeyRef.current = stateKey;
    importI485FromCaseData(caseId)
      .then((result) => {
        setAnswers(result.state.answers);
        setAnswerSources(result.state.answer_sources);
        setManualFlags(normalizeManualQuestionFlags(result.state.manual_flags));
        setFlags(result.state.evaluation.flags);
        setCompletionPct(result.state.evaluation.completion_pct);
        setReadiness(result.state.evaluation.readiness);
        getI485FormFillPreview(caseId)
          .then((preview) => setFillPreview(preview))
          .catch((error) => setMessage(error instanceof Error ? error.message : "Could not refresh I-485 fill preview."));
        setMessage(
          result.imported_count
            ? `Synced ${result.imported_count} answers from saved case data. ${result.skipped_count} existing I-485 answers were preserved.`
            : "Checked saved case data; I-485 is already in sync.",
        );
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "Could not sync I-485 answers from case data."));
  }, [caseId, loadedCaseStateKey]);

  function refreshPreview(activeCaseId: string) {
    getI485FormFillPreview(activeCaseId)
      .then((preview) => setFillPreview(preview))
      .catch((error) => setMessage(error instanceof Error ? error.message : "Could not refresh I-485 fill preview."));
  }

  function applyState(state: I485IngestionState) {
    setAnswers(state.answers);
    setAnswerSources(state.answer_sources);
    setManualFlags(normalizeManualQuestionFlags(state.manual_flags));
    setFlags(state.evaluation.flags);
    setCompletionPct(state.evaluation.completion_pct);
    setReadiness(state.evaluation.readiness);
    if (caseId) {
      refreshPreview(caseId);
    }
  }

  const selectedPage = useMemo<I485QuestionnairePage | null>(() => {
    return questionnaire?.pages.find((page) => page.id === selectedPageId) ?? null;
  }, [questionnaire, selectedPageId]);

  const pageFlags = useMemo(() => {
    if (!selectedPage) {
      return [];
    }
    const questionIds = new Set(selectedPage.questions.map((question) => question.id));
    return flags.filter((flag) => questionIds.has(flag.question_id));
  }, [flags, selectedPage]);

  const manualReviewItems = useMemo(() => manualFlagSummaries(questionnaire?.pages ?? [], manualFlags), [
    manualFlags,
    questionnaire,
  ]);
  const missingRequiredItems = useMemo(() => fillPreview?.missing_required ?? [], [fillPreview]);
  const visibleMissingRequiredItems = useMemo(
    () => missingRequiredItems.slice(0, MISSING_REQUIRED_DISPLAY_LIMIT),
    [missingRequiredItems],
  );
  const hiddenMissingRequiredCount = Math.max(missingRequiredItems.length - visibleMissingRequiredItems.length, 0);
  const missingRequiredQuestionIds = useMemo(
    () => new Set(missingRequiredItems.map((item) => item.question_id)),
    [missingRequiredItems],
  );
  const formFlowOptions = useMemo<PacketFormFlowOption[]>(() => {
    return ensurePacketFormOption(packetFormsForIncluded(prescreen?.evaluation.included_forms), "i485");
  }, [prescreen]);
  const nextFormOption = useMemo(() => nextPacketFormOption(formFlowOptions, "i485"), [formFlowOptions]);
  const isFormComplete = completionPct === 100 && !missingRequiredItems.length;

  function updateAnswer(questionId: string, value: unknown) {
    setAnswers((current) => ({ ...current, [questionId]: value }));
  }

  function useHappyPathEmploymentDefaults() {
    const foreignSchool = firstForeignSchoolEntry(answers.beneficiary_employment_history);
    setAnswers((current) => ({
      ...current,
      beneficiary_employment_history: [
        {
          ...emptyRepeatableEntry({ entry_fields: selectedPage?.questions.find((question) => question.id === "beneficiary_employment_history")?.entry_fields ?? [] } as I485Question),
          activity_type: "unemployment",
          occupation: "Unemployed",
          financial_support: "Husband",
        },
      ],
      ...(foreignSchool && !hasMeaningfulEntryValue(current.beneficiary_foreign_employer_or_school)
        ? { beneficiary_foreign_employer_or_school: [{ ...foreignSchool, outside_us: undefined }] }
        : {}),
    }));
  }

  function isPageComplete(page: I485QuestionnairePage) {
    const requiredQuestions = page.questions.filter((question) => question.required);
    if (!requiredQuestions.length) {
      return false;
    }
    const pageMissingCount = missingRequiredItems.filter((item) => item.page_id === page.id).length;
    return pageMissingCount === 0 && requiredQuestions.every((question) => hasMeaningfulEntryValue(answers[question.id]));
  }

  function pageAnswersForSave(page: I485QuestionnairePage) {
    return Object.fromEntries(
      page.questions
        .map((question) => [question.id, cleanQuestionAnswer(question, answers[question.id])] as const)
        .filter(([, value]) => value !== undefined),
    );
  }

  function saveCurrentPage() {
    if (!caseId || !selectedPage) {
      setMessage("Create or open a case first, then return to this I-485 page.");
      return;
    }
    const pageAnswers = pageAnswersForSave(selectedPage);
    startTransition(() => {
      saveI485Page(caseId, selectedPage.id, pageAnswers, manualFlagsForPage(selectedPage, manualFlags))
        .then((state) => {
          applyState(state);
          setMessage("Saved this I-485 page and refreshed the case mapping.");
        })
        .catch((error) => setMessage(error instanceof Error ? error.message : "Could not save this I-485 page."));
    });
  }

  function toggleManualFlag(question: I485Question) {
    if (!caseId || !selectedPage) {
      setMessage("Choose a case first, then mark questions to revisit.");
      return;
    }
    const nextFlags = { ...manualFlags };
    if (nextFlags[question.id]) {
      delete nextFlags[question.id];
    } else {
      nextFlags[question.id] = true;
    }
    setManualFlags(nextFlags);
    startTransition(() => {
      saveI485Page(caseId, selectedPage.id, pageAnswersForSave(selectedPage), manualFlagsForPage(selectedPage, nextFlags))
        .then((state) => {
          applyState(state);
          setMessage(nextFlags[question.id] ? "Marked for later review." : "Removed the manual review mark.");
        })
        .catch((error) => setMessage(error instanceof Error ? error.message : "Could not update the manual mark."));
    });
  }

  function importFromUpload() {
    if (!caseId) {
      setMessage("Create or open a case first, then return to this I-485 page.");
      return;
    }
    startTransition(() => {
      importI485FromUpload(caseId)
        .then((result) => {
          applyState(result.state);
          setMessage(
            `Pulled ${result.imported_count} answers from ${result.proposals[0]?.source_filename ?? "the uploaded I-485"}. ${result.skipped_count} existing answers were preserved.`,
          );
        })
        .catch((error) =>
          setMessage(error instanceof Error ? error.message : "Could not import answers from an uploaded I-485."),
        );
    });
  }

  function importFromCaseData() {
    if (!caseId) {
      setMessage("Create or open a case first, then return to this I-485 page.");
      return;
    }
    startTransition(() => {
      importI485FromCaseData(caseId)
        .then((result) => {
          applyState(result.state);
          setMessage(
            `Pulled ${result.imported_count} answers from reviewed case data. ${result.skipped_count} existing answers were preserved.`,
          );
        })
        .catch((error) => setMessage(error instanceof Error ? error.message : "Could not pull answers from case data."));
    });
  }

  function generatePdf() {
    if (!caseId) {
      setMessage("Create or open a case first, then return to this I-485 page.");
      return;
    }
    startTransition(() => {
      generateI485Pdf(caseId, { allow_incomplete: true })
        .then((result) => {
          setGeneratedPdf(result);
          setMessage(`Generated draft I-485 PDF at ${result.generated_pdf}.`);
        })
        .catch((error) => setMessage(error instanceof Error ? error.message : "Could not generate the I-485 PDF."));
    });
  }

  function navigateToForm(formKey: string) {
    const option = formFlowOptions.find((candidate) => candidate.formKey === formKey);
    if (option) {
      window.location.assign(packetFormHref(option.formKey, caseId));
    }
  }

  function selectCase(nextCase: CaseSummary) {
    rememberCaseId(nextCase.id);
    window.location.assign(`/i485-ingestion?caseId=${encodeURIComponent(nextCase.id)}`);
  }

  if (!questionnaire) {
    return <main className="mx-auto max-w-5xl px-6 py-10 text-ink">Loading I-485 questionnaire...</main>;
  }

  return (
    <main className="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-8 text-ink">
      <header className="flex flex-col gap-4 border-b border-ink/10 pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-pine/80">I-485 ingestion</p>
          <h1 className="font-display text-4xl text-ink">Adjustment questionnaire map</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-ink/70">
            Fourteen source-backed pages for collecting, mapping, and flagging I-485 answers before form-fill work.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            value="i485"
            onChange={(event) => navigateToForm(event.target.value)}
            className="h-10 rounded-lg border border-ink/15 bg-white px-3 text-sm font-semibold text-ink"
          >
            {formFlowOptions.map((option) => (
              <option key={option.formKey} value={option.formKey}>
                {option.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={importFromCaseData}
            disabled={!caseId || isPending}
            className="rounded-lg border border-ink/15 bg-white px-4 py-2 text-sm font-semibold text-ink disabled:opacity-55"
          >
            Pull from case data
          </button>
          <button
            type="button"
            onClick={importFromUpload}
            disabled={!caseId || isPending}
            className="rounded-lg border border-ink/15 bg-white px-4 py-2 text-sm font-semibold text-ink disabled:opacity-55"
          >
            Pull from uploaded I-485
          </button>
          <button
            type="button"
            onClick={generatePdf}
            disabled={!caseId || isPending}
            className="rounded-lg border border-ink/15 bg-white px-4 py-2 text-sm font-semibold text-ink disabled:opacity-55"
          >
            Generate draft PDF
          </button>
          <Link
            href={caseId ? `/packet-assembly?caseId=${encodeURIComponent(caseId)}` : "/packet-assembly"}
            className="rounded-lg border border-pine bg-pine px-4 py-2 text-sm font-semibold text-white"
          >
            Generate full packet
          </Link>
          <Link href="/" className="rounded-lg border border-ink/15 bg-white px-4 py-2 text-sm font-semibold text-ink">
            Case workspace
          </Link>
          <a
            href={questionnaire.official_url}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg border border-pine bg-pine px-4 py-2 text-sm font-semibold text-white"
          >
            USCIS source
          </a>
        </div>
      </header>

      {message ? <p className="rounded-lg border border-ink/10 bg-white p-3 text-sm text-ink/75">{message}</p> : null}

      {generatedPdf ? (
        <section className="rounded-lg border border-pine/20 bg-white p-4 text-sm text-ink/75">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="font-semibold text-ink">Draft PDF generated</p>
              <p className="mt-1 break-all">{generatedPdf.generated_pdf}</p>
            </div>
            <a
              href={apiUrl(generatedPdf.download_url)}
              target="_blank"
              rel="noreferrer"
              className="rounded-lg border border-pine bg-pine px-4 py-2 text-center text-sm font-semibold text-white"
            >
              Open PDF
            </a>
          </div>
          <p className="mt-2">
            Filled {generatedPdf.field_count} template fields from {generatedPdf.mapped_question_count} mapped questions.
            {generatedPdf.ready_for_pdf_generation ? "" : " This draft still needs questionnaire completion and review."}
          </p>
        </section>
      ) : null}

      {isFormComplete ? (
        <section className="rounded-lg border border-pine/20 bg-white p-5">
          <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-pine/80">Form complete</p>
              <h2 className="font-display text-2xl text-ink">Choose what to do next</h2>
              <p className="mt-1 text-sm leading-6 text-ink/65">
                I-485 has its required answers. Generate a draft, continue the packet path, or assemble the full packet.
              </p>
            </div>
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-3">
            <button
              type="button"
              onClick={generatePdf}
              disabled={!caseId || isPending}
              className="rounded-lg border border-ink/10 bg-paper/55 p-3 text-left text-sm font-semibold text-ink transition hover:border-pine/35 hover:bg-white disabled:opacity-55"
            >
              Generate draft PDF
            </button>
            {nextFormOption ? (
              <Link
                href={packetFormHref(nextFormOption.formKey, caseId)}
                className="rounded-lg border border-pine bg-pine p-3 text-sm font-semibold text-white"
              >
                Go to next: {nextFormOption.label}
              </Link>
            ) : (
              <Link
                href={caseId ? `/review?caseId=${encodeURIComponent(caseId)}` : "/review"}
                className="rounded-lg border border-pine bg-pine p-3 text-sm font-semibold text-white"
              >
                Review checklist
              </Link>
            )}
            <Link
              href={caseId ? `/packet-assembly?caseId=${encodeURIComponent(caseId)}` : "/packet-assembly"}
              className="rounded-lg border border-ink/15 bg-white p-3 text-sm font-semibold text-ink"
            >
              Generate full packet
            </Link>
          </div>
        </section>
      ) : null}

      {!caseId ? (
        <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
          <CaseSelector
            selectedCaseId=""
            onSelect={selectCase}
            disabled={isPending}
            label="Choose saved case"
          />
          <p className="mt-3">No active case ID is stored in this browser. Choose a case before saving answers.</p>
        </section>
      ) : (
        <section className="grid gap-4 rounded-lg border border-ink/10 bg-white p-4 text-sm text-ink/70 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] md:items-end">
          <CaseSelector
            selectedCaseId={caseId}
            onSelect={selectCase}
            disabled={isPending}
            label="Switch case"
          />
          <p>
            <span className="font-semibold text-ink">Active case ID:</span>{" "}
            <span className="break-all">{caseId}</span>
          </p>
        </section>
      )}

      {fillPreview ? (
        <section className="grid gap-3 rounded-lg border border-ink/10 bg-white p-5 md:grid-cols-[1.2fr_repeat(4,minmax(0,1fr))]">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-pine/80">Fill preview</p>
            <h2 className="font-display text-2xl text-ink">{formatStatus(fillPreview.generation_status)}</h2>
            <p className="mt-1 text-sm leading-6 text-ink/65">
              {fillPreview.questionnaire_version}
            </p>
          </div>
          {[
            ["Mapped", fillPreview.field_count],
            ["Missing", fillPreview.missing_required_count],
            ["Risk", fillPreview.blocking_flag_count],
            ["Review", fillPreview.low_confidence_count],
          ].map(([label, value]) => (
            <div key={label} className="rounded-lg border border-ink/10 bg-paper/55 p-3">
              <p className="text-xs uppercase tracking-[0.16em] text-ink/45">{label}</p>
              <p className="mt-2 text-2xl font-semibold text-ink">{value}</p>
            </div>
          ))}
        </section>
      ) : null}

      {missingRequiredItems.length ? (
        <section className="rounded-lg border border-clay/20 bg-clay/5 p-4 text-sm text-ink/76">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="font-semibold text-ink">Missing required answers</p>
            <p className="text-xs uppercase tracking-[0.14em] text-clay">
              {missingRequiredItems.length} remaining
            </p>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {visibleMissingRequiredItems.map((item) => (
              <button
                key={item.question_id}
                type="button"
                onClick={() => setSelectedPageId(item.page_id)}
                className="max-w-full rounded-full border border-clay/20 bg-white px-3 py-1.5 text-left text-xs font-semibold text-ink/72 transition hover:border-clay/40 hover:text-clay"
              >
                {item.label}
              </button>
            ))}
            {hiddenMissingRequiredCount ? (
              <span className="rounded-full border border-clay/20 bg-white px-3 py-1.5 text-xs font-semibold text-ink/55">
                +{hiddenMissingRequiredCount} more shown in the page list
              </span>
            ) : null}
          </div>
        </section>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <aside className="rounded-lg border border-ink/10 bg-white p-4">
          <div className="mb-4">
            <p className="text-sm font-semibold text-ink">Completion</p>
            <div className="mt-2 h-2 rounded-full bg-ink/10">
              <div className="h-2 rounded-full bg-pine" style={{ width: `${completionPct}%` }} />
            </div>
            <p className="mt-2 text-xs uppercase tracking-[0.18em] text-ink/55">{completionPct}% · {formatStatus(readiness)}</p>
          </div>
          <div className="grid gap-2">
            {questionnaire.pages.map((page, index) => {
              const manualFlagCount = manualFlagCountForPage(page, manualFlags);
              const pageMissingCount = missingRequiredItems.filter((item) => item.page_id === page.id).length;
              const pageComplete = isPageComplete(page);
              return (
                <button
                  key={page.id}
                  type="button"
                  onClick={() => setSelectedPageId(page.id)}
                  className={classNames(
                    "rounded-lg border px-3 py-2 text-left text-sm",
                    selectedPageId === page.id ? "border-pine bg-mist text-ink" : "border-ink/10 bg-white text-ink/75",
                    pageMissingCount ? "border-clay/30" : "",
                  )}
                >
                  <span className="flex items-start justify-between gap-2">
                    <span className="font-semibold">{index + 1}. {page.title}</span>
                    <span className="flex shrink-0 flex-wrap justify-end gap-1">
                      {pageMissingCount ? (
                        <span className="rounded-full bg-clay/10 px-2 py-0.5 text-[11px] font-semibold text-clay">
                          {pageMissingCount} missing
                        </span>
                      ) : pageComplete ? (
                        <span className="rounded-full bg-pine/10 px-2 py-0.5 text-[11px] font-semibold text-pine">
                          Done
                        </span>
                      ) : null}
                      {manualFlagCount ? (
                        <span className="rounded-full bg-sand/55 px-2 py-0.5 text-[11px] font-semibold text-ink/70">
                          {manualFlagCount}
                        </span>
                      ) : null}
                    </span>
                  </span>
                  <span className="mt-1 block text-xs text-ink/55">{page.pdf_part}</span>
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
                  <p className="text-xs uppercase tracking-[0.2em] text-pine/80">{selectedPage.pdf_part}</p>
                  <h2 className="font-display text-2xl text-ink">{selectedPage.title}</h2>
                  <p className="mt-1 text-sm text-ink/60">Local PDF pages {selectedPage.local_pdf_pages.join(", ")}</p>
                </div>
                <button
                  type="button"
                  onClick={saveCurrentPage}
                  disabled={isPending}
                  className="rounded-lg bg-pine px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
                >
                  {isPending ? "Saving..." : "Save page"}
                </button>
              </div>

              {pageFlags.length ? (
                <div className="mb-5 grid gap-2">
                  {pageFlags.map((flag) => (
                    <div key={`${flag.question_id}-${flag.code}`} className={classNames("rounded-lg border p-3 text-sm", flagTone(flag))}>
                      <p className="font-semibold">{formatStatus(flag.code)}</p>
                      <p className="mt-1 leading-6">{flag.description}</p>
                    </div>
                  ))}
                </div>
              ) : null}

              {manualReviewItems.length ? (
                <div className="mb-5 rounded-lg border border-sand/50 bg-sand/15 p-3 text-sm text-ink/72">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <p className="font-semibold text-ink">Come-back questions</p>
                    <p className="text-xs uppercase tracking-[0.14em] text-ink/50">
                      {manualReviewItems.length} marked
                    </p>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {manualReviewItems.map((item) => (
                      <button
                        key={item.questionId}
                        type="button"
                        onClick={() => setSelectedPageId(item.pageId)}
                        className="max-w-full rounded-full border border-ink/10 bg-white px-3 py-1.5 text-left text-xs font-semibold text-ink/70 transition hover:border-pine/30 hover:text-pine"
                      >
                        {item.pageTitle}: {item.label}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              {selectedPage.questions.some((question) => question.id === "beneficiary_employment_history") ? (
                <div className="mb-5 rounded-lg border border-pine/20 bg-mist p-4 text-sm text-ink">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <p className="font-semibold text-ink">USCIS Part 4 employment and education history</p>
                      <p className="mt-1 leading-6 text-ink/70">
                        Enter the current U.S. status first. For this sample, that should be unemployment supported by husband, then the Colombia school belongs in the outside-U.S. school section.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={useHappyPathEmploymentDefaults}
                      className="w-fit shrink-0 rounded-lg border border-pine bg-white px-3 py-2 text-xs font-semibold text-pine"
                    >
                      Use sample defaults
                    </button>
                  </div>
                </div>
              ) : null}

              <div className="grid gap-4">
                {selectedPage.questions.map((question) => (
                  <div
                    key={question.id}
                    className={classNames(
                      "grid gap-2 rounded-lg border p-4",
                      missingRequiredQuestionIds.has(question.id)
                        ? "border-clay/35 bg-clay/5"
                        : manualFlags[question.id]
                          ? "border-sand/60 bg-sand/15"
                          : "border-ink/10 bg-paper/55",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <span className="text-sm font-semibold text-ink">
                        {question.label}
                        {question.required ? <span className="text-clay"> *</span> : null}
                      </span>
                      <div className="flex shrink-0 items-center gap-2">
                        {missingRequiredQuestionIds.has(question.id) ? (
                          <span className="rounded-full bg-clay/10 px-2.5 py-1 text-xs font-semibold text-clay">
                            Missing
                          </span>
                        ) : null}
                        <button
                          type="button"
                          aria-pressed={Boolean(manualFlags[question.id])}
                          onClick={() => toggleManualFlag(question)}
                          disabled={isPending}
                          className={classNames(
                            "rounded-full border px-3 py-1 text-xs font-semibold transition disabled:opacity-55",
                            manualFlags[question.id]
                              ? "border-sand bg-sand/45 text-ink"
                              : "border-ink/10 bg-white text-ink/55 hover:border-sand/70 hover:text-ink",
                          )}
                        >
                          {manualFlags[question.id] ? "Flagged" : "Come back"}
                        </button>
                        <QuestionHelpButton question={question} />
                      </div>
                    </div>
                    {question.plain_language ? (
                      <span className="text-xs leading-5 text-ink/70">{question.plain_language}</span>
                    ) : null}
                    <QuestionControl question={question} value={answers[question.id]} onChange={(value) => updateAnswer(question.id, value)} />
                    <span className="text-xs text-ink/55">
                      {question.pdf_ref}
                      {question.db_path ? ` · maps to ${question.db_path}` : ""}
                    </span>
                    {question.help_text ? <span className="text-xs leading-5 text-ink/65">{question.help_text}</span> : null}
                    {sourceLabel(answerSources[question.id]) ? (
                      <span className="text-xs font-semibold text-pine">{sourceLabel(answerSources[question.id])}</span>
                    ) : null}
                  </div>
                ))}
              </div>
            </>
          ) : null}
        </section>
      </section>

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
            <a key={source.label} href={source.url.startsWith("http") ? source.url : undefined} className="rounded-lg border border-ink/10 bg-paper/50 p-3 text-sm text-ink/75">
              <span className="font-semibold text-ink">{source.label}</span>
              <span className="mt-1 block leading-6">{source.notes}</span>
            </a>
          ))}
        </div>
      </section>
    </main>
  );
}

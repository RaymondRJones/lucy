"use client";

import { useEffect, useMemo, useRef, useState, useTransition } from "react";

import { AppShell } from "@/components/app-shell";
import {
  CaseBar,
  ComeBackList,
  ComeBackToggle,
  FormCompleteNotice,
  FormTabs,
  GeneratedPdfNotice,
  HelpPopover,
  MissingAnswers,
  PageFooterActions,
  PageNav,
  QuestionCard,
  SourcesDisclosure,
} from "@/components/form-workspace";
import { LoadingState, YesNoControl, Notice, PageHeader, StatusMessage, buttonClass, cardClass, eyebrowClass } from "@/components/ui";
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
import { useUnsavedChangesGuard } from "@/lib/unsaved-changes";
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
  if (["address_list", "employment_history_list", "benefit_history_list", "entry_list"].includes(question.answer_type)) {
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
  return "border-line bg-white text-ink";
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
    return null;
  }
  if (source.source_type === "case_intake") {
    return "Filled from your other answers";
  }
  return `Filled from ${formatStatus(source.source_type)}`;
}

function QuestionHelpButton({ question }: { question: I485Question }) {
  if (!question.deep_explanation) {
    return null;
  }

  return (
    <HelpPopover label={`How to answer: ${question.label}`} title="How to answer this">
      <p>{question.deep_explanation}</p>
      {question.teaching_source ? (
        <p className="mt-2 border-t border-line pt-2 text-xs text-muted">
          Based on {question.teaching_source.label}, fetched {question.teaching_source.fetched_on}.
        </p>
      ) : null}
    </HelpPopover>
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
  // Optional lists start empty so their per-entry required markers do not read as required questions.
  const visibleEntries = entries.length ? entries : question.required ? [emptyRepeatableEntry(question)] : [];
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
      {!visibleEntries.length ? (
        <p className="rounded-lg border border-dashed border-line-strong px-3 py-2.5 text-sm text-muted">
          None added. Add an entry only if this applies.
        </p>
      ) : null}
      {visibleEntries.map((entry, index) => {
        const isOverflow = formEntryLimit !== null && index >= formEntryLimit;
        return (
          <div key={index} className="grid gap-3 rounded-lg border border-line bg-white p-3">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                Entry {index + 1}{isOverflow ? " · Part 14" : ""}
              </p>
              {visibleEntries.length > 1 || !question.required ? (
                <button
                  type="button"
                  onClick={() => removeEntry(index)}
                  className={buttonClass("ghost", "sm", "text-red-800 hover:bg-red-50")}
                >
                  Remove
                </button>
              ) : null}
            </div>
            {typeof entry.notes === "string" && entry.notes.trim() && !fields.some((field) => field.key === "notes") ? (
              <div className="flex items-start justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-950">
                <p>
                  <span className="font-semibold">Saved earlier as free text, and prints in {question.overflow_pdf_ref ?? "additional information"}:</span>{" "}
                  {entry.notes}
                </p>
                <button
                  type="button"
                  onClick={() => updateEntry(index, "notes", "")}
                  className="shrink-0 rounded-lg border border-amber-300 px-3 py-1 font-semibold"
                >
                  Remove note
                </button>
              </div>
            ) : null}
            <div className="grid gap-3 md:grid-cols-2">
              {fields.map((field) => {
                const fieldLabel = `${field.label}${field.required ? " *" : ""}`;
                if (field.type === "textarea") {
                  return (
                    <label key={field.key} className="grid gap-1 md:col-span-2">
                      <span className="text-sm font-medium text-ink">{fieldLabel}</span>
                      <textarea
                        value={fieldValue(entry[field.key])}
                        onChange={(event) => updateEntry(index, field.key, event.target.value)}
                        rows={2}
                        className="w-full rounded-lg border border-line-strong bg-white px-3 py-2 text-sm leading-6 text-ink transition-colors hover:border-ink/40"
                      />
                    </label>
                  );
                }
                if (field.type === "select") {
                  return (
                    <label key={field.key} className="grid gap-1">
                      <span className="text-sm font-medium text-ink">{fieldLabel}</span>
                      <select
                        value={fieldValue(entry[field.key])}
                        onChange={(event) => updateEntry(index, field.key, event.target.value)}
                        className="h-10 w-full rounded-lg border border-line-strong bg-white px-3 text-sm text-ink transition-colors hover:border-ink/40"
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
                    <label key={field.key} className="flex items-center gap-2 rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink">
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
                    <span className="text-sm font-medium text-ink">{fieldLabel}</span>
                    <input
                      type={field.type === "date" ? "date" : "text"}
                      value={fieldValue(entry[field.key])}
                      onChange={(event) => updateEntry(index, field.key, event.target.value)}
                      className="h-10 w-full rounded-lg border border-line-strong bg-white px-3 text-sm text-ink transition-colors hover:border-ink/40"
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
        className={buttonClass("secondary", "sm", "w-fit")}
      >
        + Add {visibleEntries.length ? "another entry" : "an entry"}
      </button>
    </div>
  );
}

export function StructuredAddressControl({
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
    <div className="grid gap-3 rounded-lg border border-line bg-white p-3 md:grid-cols-2">
      {fields.map((field) => {
        const fieldLabel = `${field.label}${field.required ? " *" : ""}`;
        if (field.type === "select") {
          return (
            <label key={field.key} className="grid gap-1">
              <span className="text-sm font-medium text-ink">{fieldLabel}</span>
              <select
                value={fieldValue(entry[field.key])}
                onChange={(event) => updateField(field.key, event.target.value)}
                className="h-10 w-full rounded-lg border border-line-strong bg-white px-3 text-sm text-ink transition-colors hover:border-ink/40"
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
            <label key={field.key} className="flex items-center gap-2 rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink">
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
            <span className="text-sm font-medium text-ink">{fieldLabel}</span>
            <input
              type={field.type === "date" ? "date" : "text"}
              value={fieldValue(entry[field.key])}
              onChange={(event) => updateField(field.key, event.target.value)}
              className="h-10 w-full rounded-lg border border-line-strong bg-white px-3 text-sm text-ink transition-colors hover:border-ink/40"
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

  if (["address_list", "employment_history_list", "benefit_history_list", "entry_list"].includes(question.answer_type) && question.entry_fields?.length) {
    return <RepeatableHistoryControl question={question} value={value} onChange={onChange} />;
  }

  if (question.answer_type === "boolean") {
    return <YesNoControl value={value} onChange={onChange} label={question.label} />;
  }

  if (question.answer_type === "select") {
    return (
      <select
        aria-label={question.label}
        value={fieldValue(value)}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 w-full rounded-lg border border-line-strong bg-white px-3 text-sm text-ink transition-colors hover:border-ink/40"
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
          <label key={option.value} className="flex items-center gap-2 rounded-lg border border-line bg-white p-3 text-sm">
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
          <label key={option.value} className="flex items-center gap-2 rounded-lg border border-line bg-white p-3 text-sm">
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
        aria-label={question.label}
        value={fieldValue(value)}
        onChange={(event) => onChange(event.target.value)}
        rows={3}
        className="w-full rounded-lg border border-line-strong bg-white px-3 py-2 text-sm leading-6 text-ink transition-colors hover:border-ink/40"
      />
    );
  }

  const inputType = question.answer_type === "date" ? "date" : question.answer_type === "number" ? "number" : "text";
  return (
    <input
      aria-label={question.label}
      type={inputType}
      value={fieldValue(value)}
      onChange={(event) => onChange(normalizeInputValue(question, event.target.value))}
      className="h-10 w-full rounded-lg border border-line-strong bg-white px-3 text-sm text-ink transition-colors hover:border-ink/40"
    />
  );
}

export function I485IngestionWorkspace({ initialCaseId }: { initialCaseId?: string }) {
  const [caseId, setCaseId] = useState<string | null>(null);
  const [questionnaire, setQuestionnaire] = useState<I485Questionnaire | null>(null);
  const [selectedPageId, setSelectedPageId] = useState<string>("");
  const [isDirty, setIsDirty] = useState(false);
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
            ? `Filled in ${result.imported_count} ${result.imported_count === 1 ? "answer" : "answers"} from your other forms. Check them before saving.`
            : null,
        );
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "Could not sync I-485 answers from case data."));
  }, [caseId, loadedCaseStateKey]);

  function refreshPreview(activeCaseId: string) {
    getI485FormFillPreview(activeCaseId)
      .then((preview) => setFillPreview(preview))
      .catch((error) => setMessage(error instanceof Error ? error.message : "Could not refresh I-485 fill preview."));
  }

  useUnsavedChangesGuard(isDirty);

  function applyState(state: I485IngestionState) {
    setAnswers(state.answers);
    setIsDirty(false);
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
    setIsDirty(true);
  }

  // Unsaved edits on the current page are saved before moving to another page.
  function goToPage(pageId: string) {
    if (pageId === selectedPage?.id) {
      return;
    }
    if (isDirty && caseId && selectedPage) {
      saveCurrentPage(false, pageId);
      return;
    }
    setSelectedPageId(pageId);
  }

  function useHappyPathEmploymentDefaults() {
    const foreignSchool = firstForeignSchoolEntry(answers.beneficiary_employment_history);
    setIsDirty(true);
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
    return pageMissingCount === 0 && requiredQuestions.every((question) => answers[question.id] === false || hasMeaningfulEntryValue(answers[question.id]));
  }

  function pageAnswersForSave(page: I485QuestionnairePage) {
    return Object.fromEntries(
      page.questions
        .map((question) => [question.id, cleanQuestionAnswer(question, answers[question.id])] as const)
        .filter(([, value]) => value !== undefined),
    );
  }

  function saveCurrentPage(moveNext = false, targetPageId?: string) {
    if (!caseId || !selectedPage) {
      setMessage("Create or open a case first, then return to this I-485 page.");
      return;
    }
    const pageAnswers = pageAnswersForSave(selectedPage);
    startTransition(() => {
      saveI485Page(caseId, selectedPage.id, pageAnswers, manualFlagsForPage(selectedPage, manualFlags))
        .then((state) => {
          applyState(state);
          setMessage(`Saved "${selectedPage.title}".`);
          if (targetPageId) {
            setSelectedPageId(targetPageId);
          } else if (moveNext && questionnaire) {
            const index = questionnaire.pages.findIndex((page) => page.id === selectedPage.id);
            const nextPage = questionnaire.pages[index + 1];
            if (nextPage) {
              setSelectedPageId(nextPage.id);
              document.getElementById("form-page")?.scrollIntoView({ behavior: "smooth", block: "start" });
            }
          }
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

  function selectCase(nextCase: CaseSummary) {
    rememberCaseId(nextCase.id);
    window.location.assign(`/i485-ingestion?caseId=${encodeURIComponent(nextCase.id)}`);
  }

  if (!questionnaire) {
    return (
      <AppShell step="forms" caseId={caseId}>
        <LoadingState label="Loading I-485 questions..." />
      </AppShell>
    );
  }

  const pageIndex = questionnaire.pages.findIndex((page) => page.id === selectedPage?.id);
  const hasNextPage = pageIndex >= 0 && pageIndex < questionnaire.pages.length - 1;
  const nextStepHref = nextFormOption
    ? packetFormHref(nextFormOption.formKey, caseId)
    : caseId
      ? `/manage-tasks?caseId=${encodeURIComponent(caseId)}`
      : "/manage-tasks";

  return (
    <AppShell step="forms" caseId={caseId}>
      <FormTabs options={formFlowOptions} activeKey="i485" caseId={caseId} />

      <PageHeader
        eyebrow={"Step 2 \u00b7 I-485"}
        title="Application to Adjust Status"
        description="Fourteen pages that follow Form I-485. Answers you gave on other forms are filled in for you to confirm."
        actions={
          <>
            <details className="relative">
              <summary className={buttonClass("secondary", "md", "cursor-pointer list-none [&::-webkit-details-marker]:hidden")}>
                Import answers {"\u25BE"}
              </summary>
              <div className="absolute right-0 z-20 mt-2 grid w-64 gap-1 rounded-lg border border-line bg-white p-1.5 shadow-pop">
                <button
                  type="button"
                  onClick={importFromCaseData}
                  disabled={!caseId || isPending}
                  className="rounded-md px-3 py-2 text-left text-sm hover:bg-paper disabled:opacity-50"
                >
                  <span className="block font-semibold text-ink">Refill from case data</span>
                  <span className="block text-xs text-muted">Copies answers saved on other forms</span>
                </button>
                <button
                  type="button"
                  onClick={importFromUpload}
                  disabled={!caseId || isPending}
                  className="rounded-md px-3 py-2 text-left text-sm hover:bg-paper disabled:opacity-50"
                >
                  <span className="block font-semibold text-ink">Read an uploaded I-485</span>
                  <span className="block text-xs text-muted">Pulls answers from a filled PDF you uploaded</span>
                </button>
              </div>
            </details>
            <button type="button" onClick={generatePdf} disabled={!caseId || isPending} className={buttonClass("primary", "md")}>
              Preview draft PDF
            </button>
          </>
        }
      />

      <StatusMessage message={message} />

      {generatedPdf ? (
        <GeneratedPdfNotice
          path={generatedPdf.generated_pdf}
          href={apiUrl(generatedPdf.download_url)}
          fieldCount={generatedPdf.field_count}
          mappedCount={generatedPdf.mapped_question_count}
          ready={generatedPdf.ready_for_pdf_generation}
        />
      ) : null}

      {isFormComplete ? (
        <FormCompleteNotice
          formCode="I-485"
          nextHref={nextStepHref}
          nextLabel={nextFormOption ? `Continue to ${nextFormOption.label}` : "Continue to checklist"}
        />
      ) : null}

      <CaseBar
        caseId={caseId ?? ""}
        onSelect={selectCase}
        disabled={isPending}
        stats={
          fillPreview
            ? [
                { label: "fields filled", value: fillPreview.field_count },
                { label: "missing", value: fillPreview.missing_required_count, tone: fillPreview.missing_required_count ? "warning" : undefined },
                { label: "risk flags", value: fillPreview.blocking_flag_count, tone: fillPreview.blocking_flag_count ? "danger" : undefined },
                { label: "to review", value: fillPreview.low_confidence_count },
              ]
            : undefined
        }
      />

      <MissingAnswers items={visibleMissingRequiredItems} hiddenCount={hiddenMissingRequiredCount} onSelect={goToPage} />

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <PageNav
          items={questionnaire.pages.map((page) => ({
            id: page.id,
            title: page.title,
            subtitle: page.pdf_part,
            missingCount: missingRequiredItems.filter((item) => item.page_id === page.id).length,
            complete: isPageComplete(page),
            flagCount: manualFlagCountForPage(page, manualFlags),
          }))}
          selectedId={selectedPageId}
          onSelect={goToPage}
          completionPct={completionPct}
          statusLabel={formatStatus(readiness)}
        />

        <section id="form-page" aria-labelledby="form-page-heading" className={classNames(cardClass, "scroll-mt-24 p-5 md:p-6")}>
          {selectedPage ? (
            <>
              <div className="mb-5">
                <p className={eyebrowClass}>
                  {selectedPage.pdf_part}
                  {selectedPage.local_pdf_pages.length ? ` \u00b7 PDF page ${selectedPage.local_pdf_pages.join(", ")}` : ""}
                </p>
                <h2 id="form-page-heading" className="mt-1 font-display text-2xl text-ink">
                  {selectedPage.title}
                </h2>
              </div>

              {pageFlags.length ? (
                <div className="mb-5 grid gap-2">
                  {pageFlags.map((flag) => (
                    <div key={`${flag.question_id}-${flag.code}`} className={classNames("rounded-lg border px-4 py-3 text-sm", flagTone(flag))}>
                      <p className="font-semibold capitalize">{formatStatus(flag.code)}</p>
                      <p className="mt-1 leading-6">{flag.description}</p>
                    </div>
                  ))}
                </div>
              ) : null}

              <ComeBackList items={manualReviewItems} onSelect={goToPage} />

              {selectedPage.questions.some((question) => question.id === "beneficiary_employment_history") ? (
                <Notice
                  tone="info"
                  className="mb-5"
                  title="Part 4 employment and education history"
                  actions={
                    <button type="button" onClick={useHappyPathEmploymentDefaults} className={buttonClass("secondary", "sm")}>
                      Use sample defaults
                    </button>
                  }
                >
                  Enter the current U.S. status first. For this sample, that should be unemployment supported by husband, then the
                  Colombia school belongs in the outside-U.S. school section.
                </Notice>
              ) : null}

              <div className="grid gap-4">
                {selectedPage.questions.map((question) => (
                  <QuestionCard
                    key={question.id}
                    label={question.label}
                    required={question.required}
                    missing={missingRequiredQuestionIds.has(question.id)}
                    flagged={Boolean(manualFlags[question.id])}
                    plainLanguage={question.plain_language}
                    meta={question.pdf_ref}
                    source={sourceLabel(answerSources[question.id])}
                    actions={
                      <>
                        <ComeBackToggle
                          flagged={Boolean(manualFlags[question.id])}
                          onToggle={() => toggleManualFlag(question)}
                          disabled={isPending}
                        />
                        <QuestionHelpButton question={question} />
                      </>
                    }
                  >
                    <QuestionControl question={question} value={answers[question.id]} onChange={(value) => updateAnswer(question.id, value)} />
                    {question.help_text ? <p className="text-xs leading-5 text-muted">{question.help_text}</p> : null}
                  </QuestionCard>
                ))}
              </div>

              <PageFooterActions
                onSave={() => saveCurrentPage(false)}
                onSaveAndNext={() => saveCurrentPage(true)}
                isPending={isPending}
                isDirty={isDirty}
                hasNext={hasNextPage}
              />
            </>
          ) : null}
        </section>
      </div>

      <SourcesDisclosure
        version={questionnaire.version}
        verifiedOn={questionnaire.verified_on}
        officialUrl={questionnaire.official_url}
        sources={questionnaire.sources}
      />
    </AppShell>
  );
}

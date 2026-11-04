"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState, useTransition } from "react";

import { AppShell } from "@/components/app-shell";
import { CaseSelector } from "@/components/case-selector";
import { HelpPopover, PageFooterActions, PageNav, QuestionCard, SourcesDisclosure } from "@/components/form-workspace";
import {
  Badge,
  Card,
  LoadingState,
  PageHeader,
  ProgressBar,
  SectionHeader,
  StatusMessage,
  YesNoControl,
  buttonClass,
  cardClass,
  eyebrowClass,
  hintClass,
  inputClass,
  labelClass,
} from "@/components/ui";
import {
  createCase,
  generateChecklist,
  getCase,
  getPrescreenQuestionnaire,
  getPrescreenState,
  savePrescreenAnswers,
} from "@/lib/api";
import { getSavedCaseId, rememberCaseId } from "@/lib/case-storage";
import { useUnsavedChangesGuard } from "@/lib/unsaved-changes";
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

function sourceLabel(source: string | undefined) {
  if (!source) {
    return null;
  }
  return "Filled from your saved case";
}

const STATUS_DISPLAY: Record<string, { label: string; tone: "success" | "warning" | "danger" | "neutral" }> = {
  happy_path_ready: { label: "Fits the standard path", tone: "success" },
  needs_review: { label: "Needs review", tone: "warning" },
  blocked_needs_review: { label: "Needs professional review", tone: "danger" },
  incomplete: { label: "In progress", tone: "neutral" },
};

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
    <HelpPopover label={`Why we ask: ${question.label}`} title="Why we ask this">
      <p>{question.why || question.help_text}</p>
    </HelpPopover>
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

  function renderBooleanButtons(currentValue: unknown, onValueChange: (nextValue: boolean) => void, label: string) {
    return <YesNoControl value={currentValue} onChange={onValueChange} label={label} />;
  }

  if (question.answer_type === "boolean") {
    return renderBooleanButtons(value, onChange, question.label);
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
    const selected = Array.isArray(value) ? value.map(String) : [];
    return (
      <div className="grid gap-2 sm:grid-cols-2">
        {question.options.map((option) => {
          const isSelected = selected.includes(option.value);
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={isSelected}
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
                  : "border-line-strong bg-white text-ink hover:border-pine/45",
              )}
            >
              <span
                aria-hidden="true"
                className={classNames(
                  "mt-0.5 flex h-4 w-4 items-center justify-center rounded border text-[0.625rem] text-white",
                  isSelected ? "border-pine bg-pine" : "border-line-strong bg-white",
                )}
              >
                {isSelected ? "\u2713" : null}
              </span>
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
        aria-label={question.label}
        value={fieldValue(value)}
        onChange={(event) => onChange(event.target.value)}
        rows={5}
        className="min-h-28 w-full rounded-lg border border-line-strong bg-white px-3 py-3 text-sm leading-6 text-ink focus:border-pine"
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
                <span className="text-sm font-medium text-ink">
                  {field.label}
                  {field.required === false ? <span className="font-normal text-muted"> optional</span> : null}
                </span>
                {renderBooleanButtons(currentValue, (nextValue) => updateGroupField(field.key, nextValue), field.label)}
              </div>
            );
          }

          if (field.type === "select") {
            return (
              <label key={field.key} className="grid gap-1">
                <span className="text-sm font-medium text-ink">
                  {field.label}
                  {field.required === false ? <span className="font-normal text-muted"> optional</span> : null}
                </span>
                <select
                  value={fieldValue(currentValue)}
                  onChange={(event) => updateGroupField(field.key, event.target.value)}
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

          if (field.type === "textarea") {
            return (
              <label key={field.key} className="grid gap-1 md:col-span-2">
                <span className="text-sm font-medium text-ink">
                  {field.label}
                  {field.required === false ? <span className="font-normal text-muted"> optional</span> : null}
                </span>
                <textarea
                  value={fieldValue(currentValue)}
                  onChange={(event) => updateGroupField(field.key, event.target.value)}
                  rows={4}
                  className="min-h-24 w-full rounded-lg border border-line-strong bg-white px-3 py-2 text-sm leading-6 text-ink focus:border-pine"
                />
              </label>
            );
          }

          const inputType = field.type === "date" ? "date" : field.type === "number" ? "number" : "text";
          return (
            <label key={field.key} className="grid gap-1">
              <span className="text-xs font-semibold text-muted">
                {field.label}
                {field.required === false ? <span className="font-normal text-muted"> optional</span> : null}
              </span>
              <input
                type={inputType}
                value={fieldValue(currentValue)}
                placeholder={field.placeholder}
                onChange={(event) => updateGroupField(field.key, event.target.value)}
                className="h-10 w-full rounded-lg border border-line-strong bg-white px-3 text-sm text-ink transition-colors hover:border-ink/40"
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
      aria-label={question.label}
      type={inputType}
      value={fieldValue(value)}
      onChange={(event) => onChange(event.target.value)}
      className="h-10 w-full rounded-lg border border-line-strong bg-white px-3 text-sm text-ink transition-colors hover:border-ink/40"
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
  const [isDirty, setIsDirty] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const loadCase = useCallback(async (caseId: string, successMessage: string | null) => {
    try {
      const [loadedCase, loadedPrescreen] = await Promise.all([getCase(caseId), getPrescreenState(caseId)]);
      rememberCaseId(caseId);
      const url = new URL(window.location.href);
      url.searchParams.set("caseId", caseId);
      window.history.replaceState({}, "", url);
      setCaseSummary(loadedCase);
      setPrescreen(loadedPrescreen);
      setDraftAnswers(loadedPrescreen.answers);
      setIsDirty(false);
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
      void loadCase(storedCaseId, null);
    }
  }, [loadCase]);

  useUnsavedChangesGuard(isDirty);

  const visibleQuestions = useMemo(() => prescreen?.evaluation.visible_questions ?? [], [prescreen]);
  const flags = prescreen?.evaluation.flags ?? [];
  const eliminatedForms = prescreen?.evaluation.eliminated_forms ?? [];
  const includedForms = useMemo(() => prescreen?.evaluation.included_forms ?? [], [prescreen?.evaluation.included_forms]);
  const missingQuestions = visibleQuestions.filter((question) => !questionHasAnswer(question, draftAnswers[question.id]));
  const nextFormOptions = useMemo(() => packetFormsForIncluded(includedForms), [includedForms]);

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
    setIsDirty(true);
  }

  // Unsaved edits on the current page are saved before moving to another page.
  function goToPage(pageId: string) {
    if (pageId === selectedPage?.id) {
      return;
    }
    if (isDirty && caseSummary && selectedPage) {
      saveCurrentPage(false, pageId);
      return;
    }
    setSelectedPageId(pageId);
  }

  function handleCaseSelect(nextCase: CaseSummary) {
    startTransition(() => {
      void loadCase(nextCase.id, `Opened ${nextCase.case_name}.`);
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

  function saveCurrentPage(moveNext: boolean, targetPageId?: string) {
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
          setIsDirty(false);
          if (targetPageId) {
            setSelectedPageId(targetPageId);
          } else if (moveNext) {
            const nextPages = Array.from(new Set(state.evaluation.visible_questions.map((question) => question.section)));
            const currentIndex = nextPages.indexOf(selectedPage.id);
            setSelectedPageId(nextPages[Math.min(currentIndex + 1, Math.max(nextPages.length - 1, 0))] ?? selectedPage.id);
            document.getElementById("form-page")?.scrollIntoView({ behavior: "smooth", block: "start" });
          }
          setMessage(`Saved "${selectedPage.title}".`);
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
      <QuestionCard
        key={question.id}
        label={question.label}
        missing={missing}
        plainLanguage={question.help_text}
        source={sourceLabel(source) ?? (fieldSourceCount ? `${fieldSourceCount} answers filled from your case` : null)}
        actions={<QuestionHelpButton question={question} />}
      >
        <QuestionControl question={question} value={draftAnswers[question.id]} onChange={(value) => updateAnswer(question.id, value)} />
      </QuestionCard>
    );
  }

  if (!questionnaire) {
    return (
      <AppShell step="prescreen" caseId={caseSummary?.id}>
        <LoadingState label="Loading prescreen questions..." />
      </AppShell>
    );
  }

  const selectedIndex = pages.findIndex((page) => page.id === selectedPage?.id);
  const hasNextPage = selectedIndex >= 0 && selectedIndex < pages.length - 1;
  const status = prescreen?.evaluation.status ?? "incomplete";
  const statusInfo = STATUS_DISPLAY[status] ?? { label: formatStatus(status), tone: "neutral" as const };
  const skipItems = prescreen ? [...eliminatedForms, ...(prescreen.evaluation.eliminated_questions ?? [])] : [];
  const prescreenComplete = prescreen?.evaluation.completion_pct === 100;
  const questionnaireGrid = (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
      <PageNav
        items={pages.map((page) => ({
          id: page.id,
          title: page.title,
          subtitle: `${page.answered} of ${page.total} answered`,
          missingCount: page.total - page.answered,
          complete: page.answered === page.total,
          flagCount: flags.filter((flag) => page.questions.some((question) => question.id === flag.question_id)).length,
        }))}
        selectedId={selectedPage?.id ?? ""}
        onSelect={goToPage}
        completionPct={prescreen?.evaluation.completion_pct ?? 0}
        statusLabel={statusInfo.label}
      />

      <section id="form-page" aria-labelledby="prescreen-page-heading" className={classNames(cardClass, "scroll-mt-24 p-5 md:p-6")}>
        {selectedPage ? (
          <>
            <div className="mb-5">
              <p className={eyebrowClass}>
                Page {selectedIndex + 1} of {pages.length}
              </p>
              <h2 id="prescreen-page-heading" className="mt-1 font-display text-2xl text-ink">
                {selectedPage.title}
              </h2>
            </div>

            {pageFlags.length ? (
              <div className="mb-5 grid gap-2">
                {pageFlags.map((flag) => (
                  <div key={`${flag.question_id}-${flag.code}`} className={classNames("rounded-lg border px-4 py-3 text-sm", flagTone(flag))}>
                    <p className="font-semibold">{flag.title}</p>
                    <p className="mt-1 leading-6">{flag.description}</p>
                  </div>
                ))}
              </div>
            ) : null}

            <div className="grid gap-4">{selectedPage.questions.map((question) => renderQuestionCard(question))}</div>

            <PageFooterActions
              onSave={() => saveCurrentPage(false)}
              onSaveAndNext={() => saveCurrentPage(true)}
              isPending={isPending}
              isDirty={isDirty}
              hasNext={hasNextPage}
              disabled={!caseSummary}
            />
          </>
        ) : (
          <p className="text-sm text-muted">Loading this case&apos;s questions...</p>
        )}
      </section>
    </div>
  );

  return (
    <AppShell
      step="prescreen"
      caseId={caseSummary?.id}
      caseName={caseSummary?.case_name}
      readinessLabel={caseSummary?.readiness_label}
    >
      <PageHeader
        eyebrow="Step 1"
        title="Prescreen"
        description="A short set of questions that checks whether your case fits the standard marriage-based path and decides which forms your packet needs."
      />

      <StatusMessage message={message} />

      {!caseSummary ? (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
          <Card aria-labelledby="new-case-heading">
            <SectionHeader
              id="new-case-heading"
              title="Start a new case"
              description="Everything you enter stays on this computer. You can change these details later."
            />
            <form onSubmit={handleCreateCase} className="mt-5 grid gap-4">
              <label className="grid gap-1.5">
                <span className={labelClass}>Case name</span>
                <input
                  required
                  value={caseForm.case_name}
                  onChange={(event) => setCaseForm((current) => ({ ...current, case_name: event.target.value }))}
                  className={inputClass}
                />
              </label>
              <div className="grid gap-4 md:grid-cols-2">
                <label className="grid gap-1.5">
                  <span className={labelClass}>
                    Petitioner email <span className="font-normal text-muted">optional</span>
                  </span>
                  <input
                    type="email"
                    autoComplete="email"
                    value={caseForm.petitioner_email}
                    onChange={(event) => setCaseForm((current) => ({ ...current, petitioner_email: event.target.value }))}
                    className={inputClass}
                  />
                </label>
                <label className="grid gap-1.5">
                  <span className={labelClass}>
                    Beneficiary email <span className="font-normal text-muted">optional</span>
                  </span>
                  <input
                    type="email"
                    value={caseForm.beneficiary_email}
                    onChange={(event) => setCaseForm((current) => ({ ...current, beneficiary_email: event.target.value }))}
                    className={inputClass}
                  />
                </label>
              </div>
              <label className="grid gap-1.5">
                <span className={labelClass}>Beneficiary&apos;s country</span>
                <input
                  value={caseForm.country_of_focus}
                  onChange={(event) => setCaseForm((current) => ({ ...current, country_of_focus: event.target.value }))}
                  className={inputClass}
                />
                <span className={hintClass}>Used for country-specific document tips, such as birth certificates.</span>
              </label>
              <div>
                <button type="submit" disabled={isPending} className={buttonClass("primary", "lg")}>
                  {isPending ? "Creating..." : "Create case and start"}
                </button>
              </div>
            </form>
          </Card>
          <Card aria-labelledby="open-case-heading" className="h-fit">
            <SectionHeader id="open-case-heading" title="Or open a saved case" description="Pick up where you left off." />
            <div className="mt-5">
              <CaseSelector selectedCaseId="" onSelect={handleCaseSelect} disabled={isPending} label="Saved cases" />
            </div>
          </Card>
        </div>
      ) : (
        <>
          <Card className="p-4 md:p-5">
            {prescreen ? (
              <div className="grid gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={statusInfo.tone}>{statusInfo.label}</Badge>
                  <span className="text-sm text-muted">
                    {visibleQuestions.length - missingQuestions.length} of {visibleQuestions.length} answered
                    {flags.length ? ` \u00b7 ${flags.length} ${flags.length === 1 ? "flag" : "flags"}` : ""}
                  </span>
                </div>
                <ProgressBar value={prescreen.evaluation.completion_pct} label="Prescreen answered" />
                {includedForms.length ? (
                  <p className="text-sm leading-6 text-muted">
                    <span className="font-semibold text-ink">Forms in your packet: </span>
                    {includedForms
                      .map((code) => FORM_ACTIONS[code]?.label)
                      .filter(Boolean)
                      .join(", ")}
                  </p>
                ) : null}
              </div>
            ) : null}
          </Card>

          {prescreenComplete ? (
            <Card aria-labelledby="next-form-heading" className="border-pine/30">
              <SectionHeader
                id="next-form-heading"
                eyebrow="Prescreen complete"
                title="Choose a form to fill in next"
                description="Start with the suggested form. Each one opens with the answers you have already given."
                actions={
                  <button
                    type="button"
                    onClick={handleGenerateStarterChecklist}
                    disabled={isPending}
                    className={buttonClass("secondary", "sm")}
                  >
                    Build checklist
                  </button>
                }
              />
              <ul className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {nextFormOptions.map((option, index) => {
                  const isSuggested = index === 0;
                  return (
                    <li key={option.formKey}>
                      <Link
                        href={packetFormHref(option.formKey, caseSummary.id)}
                        className={classNames(
                          "group flex h-full items-start justify-between gap-3 rounded-lg border p-4 text-sm transition-colors",
                          isSuggested ? "border-pine bg-pine-soft hover:bg-mist" : "border-line bg-white hover:border-line-strong hover:bg-paper",
                        )}
                      >
                        <span>
                          <span className="flex flex-wrap items-center gap-2">
                            <span className="text-base font-semibold text-ink">{option.label}</span>
                            {isSuggested ? <Badge tone="accent">Suggested next</Badge> : null}
                          </span>
                          <span className="mt-0.5 block text-muted">{option.detail}</span>
                          <span className="mt-2 block text-xs font-semibold text-muted">{option.phase}</span>
                        </span>
                        <span aria-hidden="true" className="text-lg text-pine transition-transform group-hover:translate-x-0.5">
                          {"\u2192"}
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </Card>
          ) : null}

          {prescreenComplete ? (
            <details className={classNames(cardClass, "group/answers")}>
              <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-3 rounded-xl px-5 py-4 text-sm hover:bg-paper [&::-webkit-details-marker]:hidden">
                <span>
                  <span className="font-semibold text-ink">Edit your prescreen answers</span>
                  <span className="ml-2 text-muted">
                    {visibleQuestions.length} answered across {pages.length} pages
                  </span>
                </span>
                <span aria-hidden="true" className="text-muted transition-transform group-open/answers:rotate-180">
                  {"\u25BE"}
                </span>
              </summary>
              <div className="border-t border-line p-4 md:p-5">
                {questionnaireGrid}
              </div>
            </details>
          ) : (
            questionnaireGrid
          )}

          {skipItems.length ? (
            <details className={classNames(cardClass, "group")}>
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-xl px-5 py-4 text-sm hover:bg-paper [&::-webkit-details-marker]:hidden">
                <span>
                  <span className="font-semibold text-ink">What you can skip</span>
                  <span className="ml-2 text-muted">
                    {skipItems.length} {skipItems.length === 1 ? "form or question" : "forms and questions"} not needed for your answers
                  </span>
                </span>
                <span aria-hidden="true" className="text-muted transition-transform group-open:rotate-180">
                  {"\u25BE"}
                </span>
              </summary>
              <ul className="grid gap-2 border-t border-line px-5 py-4 md:grid-cols-2">
                {skipItems.map((item) => {
                  const key = "form_code" in item ? item.form_code : item.question_id;
                  return (
                    <li key={key} className="rounded-lg border border-line bg-paper px-4 py-3 text-sm">
                      <p className="font-semibold text-ink">{"label" in item ? item.label : key}</p>
                      <p className="mt-0.5 leading-6 text-muted">{item.reason}</p>
                    </li>
                  );
                })}
              </ul>
            </details>
          ) : null}
        </>
      )}

      <SourcesDisclosure
        version={questionnaire.version}
        verifiedOn={questionnaire.verified_on}
        officialUrl={questionnaire.sources[0]?.url}
        sources={questionnaire.sources}
      />
    </AppShell>
  );
}

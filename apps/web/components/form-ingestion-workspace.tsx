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
import { StructuredAddressControl } from "@/components/i485-ingestion-workspace";
import {
  apiUrl,
  generateFormPdf,
  getFormFillPreview,
  getFormIngestionState,
  getFormQuestionnaire,
  getPrescreenState,
  importFormFromCaseData,
  saveFormPage,
} from "@/lib/api";
import { Badge, LoadingState, YesNoControl, PageHeader, StatusMessage, buttonClass, cardClass, eyebrowClass } from "@/components/ui";
import { getSavedCaseId, rememberCaseId } from "@/lib/case-storage";
import { forgetFormStatuses } from "@/lib/form-status";
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
  FormFillPreview,
  FormFlag,
  FormIngestionState,
  FormPdfGenerateResponse,
  FormQuestion,
  FormQuestionnaire,
  FormQuestionnairePage,
  PrescreenState,
} from "@/lib/types";
const SUPPORTED_FORMS = new Set(["i130", "i130a", "i765", "i131", "i864"]);
const MISSING_REQUIRED_DISPLAY_LIMIT = 5;

const US_STATE_OPTIONS = [
  { value: "AL", label: "Alabama" },
  { value: "AK", label: "Alaska" },
  { value: "AZ", label: "Arizona" },
  { value: "AR", label: "Arkansas" },
  { value: "CA", label: "California" },
  { value: "CO", label: "Colorado" },
  { value: "CT", label: "Connecticut" },
  { value: "DE", label: "Delaware" },
  { value: "DC", label: "District of Columbia" },
  { value: "FL", label: "Florida" },
  { value: "GA", label: "Georgia" },
  { value: "HI", label: "Hawaii" },
  { value: "ID", label: "Idaho" },
  { value: "IL", label: "Illinois" },
  { value: "IN", label: "Indiana" },
  { value: "IA", label: "Iowa" },
  { value: "KS", label: "Kansas" },
  { value: "KY", label: "Kentucky" },
  { value: "LA", label: "Louisiana" },
  { value: "ME", label: "Maine" },
  { value: "MD", label: "Maryland" },
  { value: "MA", label: "Massachusetts" },
  { value: "MI", label: "Michigan" },
  { value: "MN", label: "Minnesota" },
  { value: "MS", label: "Mississippi" },
  { value: "MO", label: "Missouri" },
  { value: "MT", label: "Montana" },
  { value: "NE", label: "Nebraska" },
  { value: "NV", label: "Nevada" },
  { value: "NH", label: "New Hampshire" },
  { value: "NJ", label: "New Jersey" },
  { value: "NM", label: "New Mexico" },
  { value: "NY", label: "New York" },
  { value: "NC", label: "North Carolina" },
  { value: "ND", label: "North Dakota" },
  { value: "OH", label: "Ohio" },
  { value: "OK", label: "Oklahoma" },
  { value: "OR", label: "Oregon" },
  { value: "PA", label: "Pennsylvania" },
  { value: "RI", label: "Rhode Island" },
  { value: "SC", label: "South Carolina" },
  { value: "SD", label: "South Dakota" },
  { value: "TN", label: "Tennessee" },
  { value: "TX", label: "Texas" },
  { value: "UT", label: "Utah" },
  { value: "VT", label: "Vermont" },
  { value: "VA", label: "Virginia" },
  { value: "WA", label: "Washington" },
  { value: "WV", label: "West Virginia" },
  { value: "WI", label: "Wisconsin" },
  { value: "WY", label: "Wyoming" },
  { value: "AA", label: "Armed Forces Americas" },
  { value: "AE", label: "Armed Forces Europe" },
  { value: "AP", label: "Armed Forces Pacific" },
  { value: "AS", label: "American Samoa" },
  { value: "FM", label: "Federated States of Micronesia" },
  { value: "GU", label: "Guam" },
  { value: "MH", label: "Marshall Islands" },
  { value: "MP", label: "Northern Mariana Islands" },
  { value: "PR", label: "Puerto Rico" },
  { value: "PW", label: "Palau" },
  { value: "VI", label: "U.S. Virgin Islands" },
];

const US_STATE_CODES = new Set(US_STATE_OPTIONS.map((option) => option.value));
const US_STATE_NAME_TO_CODE = new Map(
  US_STATE_OPTIONS.map((option) => [option.label.toLowerCase().replace(/[^a-z]/g, ""), option.value]),
);

const ADDRESS_STATE_QUESTION_IDS = new Set([
  "beneficiary_mailing_state",
  "beneficiary_physical_state",
  "petitioner_current_state",
]);

type AddressQuestionGroup = {
  id: string;
  title: string;
  description: string;
  questionIds: string[];
};

type QuestionDisplayItem =
  | { type: "group"; group: AddressQuestionGroup; questions: FormQuestion[] }
  | { type: "question"; question: FormQuestion };

const I765_ADDRESS_GROUPS: AddressQuestionGroup[] = [
  {
    id: "i765_mailing_address",
    title: "Mailing address",
    description: "Where USCIS should send notices for this work authorization request.",
    questionIds: [
      "beneficiary_mailing_in_care_of",
      "beneficiary_mailing_address_line1",
      "beneficiary_mailing_address_line2",
      "beneficiary_mailing_city",
      "beneficiary_mailing_state",
      "beneficiary_mailing_zip",
    ],
  },
  {
    id: "i765_physical_address",
    title: "Physical address, if different",
    description: "The applicant's actual residence only when it is not the mailing address.",
    questionIds: [
      "beneficiary_physical_address_line1",
      "beneficiary_physical_address_line2",
      "beneficiary_physical_city",
      "beneficiary_physical_state",
      "beneficiary_physical_zip",
    ],
  },
];

const I765_ADDRESS_GROUP_BY_QUESTION_ID = new Map(
  I765_ADDRESS_GROUPS.flatMap((group) => group.questionIds.map((questionId) => [questionId, group] as const)),
);

function classNames(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

function normalizeFormKey(value: string | null | undefined) {
  const normalized = (value || "i765").toLowerCase().replace("-", "");
  return SUPPORTED_FORMS.has(normalized) ? normalized : "i765";
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

function normalizeUsStateCode(value: unknown) {
  const raw = fieldValue(value).trim();
  if (!raw) {
    return "";
  }
  const upper = raw.toUpperCase();
  if (US_STATE_CODES.has(upper)) {
    return upper;
  }
  return US_STATE_NAME_TO_CODE.get(raw.toLowerCase().replace(/[^a-z]/g, "")) ?? "";
}

function isAddressStateQuestion(question: FormQuestion) {
  return ADDRESS_STATE_QUESTION_IDS.has(question.id);
}

function isPositiveIntegerQuestion(question: FormQuestion) {
  return question.id === "i131_expected_trip_length";
}

function normalizeQuestionAnswerForSave(question: FormQuestion, value: unknown) {
  if (isAddressStateQuestion(question)) {
    return normalizeUsStateCode(value) || value;
  }
  if (isPositiveIntegerQuestion(question)) {
    const digits = fieldValue(value).replace(/\D/g, "");
    return digits ? Number(digits) : "";
  }
  return value;
}

function hasMeaningfulValue(value: unknown): boolean {
  if (value === null || value === undefined || value === "" || value === false) {
    return false;
  }
  if (Array.isArray(value)) {
    return value.some(hasMeaningfulValue);
  }
  if (typeof value === "object") {
    return Object.values(value).some(hasMeaningfulValue);
  }
  return true;
}

function normalizeInputValue(question: FormQuestion, rawValue: string | boolean | string[]) {
  if (isPositiveIntegerQuestion(question)) {
    const digits = String(rawValue).replace(/\D/g, "");
    return digits ? Number(digits) : "";
  }
  if (question.answer_type === "number") {
    if (rawValue === "") {
      return "";
    }
    return Number(rawValue);
  }
  return rawValue;
}

function flagTone(flag: FormFlag) {
  if (flag.severity === "blocking") {
    return "border-red-200 bg-red-50 text-red-950";
  }
  if (flag.category === "outside_niche") {
    return "border-amber-200 bg-amber-50 text-amber-950";
  }
  return "border-line bg-white text-ink";
}

function isChecked(value: unknown, option: string) {
  return Array.isArray(value) && value.includes(option);
}

function sourceLabel(source: FormIngestionState["answer_sources"][string] | undefined) {
  if (!source) {
    return null;
  }
  if (source.source_type === "user") {
    return null;
  }
  if (source.source_type === "case_intake") {
    return "Filled from your other answers";
  }
  return `Filled from ${formatStatus(source.source_type)}`;
}

function buildQuestionDisplayItems(formKey: string, page: FormQuestionnairePage): QuestionDisplayItem[] {
  if (formKey !== "i765" || page.id !== "i765_page_02_addresses") {
    return page.questions.map((question) => ({ type: "question", question }));
  }

  const questionsById = new Map(page.questions.map((question) => [question.id, question]));
  const renderedGroupIds = new Set<string>();
  const items: QuestionDisplayItem[] = [];

  for (const question of page.questions) {
    const group = I765_ADDRESS_GROUP_BY_QUESTION_ID.get(question.id);
    if (!group) {
      items.push({ type: "question", question });
      continue;
    }
    if (renderedGroupIds.has(group.id)) {
      continue;
    }
    renderedGroupIds.add(group.id);
    items.push({
      type: "group",
      group,
      questions: group.questionIds.map((questionId) => questionsById.get(questionId)).filter((entry): entry is FormQuestion => Boolean(entry)),
    });
  }

  return items;
}

function QuestionHelpButton({ question }: { question: FormQuestion }) {
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

function QuestionControl({
  question,
  value,
  onChange,
}: {
  question: FormQuestion;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
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

  if (isAddressStateQuestion(question)) {
    return (
      <select
        aria-label={question.label}
        value={normalizeUsStateCode(value)}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 w-full rounded-lg border border-line-strong bg-white px-3 text-sm text-ink transition-colors hover:border-ink/40"
      >
        <option value="">Select</option>
        {US_STATE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    );
  }

  if (isPositiveIntegerQuestion(question)) {
    return (
      <input
        aria-label={question.label}
        type="text"
        inputMode="numeric"
        pattern="[0-9]*"
        value={fieldValue(value).replace(/\D/g, "")}
        onChange={(event) => onChange(normalizeInputValue(question, event.target.value))}
        className="h-10 w-full rounded-lg border border-line-strong bg-white px-3 text-sm text-ink transition-colors hover:border-ink/40"
      />
    );
  }

  if (question.answer_type === "address" && question.entry_fields?.length) {
    return <StructuredAddressControl question={question} value={value} onChange={onChange} />;
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

export function FormIngestionWorkspace({
  initialCaseId,
  initialFormKey,
}: {
  initialCaseId?: string;
  initialFormKey?: string;
}) {
  const [formKey] = useState(normalizeFormKey(initialFormKey));
  const [caseId, setCaseId] = useState<string | null>(null);
  const [questionnaire, setQuestionnaire] = useState<FormQuestionnaire | null>(null);
  const [selectedPageId, setSelectedPageId] = useState<string>("");
  const [isDirty, setIsDirty] = useState(false);
  // Missing answers are highlighted only on pages the user has saved or left, not on first view.
  const [attemptedPageIds, setAttemptedPageIds] = useState<Set<string>>(new Set());
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [answerSources, setAnswerSources] = useState<FormIngestionState["answer_sources"]>({});
  const [manualFlags, setManualFlags] = useState<ManualQuestionFlags>({});
  const [flags, setFlags] = useState<FormFlag[]>([]);
  const [fillPreview, setFillPreview] = useState<FormFillPreview | null>(null);
  const [generatedPdf, setGeneratedPdf] = useState<FormPdfGenerateResponse | null>(null);
  const [prescreen, setPrescreen] = useState<PrescreenState | null>(null);
  const [completionPct, setCompletionPct] = useState(0);
  const [readiness, setReadiness] = useState("not_loaded");
  const [message, setMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const [loadedCaseStateKey, setLoadedCaseStateKey] = useState<string | null>(null);
  const autoSyncKeyRef = useRef<string | null>(null);
  const canGeneratePdf = Boolean(questionnaire?.local_template_pdf);

  useEffect(() => {
    if (initialCaseId) {
      rememberCaseId(initialCaseId);
      setCaseId(initialCaseId);
      return;
    }
    setCaseId(getSavedCaseId());
  }, [initialCaseId]);

  useEffect(() => {
    setQuestionnaire(null);
    setSelectedPageId("");
    setAnswers({});
    setAnswerSources({});
    setManualFlags({});
    setFlags([]);
    setFillPreview(null);
    setGeneratedPdf(null);
    setCompletionPct(0);
    setReadiness("not_loaded");
    getFormQuestionnaire(formKey)
      .then((payload) => {
        setQuestionnaire(payload);
        setSelectedPageId(payload.pages[0]?.id ?? "");
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "Could not load form questionnaire."));
  }, [formKey]);

  useEffect(() => {
    if (!caseId) {
      return;
    }
    const stateKey = `${caseId}:${formKey}`;
    setLoadedCaseStateKey(null);
    getPrescreenState(caseId)
      .then(setPrescreen)
      .catch(() => setPrescreen(null));
    getFormIngestionState(caseId, formKey)
      .then((state) => {
        setAnswers(state.answers);
        setAnswerSources(state.answer_sources);
        setManualFlags(normalizeManualQuestionFlags(state.manual_flags));
        setFlags(state.evaluation.flags);
        setCompletionPct(state.evaluation.completion_pct);
        setReadiness(state.evaluation.readiness);
        return getFormFillPreview(caseId, formKey);
      })
      .then((preview) => {
        setFillPreview(preview);
        setLoadedCaseStateKey(stateKey);
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "Could not load saved form answers."));
  }, [caseId, formKey]);

  useEffect(() => {
    if (!caseId) {
      return;
    }
    const stateKey = `${caseId}:${formKey}`;
    if (loadedCaseStateKey !== stateKey || autoSyncKeyRef.current === stateKey) {
      return;
    }
    autoSyncKeyRef.current = stateKey;
    importFormFromCaseData(caseId, formKey)
      .then((result) => {
        setAnswers(result.state.answers);
        setAnswerSources(result.state.answer_sources);
        setManualFlags(normalizeManualQuestionFlags(result.state.manual_flags));
        setFlags(result.state.evaluation.flags);
        setCompletionPct(result.state.evaluation.completion_pct);
        setReadiness(result.state.evaluation.readiness);
        getFormFillPreview(caseId, formKey)
          .then((preview) => setFillPreview(preview))
          .catch((error) => setMessage(error instanceof Error ? error.message : "Could not refresh form fill preview."));
        setMessage(
          result.imported_count
            ? `Filled in ${result.imported_count} ${result.imported_count === 1 ? "answer" : "answers"} from your other forms. Check them before saving.`
            : null,
        );
      })
      .catch((error) => setMessage(error instanceof Error ? error.message : "Could not sync answers from case data."));
  }, [caseId, formKey, loadedCaseStateKey]);

  function refreshPreview(activeCaseId: string) {
    getFormFillPreview(activeCaseId, formKey)
      .then((preview) => setFillPreview(preview))
      .catch((error) => setMessage(error instanceof Error ? error.message : "Could not refresh form fill preview."));
  }

  useUnsavedChangesGuard(isDirty);

  function applyState(state: FormIngestionState) {
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

  const selectedPage = useMemo<FormQuestionnairePage | null>(() => {
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
    return ensurePacketFormOption(packetFormsForIncluded(prescreen?.evaluation.included_forms), formKey);
  }, [formKey, prescreen]);
  const nextFormOption = useMemo(() => nextPacketFormOption(formFlowOptions, formKey), [formFlowOptions, formKey]);
  const isFormComplete = completionPct === 100 && !missingRequiredItems.length;
  const selectedPageItems = useMemo(
    () => (selectedPage ? buildQuestionDisplayItems(formKey, selectedPage) : []),
    [formKey, selectedPage],
  );

  function updateAnswer(questionId: string, value: unknown) {
    setAnswers((current) => ({ ...current, [questionId]: value }));
    setIsDirty(true);
  }

  function showMissing(questionId: string) {
    return missingRequiredQuestionIds.has(questionId) && Boolean(selectedPage && attemptedPageIds.has(selectedPage.id));
  }

  // Unsaved edits on the current page are saved before moving to another page.
  function goToPage(pageId: string) {
    if (pageId === selectedPage?.id) {
      return;
    }
    if (selectedPage) {
      const leftPageId = selectedPage.id;
      setAttemptedPageIds((current) => new Set(current).add(leftPageId));
    }
    if (isDirty && caseId && selectedPage) {
      saveCurrentPage(false, pageId);
      return;
    }
    setSelectedPageId(pageId);
  }

  function isPageComplete(page: FormQuestionnairePage) {
    const requiredQuestions = page.questions.filter((question) => question.required);
    if (!requiredQuestions.length) {
      return false;
    }
    const pageMissingCount = missingRequiredItems.filter((item) => item.page_id === page.id).length;
    return pageMissingCount === 0 && requiredQuestions.every((question) => answers[question.id] === false || hasMeaningfulValue(answers[question.id]));
  }

  function pageAnswersForSave(page: FormQuestionnairePage) {
    return Object.fromEntries(
      page.questions
        .map((question) => [question.id, normalizeQuestionAnswerForSave(question, answers[question.id])])
        .filter(([, value]) => value !== undefined),
    );
  }

  function saveCurrentPage(moveNext = false, targetPageId?: string) {
    if (!caseId || !selectedPage) {
      setMessage("Create or open a case first, then return to this form page.");
      return;
    }
    const pageAnswers = pageAnswersForSave(selectedPage);
    startTransition(() => {
      saveFormPage(caseId, formKey, selectedPage.id, pageAnswers, manualFlagsForPage(selectedPage, manualFlags))
        .then((state) => {
          applyState(state);
          forgetFormStatuses(caseId);
          setAttemptedPageIds((current) => new Set(current).add(selectedPage.id));
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
        .catch((error) => setMessage(error instanceof Error ? error.message : "Could not save this form page."));
    });
  }

  function toggleManualFlag(question: FormQuestion) {
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
      saveFormPage(
        caseId,
        formKey,
        selectedPage.id,
        pageAnswersForSave(selectedPage),
        manualFlagsForPage(selectedPage, nextFlags),
      )
        .then((state) => {
          applyState(state);
          setMessage(nextFlags[question.id] ? "Marked for later review." : "Removed the manual review mark.");
        })
        .catch((error) => setMessage(error instanceof Error ? error.message : "Could not update the manual mark."));
    });
  }

  function renderQuestionCard(question: FormQuestion) {
    return (
      <QuestionCard
        key={question.id}
        label={question.label}
        required={question.required}
        missing={showMissing(question.id)}
        flagged={Boolean(manualFlags[question.id])}
        plainLanguage={question.plain_language}
        meta={question.pdf_ref}
        source={sourceLabel(answerSources[question.id])}
        actions={
          <>
            <ComeBackToggle flagged={Boolean(manualFlags[question.id])} onToggle={() => toggleManualFlag(question)} disabled={isPending} />
            <QuestionHelpButton question={question} />
          </>
        }
      >
        <QuestionControl question={question} value={answers[question.id]} onChange={(value) => updateAnswer(question.id, value)} />
      </QuestionCard>
    );
  }

  function renderAddressGroup(group: AddressQuestionGroup, questions: FormQuestion[]) {
    const missingCount = questions.filter((question) => showMissing(question.id)).length;
    const manualFlagCount = questions.filter((question) => manualFlags[question.id]).length;

    return (
      <fieldset
        key={group.id}
        className={classNames(
          "grid gap-4 rounded-lg border bg-white p-4",
          missingCount ? "border-clay/40 shadow-[inset_3px_0_0_0_#a8522f]" : manualFlagCount ? "border-amber-300" : "border-line",
        )}
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <legend className="text-sm font-semibold text-ink">{group.title}</legend>
            <p className="mt-0.5 text-sm leading-6 text-muted">{group.description}</p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-1">
            {missingCount ? <Badge tone="danger">{missingCount} missing</Badge> : null}
            {manualFlagCount ? <Badge tone="warning">{manualFlagCount} marked</Badge> : null}
          </div>
        </div>

        <div className="grid gap-x-4 gap-y-4 md:grid-cols-2">
          {questions.map((question) => (
            <div key={question.id} className={classNames("grid content-start gap-1.5", question.answer_type === "boolean" ? "md:col-span-2" : "")}>
              <div className="flex items-start justify-between gap-2">
                <span className="text-sm font-semibold leading-5 text-ink">
                  {question.label}
                  {question.required ? <span className="text-clay"> *</span> : null}
                  {showMissing(question.id) ? <span className="sr-only"> (missing)</span> : null}
                </span>
                <div className="flex shrink-0 items-center gap-1">
                  <ComeBackToggle
                    compact
                    flagged={Boolean(manualFlags[question.id])}
                    onToggle={() => toggleManualFlag(question)}
                    disabled={isPending}
                  />
                  <QuestionHelpButton question={question} />
                </div>
              </div>
              <QuestionControl question={question} value={answers[question.id]} onChange={(value) => updateAnswer(question.id, value)} />
              <span className={classNames("text-xs", showMissing(question.id) ? "font-semibold text-clay" : "text-muted")}>
                {showMissing(question.id) ? "Required. " : ""}
                {question.pdf_ref}
                {sourceLabel(answerSources[question.id]) ? ` \u00b7 ${sourceLabel(answerSources[question.id])}` : ""}
              </span>
            </div>
          ))}
        </div>
      </fieldset>
    );
  }

  function importFromCaseData() {
    if (!caseId) {
      setMessage("Create or open a case first, then return to this form page.");
      return;
    }
    startTransition(() => {
      importFormFromCaseData(caseId, formKey)
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
      setMessage("Create or open a case first, then return to this form page.");
      return;
    }
    startTransition(() => {
      generateFormPdf(caseId, formKey, { allow_incomplete: true })
        .then((result) => {
          setGeneratedPdf(result);
          setMessage(`Generated draft ${questionnaire?.form_code ?? "form"} PDF at ${result.generated_pdf}.`);
        })
        .catch((error) => setMessage(error instanceof Error ? error.message : "Could not generate the form PDF."));
    });
  }

  function selectCase(nextCase: CaseSummary) {
    rememberCaseId(nextCase.id);
    window.location.assign(`/form-ingestion?form=${encodeURIComponent(formKey)}&caseId=${encodeURIComponent(nextCase.id)}`);
  }

  if (!questionnaire) {
    return (
      <AppShell step="forms" caseId={caseId}>
        {message ? <StatusMessage message={message} /> : <LoadingState label="Loading form questions..." />}
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
      <FormTabs options={formFlowOptions} activeKey={formKey} caseId={caseId} />

      <PageHeader
        eyebrow={`Step 2 \u00b7 ${questionnaire.form_code}`}
        title={questionnaire.title}
        description="Answer each page, then save. Answers you gave on other forms are filled in for you to confirm."
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
                  <span className="block font-semibold text-ink">Refill from other forms</span>
                  <span className="block text-xs text-muted">Copies answers saved on other forms</span>
                </button>
              </div>
            </details>
            <button
              type="button"
              onClick={generatePdf}
              disabled={!caseId || isPending || !canGeneratePdf}
              className={buttonClass("secondary", "md")}
            >
              {canGeneratePdf ? "Preview draft PDF" : "PDF template pending"}
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


      {!caseId ? <CaseBar caseId="" onSelect={selectCase} disabled={isPending} /> : null}

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

              <div className="divide-y divide-line border-y border-line">
                {selectedPageItems.map((item) =>
                  item.type === "group" ? renderAddressGroup(item.group, item.questions) : renderQuestionCard(item.question),
                )}
              </div>

              <PageFooterActions
                onPrevious={pageIndex > 0 ? () => goToPage(questionnaire.pages[pageIndex - 1].id) : undefined}
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

      {isFormComplete && !hasNextPage ? (
        <FormCompleteNotice
          formCode={questionnaire.form_code}
          nextHref={nextStepHref}
          nextLabel={nextFormOption ? `Continue to ${nextFormOption.label}` : "Continue to checklist"}
        />
      ) : null}

      <SourcesDisclosure
        version={questionnaire.version}
        verifiedOn={questionnaire.verified_on}
        officialUrl={questionnaire.official_url}
        sources={questionnaire.sources}
      />
    </AppShell>
  );
}

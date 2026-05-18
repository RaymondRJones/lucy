"use client";

import Link from "next/link";
import { FormEvent, useDeferredValue, useEffect, useMemo, useState, useTransition, type ReactNode } from "react";

import { CaseSelector } from "@/components/case-selector";
import {
  confirmUpload,
  createCase,
  deleteUpload,
  generateChecklist,
  getCase,
  getChecklist,
  getCountryGuidance,
  getExplanations,
  getIntake,
  getQa,
  getUscisRequirements,
  listCases,
  listUploads,
  requestUpload,
  runQa,
  saveIntake,
  submitIntake,
  updateChecklistItem,
  uploadBinary,
} from "@/lib/api";
import { clearSavedCaseId, getSavedCaseId, rememberCaseId } from "@/lib/case-storage";
import {
  CHECKLIST_STATUS_OPTIONS,
  DEFAULT_INTAKE_VALUES,
  type CaseSummary,
  type ChecklistDocumentStatus,
  type ChecklistItem,
  type ChecklistWorkflowStatus,
  type CountryGuidance,
  type ExplanationContent,
  type IntakeFormValues,
  type QaResults,
  type UploadRecord,
  type UscisRequirementsPayload,
} from "@/lib/types";

type WorkspaceTab = "overview" | "intake" | "packet" | "review" | "references";

type UploadFormState = {
  checklistCode: string;
  language: string;
  hasTranslation: boolean;
  documentType: string;
};

type PriorityNote = {
  title: string;
  detail: string;
  tab: WorkspaceTab;
};

const DEFAULT_UPLOAD_FORM: UploadFormState = {
  checklistCode: "",
  language: "english",
  hasTranslation: false,
  documentType: "supporting_document",
};

type ChecklistViewMode = "board" | "list";
type ChecklistStatusFilter = "all" | ChecklistWorkflowStatus;
type ChecklistDocumentFilter = "all" | ChecklistDocumentStatus;
type RequirementForm = UscisRequirementsPayload["forms"][number];
type ChoiceOption<T extends string> = {
  value: T;
  label: string;
};
type ChecklistCardData = ChecklistItem & {
  uploadsForItem: UploadRecord[];
  relatedForms: RequirementForm[];
  primaryRequirement?: RequirementForm;
  formLabels: string[];
  detectedEditions: string[];
  editionMatches: boolean;
  documentStatus: ChecklistDocumentStatus;
  displayStatus: ChecklistWorkflowStatus;
  isSatisfied: boolean;
};

const CHECKLIST_BOARD_ORDER: ChecklistWorkflowStatus[] = [
  "not_started",
  "pending",
  "in_progress",
  "uploaded",
  "almost_done",
  "approved",
  "complete",
];
const CHECKLIST_STATUS_FILTER_OPTIONS: ChoiceOption<ChecklistStatusFilter>[] = [
  { value: "all", label: "All statuses" },
  ...CHECKLIST_STATUS_OPTIONS,
];

const REVIEW_ONLY_CODES = new Set(["review_current_fees", "review_form_editions"]);
const WORKSPACE_TABS: Array<{ id: WorkspaceTab; label: string; detail: string }> = [
  { id: "overview", label: "Overview", detail: "What matters most right now" },
  { id: "intake", label: "Intake", detail: "Facts that drive the checklist" },
  { id: "packet", label: "Packet", detail: "Milestones and checklist detail" },
  { id: "review", label: "Uploads + QA", detail: "Documents and issue review" },
  { id: "references", label: "References", detail: "USCIS and country guidance" },
];
function classNames(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

function formatCategory(category: string) {
  return category.replaceAll("_", " ");
}

function formatStatus(status: string) {
  return status.replaceAll("_", " ");
}

function formatDateLabel(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function getStatusTone(status: string) {
  if (status === "required" || status === "blocking") {
    return "bg-clay/15 text-clay ring-clay/20";
  }
  if (status === "recommended" || status === "important" || status === "pending" || status === "requested") {
    return "bg-sand/30 text-ink ring-sand/40";
  }
  if (status === "in_progress" || status === "uploaded") {
    return "bg-clay/12 text-clay ring-clay/20";
  }
  if (status === "almost_done") {
    return "bg-mist/90 text-ink ring-pine/15";
  }
  if (status === "approved" || status === "complete" || status === "confirmed" || status === "reviewed") {
    return "bg-pine/15 text-pine ring-pine/20";
  }
  if (status === "not_applicable") {
    return "bg-ink/6 text-ink/55 ring-ink/10";
  }
  return "bg-white/70 text-ink/70 ring-ink/10";
}

function formatRequirementType(value: string) {
  return value.replaceAll("_", " ");
}

function getSatisfiedChecklistCodes(upload: UploadRecord) {
  const extraCodes = Array.isArray(upload.extracted_fields.satisfies_checklist_codes)
    ? upload.extracted_fields.satisfies_checklist_codes
        .filter((value): value is string => typeof value === "string" && value.length > 0)
    : [];
  const combined = new Set<string>([
    ...(upload.checklist_item_code ? [upload.checklist_item_code] : []),
    ...extraCodes,
  ]);
  return Array.from(combined);
}

function getDocumentStatus(uploads: UploadRecord[]): ChecklistDocumentStatus {
  if (uploads.some((upload) => upload.upload_status === "confirmed")) {
    return "confirmed";
  }
  if (uploads.some((upload) => upload.upload_status === "uploaded")) {
    return "uploaded";
  }
  if (uploads.some((upload) => upload.upload_status === "requested")) {
    return "requested";
  }
  return "missing";
}

function getDisplayChecklistStatus(
  status: ChecklistWorkflowStatus,
  documentStatus: ChecklistDocumentStatus,
): ChecklistWorkflowStatus {
  if (status === "not_started" && documentStatus === "confirmed") {
    return "uploaded";
  }
  return status;
}

function isChecklistItemSatisfied(
  item: ChecklistItem,
  documentStatus: ChecklistDocumentStatus,
  displayStatus: ChecklistWorkflowStatus,
) {
  if (["uploaded", "almost_done", "approved", "complete"].includes(displayStatus)) {
    return true;
  }
  if (REVIEW_ONLY_CODES.has(item.code)) {
    return item.completion_status === "complete";
  }
  return documentStatus === "confirmed";
}

function toBoolean(value: unknown, fallback: boolean) {
  if (typeof value === "boolean") {
    return value;
  }
  return fallback;
}

function toNumber(value: unknown, fallback: number) {
  if (typeof value === "number") {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  return fallback;
}

function hydrateIntake(merged: Record<string, unknown>): IntakeFormValues {
  return {
    petitioner_first_name: String(merged.petitioner_first_name ?? DEFAULT_INTAKE_VALUES.petitioner_first_name),
    petitioner_middle_name: String(merged.petitioner_middle_name ?? DEFAULT_INTAKE_VALUES.petitioner_middle_name),
    petitioner_last_name: String(merged.petitioner_last_name ?? DEFAULT_INTAKE_VALUES.petitioner_last_name),
    petitioner_date_of_birth: String(
      merged.petitioner_date_of_birth ?? DEFAULT_INTAKE_VALUES.petitioner_date_of_birth,
    ),
    petitioner_phone: String(merged.petitioner_phone ?? DEFAULT_INTAKE_VALUES.petitioner_phone),
    petitioner_email: String(merged.petitioner_email ?? DEFAULT_INTAKE_VALUES.petitioner_email),
    petitioner_current_address: String(
      merged.petitioner_current_address ?? DEFAULT_INTAKE_VALUES.petitioner_current_address,
    ),
    beneficiary_first_name: String(merged.beneficiary_first_name ?? DEFAULT_INTAKE_VALUES.beneficiary_first_name),
    beneficiary_middle_name: String(
      merged.beneficiary_middle_name ?? DEFAULT_INTAKE_VALUES.beneficiary_middle_name,
    ),
    beneficiary_last_name: String(merged.beneficiary_last_name ?? DEFAULT_INTAKE_VALUES.beneficiary_last_name),
    beneficiary_date_of_birth: String(
      merged.beneficiary_date_of_birth ?? DEFAULT_INTAKE_VALUES.beneficiary_date_of_birth,
    ),
    beneficiary_email: String(merged.beneficiary_email ?? DEFAULT_INTAKE_VALUES.beneficiary_email),
    beneficiary_phone: String(merged.beneficiary_phone ?? DEFAULT_INTAKE_VALUES.beneficiary_phone),
    beneficiary_a_number: String(merged.beneficiary_a_number ?? DEFAULT_INTAKE_VALUES.beneficiary_a_number),
    beneficiary_i94_number: String(merged.beneficiary_i94_number ?? DEFAULT_INTAKE_VALUES.beneficiary_i94_number),
    beneficiary_passport_number: String(
      merged.beneficiary_passport_number ?? DEFAULT_INTAKE_VALUES.beneficiary_passport_number,
    ),
    beneficiary_passport_country: String(
      merged.beneficiary_passport_country ?? DEFAULT_INTAKE_VALUES.beneficiary_passport_country,
    ),
    beneficiary_passport_expiration: String(
      merged.beneficiary_passport_expiration ?? DEFAULT_INTAKE_VALUES.beneficiary_passport_expiration,
    ),
    marriage_date: String(merged.marriage_date ?? DEFAULT_INTAKE_VALUES.marriage_date),
    beneficiary_country_of_birth: String(
      merged.beneficiary_country_of_birth ?? DEFAULT_INTAKE_VALUES.beneficiary_country_of_birth,
    ),
    beneficiary_country_of_citizenship: String(
      merged.beneficiary_country_of_citizenship ?? DEFAULT_INTAKE_VALUES.beneficiary_country_of_citizenship,
    ),
    beneficiary_location:
      merged.beneficiary_location === "abroad" ? "abroad" : DEFAULT_INTAKE_VALUES.beneficiary_location,
    beneficiary_entered_us_legally: toBoolean(
      merged.beneficiary_entered_us_legally,
      DEFAULT_INTAKE_VALUES.beneficiary_entered_us_legally,
    ),
    beneficiary_current_immigration_status: String(
      merged.beneficiary_current_immigration_status ??
        DEFAULT_INTAKE_VALUES.beneficiary_current_immigration_status,
    ),
    beneficiary_current_address: String(
      merged.beneficiary_current_address ?? DEFAULT_INTAKE_VALUES.beneficiary_current_address,
    ),
    beneficiary_current_address_since: String(
      merged.beneficiary_current_address_since ?? DEFAULT_INTAKE_VALUES.beneficiary_current_address_since,
    ),
    beneficiary_prior_address_1: String(
      merged.beneficiary_prior_address_1 ?? DEFAULT_INTAKE_VALUES.beneficiary_prior_address_1,
    ),
    beneficiary_prior_address_1_from: String(
      merged.beneficiary_prior_address_1_from ?? DEFAULT_INTAKE_VALUES.beneficiary_prior_address_1_from,
    ),
    beneficiary_prior_address_1_to: String(
      merged.beneficiary_prior_address_1_to ?? DEFAULT_INTAKE_VALUES.beneficiary_prior_address_1_to,
    ),
    beneficiary_prior_address_2: String(
      merged.beneficiary_prior_address_2 ?? DEFAULT_INTAKE_VALUES.beneficiary_prior_address_2,
    ),
    beneficiary_prior_address_2_from: String(
      merged.beneficiary_prior_address_2_from ?? DEFAULT_INTAKE_VALUES.beneficiary_prior_address_2_from,
    ),
    beneficiary_prior_address_2_to: String(
      merged.beneficiary_prior_address_2_to ?? DEFAULT_INTAKE_VALUES.beneficiary_prior_address_2_to,
    ),
    beneficiary_employment_history: String(
      merged.beneficiary_employment_history ?? DEFAULT_INTAKE_VALUES.beneficiary_employment_history,
    ),
    first_marriage_for_both: toBoolean(
      merged.first_marriage_for_both,
      DEFAULT_INTAKE_VALUES.first_marriage_for_both,
    ),
    wants_i765: toBoolean(merged.wants_i765, DEFAULT_INTAKE_VALUES.wants_i765),
    wants_i131: toBoolean(merged.wants_i131, DEFAULT_INTAKE_VALUES.wants_i131),
    needs_translation: toBoolean(merged.needs_translation, DEFAULT_INTAKE_VALUES.needs_translation),
    household_size: toNumber(merged.household_size, DEFAULT_INTAKE_VALUES.household_size),
    annual_income: toNumber(merged.annual_income, DEFAULT_INTAKE_VALUES.annual_income),
    employment_status: String(merged.employment_status ?? DEFAULT_INTAKE_VALUES.employment_status),
    has_children: toBoolean(merged.has_children, DEFAULT_INTAKE_VALUES.has_children),
    has_joint_lease: toBoolean(merged.has_joint_lease, DEFAULT_INTAKE_VALUES.has_joint_lease),
    has_joint_bank_account: toBoolean(
      merged.has_joint_bank_account,
      DEFAULT_INTAKE_VALUES.has_joint_bank_account,
    ),
    has_relationship_photos: toBoolean(
      merged.has_relationship_photos,
      DEFAULT_INTAKE_VALUES.has_relationship_photos,
    ),
    has_affidavits: toBoolean(merged.has_affidavits, DEFAULT_INTAKE_VALUES.has_affidavits),
    reviewed_current_fees: toBoolean(
      merged.reviewed_current_fees,
      DEFAULT_INTAKE_VALUES.reviewed_current_fees,
    ),
    reviewed_current_form_editions: toBoolean(
      merged.reviewed_current_form_editions,
      DEFAULT_INTAKE_VALUES.reviewed_current_form_editions,
    ),
    prior_immigration_denials: toBoolean(
      merged.prior_immigration_denials,
      DEFAULT_INTAKE_VALUES.prior_immigration_denials,
    ),
    criminal_history: toBoolean(merged.criminal_history, DEFAULT_INTAKE_VALUES.criminal_history),
    removal_history: toBoolean(merged.removal_history, DEFAULT_INTAKE_VALUES.removal_history),
    identity_inconsistencies: toBoolean(
      merged.identity_inconsistencies,
      DEFAULT_INTAKE_VALUES.identity_inconsistencies,
    ),
  };
}

function getDisplayName(firstName?: string | null, lastName?: string | null) {
  const parts = [firstName, lastName].filter((value): value is string => Boolean(value?.trim()));
  return parts.length ? parts.join(" ") : "Not provided";
}

function BooleanField({
  label,
  checked,
  onChange,
  description,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  description?: string;
}) {
  return (
    <label className="rounded-[1.4rem] border border-ink/10 bg-white/72 p-4 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-ink">{label}</p>
          {description ? <p className="mt-1 text-sm leading-6 text-ink/65">{description}</p> : null}
        </div>
        <input
          type="checkbox"
          checked={checked}
          onChange={(event) => onChange(event.target.checked)}
          className="mt-1 h-5 w-5 rounded border-ink/30 text-pine focus:ring-pine"
        />
      </div>
    </label>
  );
}

function Card({
  title,
  eyebrow,
  children,
  action,
  className,
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={classNames(
        "rounded-[2rem] border border-white/60 bg-white/78 p-6 shadow-panel backdrop-blur",
        className,
      )}
    >
      <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          {eyebrow ? <p className="text-xs uppercase tracking-[0.24em] text-pine/80">{eyebrow}</p> : null}
          <h2 className="font-display text-2xl text-ink">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function FieldGroup({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-[1.75rem] border border-ink/10 bg-paper/55 p-5">
      <div className="mb-4">
        <h3 className="font-semibold text-ink">{title}</h3>
        {description ? <p className="mt-1 text-sm leading-6 text-ink/68">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}

function MetricTile({
  label,
  value,
  detail,
}: {
  label: string;
  value: ReactNode;
  detail?: string;
}) {
  return (
    <div className="rounded-[1.4rem] border border-ink/10 bg-white/72 px-4 py-4">
      <p className="text-xs uppercase tracking-[0.18em] text-ink/45">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-ink">{value}</p>
      {detail ? <p className="mt-1 text-sm text-ink/62">{detail}</p> : null}
    </div>
  );
}

function SnapshotRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-ink/8 py-3 last:border-b-0 last:pb-0">
      <span className="text-sm text-ink/60">{label}</span>
      <span className="text-right text-sm font-medium text-ink">{value}</span>
    </div>
  );
}

function TabButton({
  label,
  detail,
  isActive,
  onClick,
}: {
  label: string;
  detail: string;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={classNames(
        "min-w-[10.5rem] rounded-full px-4 py-3 text-left transition",
        isActive
          ? "bg-ink text-white shadow-sm"
          : "bg-transparent text-ink/72 hover:bg-white/75 hover:text-ink",
      )}
      aria-current={isActive ? "page" : undefined}
    >
      <p className="text-sm font-semibold">{label}</p>
      <p className={classNames("mt-1 text-xs", isActive ? "text-white/72" : "text-ink/55")}>{detail}</p>
    </button>
  );
}

function ChoiceChips<T extends string>({
  options,
  value,
  onChange,
}: {
  options: ChoiceOption<T>[];
  value: T;
  onChange: (nextValue: T) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((option) => {
        const isActive = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={classNames(
              "rounded-full border px-2.5 py-1.5 text-xs transition",
              isActive
                ? "border-ink bg-ink text-white"
                : "border-ink/10 bg-white text-ink/68 hover:border-ink/20 hover:text-ink",
            )}
            aria-pressed={isActive}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function DisclosurePanel({
  title,
  subtitle,
  children,
  defaultOpen = false,
  meta,
  aside,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  defaultOpen?: boolean;
  meta?: ReactNode;
  aside?: ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  useEffect(() => {
    if (defaultOpen) {
      setIsOpen(true);
    }
  }, [defaultOpen]);

  return (
    <div className="overflow-hidden rounded-[1.75rem] border border-ink/10 bg-white/72">
      <button
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        className="flex w-full flex-col gap-4 px-5 py-5 text-left md:flex-row md:items-start md:justify-between"
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold text-ink">{title}</h3>
            {meta}
          </div>
          {subtitle ? <p className="mt-2 text-sm leading-6 text-ink/70">{subtitle}</p> : null}
        </div>
        <div className="flex items-center gap-3 self-start md:self-center">
          {aside}
          <span className="rounded-full border border-ink/10 bg-paper/75 px-3 py-1 text-xs uppercase tracking-[0.16em] text-ink/62">
            {isOpen ? "Hide" : "Show"}
          </span>
        </div>
      </button>
      {isOpen ? <div className="border-t border-ink/10 px-5 pb-5 pt-4">{children}</div> : null}
    </div>
  );
}

export function CaseWorkspace() {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("overview");
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [caseSummary, setCaseSummary] = useState<CaseSummary | null>(null);
  const [intakeValues, setIntakeValues] = useState<IntakeFormValues>(DEFAULT_INTAKE_VALUES);
  const [missingFields, setMissingFields] = useState<string[]>([]);
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [uploads, setUploads] = useState<UploadRecord[]>([]);
  const [qa, setQa] = useState<QaResults | null>(null);
  const [guidance, setGuidance] = useState<CountryGuidance | null>(null);
  const [explanations, setExplanations] = useState<ExplanationContent | null>(null);
  const [uscisRequirements, setUscisRequirements] = useState<UscisRequirementsPayload | null>(null);
  const [message, setMessage] = useState<string>("Create a case to start organizing the packet.");
  const [createForm, setCreateForm] = useState({
    case_name: "Lucy marriage packet",
    petitioner_email: "",
    beneficiary_email: "",
    country_of_focus: "Colombia",
  });
  const [isCreateCaseOpen, setIsCreateCaseOpen] = useState(false);
  const [uploadForm, setUploadForm] = useState<UploadFormState>(DEFAULT_UPLOAD_FORM);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [checklistView, setChecklistView] = useState<ChecklistViewMode>("board");
  const [statusFilter, setStatusFilter] = useState<ChecklistStatusFilter>("all");
  const [documentFilter, setDocumentFilter] = useState<ChecklistDocumentFilter>("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [uploadInputKey, setUploadInputKey] = useState(0);
  const [draggedChecklistItemId, setDraggedChecklistItemId] = useState<string | null>(null);
  const [dragTargetStatus, setDragTargetStatus] = useState<ChecklistWorkflowStatus | null>(null);
  const [isPending, startTransition] = useTransition();
  const deferredSearchQuery = useDeferredValue(searchQuery);

  function rememberCaseInUrl(caseId: string) {
    rememberCaseId(caseId);
    const url = new URL(window.location.href);
    url.searchParams.set("caseId", caseId);
    window.history.replaceState({}, "", url);
  }

  useEffect(() => {
    let cancelled = false;

    async function bootstrap(caseId: string, successMessage: string) {
      try {
        const [
          loadedCase,
          intakeState,
          loadedChecklist,
          loadedUploads,
          loadedQa,
          loadedExplanations,
          loadedRequirements,
        ] = await Promise.all([
          getCase(caseId),
          getIntake(caseId).catch(() => null),
          getChecklist(caseId).catch(() => null),
          listUploads(caseId).catch(() => []),
          getQa(caseId).catch(() => null),
          getExplanations(),
          getUscisRequirements(),
        ]);

        if (cancelled) {
          return;
        }

        setCaseSummary(loadedCase);
        setUploads(loadedUploads);
        setQa(loadedQa);
        setExplanations(loadedExplanations);
        setUscisRequirements(loadedRequirements);

        if (intakeState) {
          setIntakeValues(hydrateIntake(intakeState.merged));
          setMissingFields(intakeState.missing_fields);
        }

        if (loadedChecklist) {
          setChecklist(loadedChecklist.items);
        }

        const countryCode =
          (intakeState?.merged.beneficiary_country_of_birth as string | undefined) ||
          loadedCase.country_of_focus ||
          "CO";
        const loadedGuidance = await getCountryGuidance(countryCode).catch(() => null);

        if (!cancelled) {
          setGuidance(loadedGuidance);
          setMessage(successMessage);
          rememberCaseInUrl(caseId);
        }
      } catch (error) {
        if (!cancelled) {
          clearSavedCaseId();
          setMessage(error instanceof Error ? error.message : "Unable to restore the saved case.");
        }
      } finally {
        if (!cancelled) {
          setIsBootstrapping(false);
        }
      }
    }

    async function initialize() {
      try {
        const searchParams = new URLSearchParams(window.location.search);
        const existingCaseId =
          searchParams.get("caseId") || getSavedCaseId();

        if (existingCaseId) {
          await bootstrap(existingCaseId, "Welcome back. Your packet workspace is ready.");
          return;
        }

        const [payload, requirements, cases] = await Promise.all([
          getExplanations(),
          getUscisRequirements(),
          listCases().catch(() => []),
        ]);

        if (cancelled) {
          return;
        }

        setExplanations(payload);
        setUscisRequirements(requirements);

        if (cases.length > 0) {
          await bootstrap(cases[0].id, "Loaded the most recent case already stored in the workspace.");
          return;
        }

        setMessage("Create a case to start organizing the packet.");
      } catch (error) {
        if (!cancelled) {
          setMessage(error instanceof Error ? error.message : "Unable to load workspace content.");
        }
      } finally {
        if (!cancelled) {
          setIsBootstrapping(false);
        }
      }
    }

    void initialize();

    return () => {
      cancelled = true;
    };
  }, []);

  const uploadsBySatisfiedChecklist = useMemo(() => {
    return uploads.reduce<Record<string, UploadRecord[]>>((accumulator, upload) => {
      for (const checklistCode of getSatisfiedChecklistCodes(upload)) {
        accumulator[checklistCode] = accumulator[checklistCode]
          ? [...accumulator[checklistCode], upload]
          : [upload];
      }
      return accumulator;
    }, {});
  }, [uploads]);

  const requirementFormsByChecklistCode = useMemo(() => {
    const accumulator: Record<string, UscisRequirementsPayload["forms"][number][]> = {};
    for (const requirement of uscisRequirements?.forms ?? []) {
      for (const code of requirement.related_checklist_codes) {
        accumulator[code] = accumulator[code]
          ? [...accumulator[code], requirement]
          : [requirement];
      }
    }
    return accumulator;
  }, [uscisRequirements]);

  const checklistCards = useMemo<ChecklistCardData[]>(() => {
    return checklist.map((item) => {
      const uploadsForItem = uploadsBySatisfiedChecklist[item.code] ?? [];
      const relatedForms = requirementFormsByChecklistCode[item.code] ?? [];
      const primaryRequirement = relatedForms.find(
        (requirement) => requirement.related_checklist_codes[0] === item.code,
      );
      const formLabels =
        item.item_metadata.form_codes && Array.isArray(item.item_metadata.form_codes)
          ? item.item_metadata.form_codes
              .map(
                (code) =>
                  uscisRequirements?.forms.find((requirement) => requirement.code === code)?.label || code,
              )
              .filter((value): value is string => typeof value === "string" && value.length > 0)
          : [];
      const detectedEditions = uploadsForItem
        .map((upload) => String(upload.extracted_fields.form_edition ?? ""))
        .filter(Boolean);
      const editionMatches = uploadsForItem.some(
        (upload) => upload.extracted_fields.edition_matches_current_uscis_requirement === true,
      );
      const documentStatus = getDocumentStatus(uploadsForItem);
      const displayStatus = getDisplayChecklistStatus(item.completion_status, documentStatus);
      return {
        ...item,
        uploadsForItem,
        relatedForms,
        primaryRequirement,
        formLabels,
        detectedEditions,
        editionMatches,
        documentStatus,
        displayStatus,
        isSatisfied: isChecklistItemSatisfied(item, documentStatus, displayStatus),
      };
    });
  }, [checklist, requirementFormsByChecklistCode, uploadsBySatisfiedChecklist, uscisRequirements]);

  const checklistCardsByCode = useMemo(() => {
    return Object.fromEntries(checklistCards.map((item) => [item.code, item] as const));
  }, [checklistCards]);

  const checklistCardsById = useMemo(() => {
    return Object.fromEntries(checklistCards.map((item) => [item.id, item] as const));
  }, [checklistCards]);

  const formPacketPlans = useMemo(() => {
    return (uscisRequirements?.forms ?? []).flatMap((requirement) => {
      const rootChecklistCode = requirement.initial_evidence[0]?.checklist_code;
      const rootItem = rootChecklistCode ? checklistCardsByCode[rootChecklistCode] : undefined;
      if (rootItem?.applicability === "not_applicable") {
        return [];
      }

      const milestones = requirement.initial_evidence.flatMap((entry) => {
        const item = checklistCardsByCode[entry.checklist_code];
        if (item?.applicability === "not_applicable") {
          return [];
        }
        const linkedUploads = item?.uploadsForItem ?? [];
        const status = item?.displayStatus ?? "not_started";
        const necessity = item?.applicability === "required" ? "required" : entry.necessity;
        return [
          {
            ...entry,
            item,
            status,
            necessity,
            linkedUploads,
            documentStatus: item?.documentStatus ?? getDocumentStatus(linkedUploads),
            isSatisfied: item?.isSatisfied ?? linkedUploads.some((upload) => upload.upload_status === "confirmed"),
          },
        ];
      });

      const requiredMilestones = milestones.filter((entry) => entry.necessity === "required");
      const completedRequired = requiredMilestones.filter((entry) => entry.isSatisfied).length;
      const nextMissing = requiredMilestones
        .filter((entry) => !entry.isSatisfied)
        .map((entry) => entry.label)
        .slice(0, 3);

      return [
        {
          ...requirement,
          rootChecklistCode,
          milestones,
          completedRequired,
          requiredCount: requiredMilestones.length,
          nextMissing,
        },
      ];
    });
  }, [checklistCardsByCode, uscisRequirements]);
  const visibleChecklistCards = useMemo(
    () => checklistCards.filter((item) => item.applicability !== "not_applicable"),
    [checklistCards],
  );

  const normalizedSearch = deferredSearchQuery.trim().toLowerCase();

  const filteredChecklistCards = useMemo(() => {
    return visibleChecklistCards.filter((item) => {
      const matchesStatus = statusFilter === "all" || item.displayStatus === statusFilter;
      const matchesDocument = documentFilter === "all" || item.documentStatus === documentFilter;
      const matchesCategory = categoryFilter === "all" || item.category === categoryFilter;
      const haystack = [item.label, item.description, item.category, item.owner_role, ...item.formLabels]
        .join(" ")
        .toLowerCase();
      const matchesSearch = !normalizedSearch || haystack.includes(normalizedSearch);
      return matchesStatus && matchesDocument && matchesCategory && matchesSearch;
    });
  }, [categoryFilter, documentFilter, normalizedSearch, statusFilter, visibleChecklistCards]);

  const filteredChecklistGroups = useMemo(() => {
    return filteredChecklistCards.reduce<Record<string, ChecklistCardData[]>>((accumulator, item) => {
      accumulator[item.category] = accumulator[item.category]
        ? [...accumulator[item.category], item]
        : [item];
      return accumulator;
    }, {});
  }, [filteredChecklistCards]);

  const checklistBoardColumns = useMemo(() => {
    return CHECKLIST_BOARD_ORDER.reduce<Record<ChecklistWorkflowStatus, ChecklistCardData[]>>(
      (accumulator, status) => {
        accumulator[status] = filteredChecklistCards.filter((item) => item.displayStatus === status);
        return accumulator;
      },
      {
        not_started: [],
        pending: [],
        in_progress: [],
        uploaded: [],
        almost_done: [],
        approved: [],
        complete: [],
        not_applicable: [],
      },
    );
  }, [filteredChecklistCards]);

  const uploadableItems = useMemo(
    () => checklistCards.filter((item) => item.applicability !== "not_applicable" && !REVIEW_ONLY_CODES.has(item.code)),
    [checklistCards],
  );

  const actionableChecklist = visibleChecklistCards;

  const incompleteRequiredItems = useMemo(
    () =>
      actionableChecklist.filter((item) => item.applicability === "required" && !item.isSatisfied),
    [actionableChecklist],
  );

  const unresolvedIssues = useMemo(
    () => (qa?.issues ?? []).filter((issue) => !issue.is_resolved),
    [qa],
  );

  const recentUploads = useMemo(() => {
    return [...uploads]
      .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))
      .slice(0, 4);
  }, [uploads]);

  const progressPercent = useMemo(() => {
    const actionable = visibleChecklistCards;
    if (!actionable.length) {
      return 0;
    }
    const complete = actionable.filter((item) => item.isSatisfied).length;
    return Math.round((complete / actionable.length) * 100);
  }, [visibleChecklistCards]);

  const hasRiskFlags =
    intakeValues.prior_immigration_denials ||
    intakeValues.criminal_history ||
    intakeValues.removal_history ||
    intakeValues.identity_inconsistencies;

  const petitionerName = getDisplayName(
    caseSummary?.petitioner?.first_name ?? intakeValues.petitioner_first_name,
    caseSummary?.petitioner?.last_name ?? intakeValues.petitioner_last_name,
  );
  const beneficiaryName = getDisplayName(
    caseSummary?.beneficiary?.first_name ?? intakeValues.beneficiary_first_name,
    caseSummary?.beneficiary?.last_name ?? intakeValues.beneficiary_last_name,
  );
  const countryFocusLabel =
    guidance?.country_name ||
    intakeValues.beneficiary_country_of_birth ||
    caseSummary?.country_of_focus ||
    "Not set";
  const filingTrackLabel =
    intakeValues.beneficiary_location === "abroad"
      ? "Beneficiary is outside the U.S.; standard concurrent filing may not fit."
      : intakeValues.beneficiary_entered_us_legally
        ? "Facts currently align with a standard adjustment-of-status style workflow."
        : "Lawful-entry review is needed before relying on the standard filing path.";

  const priorityNotes = useMemo<PriorityNote[]>(() => {
    const notes: PriorityNote[] = [];

    if (missingFields.length) {
      notes.push({
        title: `${missingFields.length} intake fields still need attention`,
        detail: `Complete ${missingFields.slice(0, 3).join(", ")} so the rules engine has clean facts.`,
        tab: "intake",
      });
    }

    if (!checklist.length) {
      notes.push({
        title: "The personalized checklist has not been generated yet",
        detail: "Save the intake, then create the backend-driven filing plan.",
        tab: "intake",
      });
    }

    if (incompleteRequiredItems.length) {
      notes.push({
        title: `${incompleteRequiredItems.length} required checklist items remain open`,
        detail: incompleteRequiredItems
          .slice(0, 2)
          .map((item) => item.label)
          .join(", "),
        tab: "packet",
      });
    }

    if (!uploads.length && checklist.length) {
      notes.push({
        title: "No supporting documents have been linked yet",
        detail: "Start assigning files to checklist items so packet progress becomes concrete.",
        tab: "review",
      });
    }

    if (unresolvedIssues.length) {
      notes.push({
        title: `${unresolvedIssues.length} QA issues need review`,
        detail: unresolvedIssues
          .slice(0, 2)
          .map((issue) => issue.title)
          .join(", "),
        tab: "review",
      });
    }

    if (!notes.length) {
      notes.push({
        title: "The packet is in a calmer state",
        detail: "Use the reference tab for a final source check before printing and assembling.",
        tab: "references",
      });
    }

    return notes.slice(0, 4);
  }, [checklist.length, incompleteRequiredItems, missingFields, unresolvedIssues, uploads.length]);

  async function refreshCase(caseId: string) {
    const [loadedCase, loadedChecklist, loadedUploads, loadedQa] = await Promise.all([
      getCase(caseId),
      getChecklist(caseId).catch(() => null),
      listUploads(caseId),
      getQa(caseId).catch(() => null),
    ]);
    setCaseSummary(loadedCase);
    setUploads(loadedUploads);
    setQa(loadedQa);
    if (loadedChecklist) {
      setChecklist(loadedChecklist.items);
    }
  }

  function handleCaseSelect(nextCase: CaseSummary) {
    startTransition(() => {
      void (async () => {
        try {
          const intakeState = await getIntake(nextCase.id).catch(() => null);
          await refreshCase(nextCase.id);
          rememberCaseInUrl(nextCase.id);
          if (intakeState) {
            setIntakeValues(hydrateIntake(intakeState.merged));
            setMissingFields(intakeState.missing_fields);
          }
          const countryCode =
            (intakeState?.merged.beneficiary_country_of_birth as string | undefined) ||
            nextCase.country_of_focus ||
            "CO";
          setGuidance(await getCountryGuidance(countryCode).catch(() => null));
          setMessage(`Loaded ${nextCase.case_name}.`);
        } catch (error) {
          setMessage(error instanceof Error ? error.message : "Could not switch cases.");
        }
      })();
    });
  }

  async function handleCreateCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    startTransition(() => {
      void (async () => {
        try {
          const payload = {
            case_name: createForm.case_name.trim(),
            petitioner_email: createForm.petitioner_email.trim() || undefined,
            beneficiary_email: createForm.beneficiary_email.trim() || undefined,
            country_of_focus: createForm.country_of_focus.trim() || undefined,
          };
          if (!payload.case_name) {
            setMessage("Add a case name before creating the workspace.");
            return;
          }

          const created = await createCase(payload);
          rememberCaseInUrl(created.id);
          setCaseSummary(created);
          setChecklist([]);
          setUploads([]);
          setQa(null);
          setMissingFields([]);
          setIsCreateCaseOpen(false);
          setActiveTab("intake");
          setMessage("Case created. Fill in the intake so the packet plan can stay specific.");

          if (payload.country_of_focus) {
            const loadedGuidance = await getCountryGuidance(payload.country_of_focus).catch(() => null);
            setGuidance(loadedGuidance);
          }
        } catch (error) {
          setMessage(error instanceof Error ? error.message : "Case creation failed.");
        }
      })();
    });
  }

  async function handleSaveIntake(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!caseSummary) {
      return;
    }

    startTransition(() => {
      void (async () => {
        try {
          const payload = {
            ...intakeValues,
            petitioner_email: intakeValues.petitioner_email,
            beneficiary_email: intakeValues.beneficiary_email,
          };
          const intakeState = await saveIntake(caseSummary.id, payload);
          setMissingFields(intakeState.missing_fields);
          setIntakeValues(hydrateIntake(intakeState.merged));
          setMessage("Intake saved. You can keep refining it before generating the checklist.");

          const loadedGuidance = await getCountryGuidance(
            String(intakeState.merged.beneficiary_country_of_birth ?? "CO"),
          ).catch(() => null);
          setGuidance(loadedGuidance);

          await refreshCase(caseSummary.id);
        } catch (error) {
          setMessage(error instanceof Error ? error.message : "Unable to save intake.");
        }
      })();
    });
  }

  async function handleGenerateChecklist() {
    if (!caseSummary) {
      return;
    }

    startTransition(() => {
      void (async () => {
        try {
          await submitIntake(caseSummary.id);
          const generated = await generateChecklist(caseSummary.id);
          setChecklist(generated.items);
          setActiveTab("packet");
          setMessage("Checklist generated. Review the packet milestones and start linking files.");
          await refreshCase(caseSummary.id);
        } catch (error) {
          setActiveTab("intake");
          setMessage(error instanceof Error ? error.message : "Checklist generation failed.");
        }
      })();
    });
  }

  async function handleChecklistStatus(itemId: string, nextStatus: ChecklistWorkflowStatus) {
    if (!caseSummary) {
      return;
    }
    const currentItem = checklist.find((item) => item.id === itemId);
    if (!currentItem || currentItem.completion_status === nextStatus) {
      return;
    }
    const previousChecklist = checklist;
    startTransition(() => {
      void (async () => {
        try {
          setChecklist((current) =>
            current.map((item) =>
              item.id === itemId ? { ...item, completion_status: nextStatus } : item,
            ),
          );
          await updateChecklistItem(itemId, nextStatus);
          const refreshed = await getChecklist(caseSummary.id);
          setChecklist(refreshed.items);
          setMessage("Checklist status updated.");
        } catch (error) {
          setChecklist(previousChecklist);
          setMessage(error instanceof Error ? error.message : "Unable to update checklist status.");
        }
      })();
    });
  }

  function getNeighborStatus(status: ChecklistWorkflowStatus, direction: -1 | 1) {
    const currentIndex = CHECKLIST_BOARD_ORDER.indexOf(status);
    if (currentIndex < 0) {
      return null;
    }
    return CHECKLIST_BOARD_ORDER[currentIndex + direction] ?? null;
  }

  function handleChecklistCardMove(item: ChecklistCardData, direction: -1 | 1) {
    const nextStatus = getNeighborStatus(item.displayStatus, direction);
    if (!nextStatus) {
      return;
    }
    void handleChecklistStatus(item.id, nextStatus);
  }

  function handleChecklistCardDragStart(itemId: string) {
    setDraggedChecklistItemId(itemId);
  }

  function handleChecklistCardDragEnd() {
    setDraggedChecklistItemId(null);
    setDragTargetStatus(null);
  }

  function handleChecklistBoardDrop(status: ChecklistWorkflowStatus) {
    if (!draggedChecklistItemId) {
      return;
    }
    const draggedItem = checklistCardsById[draggedChecklistItemId];
    setDraggedChecklistItemId(null);
    setDragTargetStatus(null);
    if (!draggedItem || draggedItem.displayStatus === status) {
      return;
    }
    void handleChecklistStatus(draggedItem.id, status);
  }

  function stageUploadForItem(itemCode: string, itemLabel: string) {
    setUploadForm((current) => ({ ...current, checklistCode: itemCode }));
    setMessage(`${itemLabel} is selected in the upload form below.`);
  }

  async function handleUpload() {
    if (!caseSummary || !selectedFile || !uploadForm.checklistCode) {
      setMessage("Choose a checklist item and a file before uploading.");
      return;
    }

    startTransition(() => {
      void (async () => {
        try {
          const requested = await requestUpload(caseSummary.id, {
            checklist_item_code: uploadForm.checklistCode,
            original_filename: selectedFile.name,
            mime_type: selectedFile.type,
            document_language: uploadForm.language,
            has_translation: uploadForm.hasTranslation,
          });
          await uploadBinary(requested.upload_url, selectedFile);
          await confirmUpload(requested.upload_id, {
            document_type: uploadForm.documentType,
            document_language: uploadForm.language,
            has_translation: uploadForm.hasTranslation,
            extraction_confidence: 0.35,
          });
          setSelectedFile(null);
          setUploadForm(DEFAULT_UPLOAD_FORM);
          setUploadInputKey((current) => current + 1);
          setActiveTab("review");
          await refreshCase(caseSummary.id);
          setMessage("Upload saved and linked to the checklist item.");
        } catch (error) {
          setMessage(error instanceof Error ? error.message : "Upload failed.");
        }
      })();
    });
  }

  async function handleDeleteUpload(uploadId: string) {
    if (!caseSummary) {
      return;
    }
    startTransition(() => {
      void (async () => {
        try {
          await deleteUpload(uploadId);
          await refreshCase(caseSummary.id);
          setMessage("Upload removed.");
        } catch (error) {
          setMessage(error instanceof Error ? error.message : "Unable to delete upload.");
        }
      })();
    });
  }

  async function handleRunQa() {
    if (!caseSummary) {
      return;
    }
    startTransition(() => {
      void (async () => {
        try {
          const results = await runQa(caseSummary.id);
          setQa(results);
          setActiveTab("review");
          await refreshCase(caseSummary.id);
          setMessage("QA complete. Review the issue list and finish the remaining fixes.");
        } catch (error) {
          setMessage(error instanceof Error ? error.message : "QA run failed.");
        }
      })();
    });
  }

  function renderChecklistCard(item: ChecklistCardData, compact = false) {
    const previousStatus = getNeighborStatus(item.displayStatus, -1);
    const nextStatus = getNeighborStatus(item.displayStatus, 1);

    return (
      <div
        key={item.id}
        draggable={compact}
        onDragStart={(event) => {
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData("text/plain", item.id);
          handleChecklistCardDragStart(item.id);
        }}
        onDragEnd={handleChecklistCardDragEnd}
        className={classNames(
          "rounded-3xl border border-ink/10 bg-white/70 p-4",
          compact ? "cursor-grab shadow-sm active:cursor-grabbing" : "",
          draggedChecklistItemId === item.id ? "opacity-70 ring-2 ring-pine/20" : "",
        )}
      >
        <div
          className={classNames(
            "flex flex-col gap-4",
            compact ? "" : "md:flex-row md:items-start md:justify-between",
          )}
        >
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h4 className="font-semibold text-ink">{item.label}</h4>
              <span
                className={classNames(
                  "rounded-full px-3 py-1 text-xs uppercase tracking-[0.16em] ring-1",
                  getStatusTone(item.applicability),
                )}
              >
                {formatStatus(item.applicability)}
              </span>
              <span className="rounded-full bg-ink/6 px-3 py-1 text-xs uppercase tracking-[0.16em] text-ink/70">
                {item.owner_role}
              </span>
              <span
                className={classNames(
                  "rounded-full px-3 py-1 text-xs uppercase tracking-[0.16em] ring-1",
                  getStatusTone(item.documentStatus),
                )}
              >
                Docs {formatStatus(item.documentStatus)}
              </span>
            </div>
            <p className="mt-2 text-sm leading-6 text-ink/72">{item.description}</p>
            {item.formLabels.length ? (
              <div className="mt-3 flex flex-wrap gap-2 text-xs uppercase tracking-[0.14em] text-ink/60">
                {item.formLabels.map((label) => (
                  <span
                    key={`${item.code}-${label}`}
                    className="rounded-full bg-paper/80 px-3 py-1 ring-1 ring-ink/10"
                  >
                    Supports {label}
                  </span>
                ))}
              </div>
            ) : null}
            {item.uploadsForItem.length ? (
              <p className="mt-3 text-sm text-pine">
                Linked upload{item.uploadsForItem.length > 1 ? "s" : ""}:{" "}
                {item.uploadsForItem
                  .slice(0, compact ? 2 : 3)
                  .map((upload) => upload.original_filename)
                  .join(", ")}
              </p>
            ) : !REVIEW_ONLY_CODES.has(item.code) ? (
              <p className="mt-3 text-sm text-ink/58">No linked upload yet.</p>
            ) : null}
          </div>
          <div
            className={classNames(
              "rounded-3xl border border-ink/10 bg-paper/75 p-4",
              compact ? "min-w-0" : "min-w-52",
            )}
          >
            <p className="text-xs uppercase tracking-[0.18em] text-ink/45">Workflow status</p>
            {compact ? (
              <>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => handleChecklistCardMove(item, -1)}
                    disabled={!previousStatus || isPending}
                    className="rounded-2xl border border-ink/10 bg-white px-3 py-2 text-sm text-ink transition hover:border-ink/20 hover:text-ink disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    Back
                  </button>
                  <button
                    type="button"
                    onClick={() => handleChecklistCardMove(item, 1)}
                    disabled={!nextStatus || isPending}
                    className="rounded-2xl border border-pine/15 bg-pine/10 px-3 py-2 text-sm text-pine transition hover:bg-pine hover:text-white disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    Advance
                  </button>
                </div>
                <p className="mt-3 text-xs text-ink/55">Drag to another lane or use the buttons above.</p>
              </>
            ) : (
              <select
                value={item.completion_status}
                onChange={(event) =>
                  handleChecklistStatus(item.id, event.target.value as ChecklistWorkflowStatus)
                }
                className="mt-3 w-full rounded-2xl border border-ink/10 bg-white px-4 py-3 text-sm text-ink"
              >
                {CHECKLIST_STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            )}
            <p
              className={classNames(
                "mt-3 inline-flex rounded-full px-3 py-1 text-sm capitalize ring-1",
                getStatusTone(item.displayStatus),
              )}
            >
              {formatStatus(item.displayStatus)}
            </p>
            {!REVIEW_ONLY_CODES.has(item.code) ? (
              <button
                type="button"
                onClick={() => stageUploadForItem(item.code, item.label)}
                className="mt-4 w-full rounded-full border border-pine/20 bg-pine/10 px-4 py-2 text-sm text-pine transition hover:bg-pine hover:text-white"
              >
                Link upload
              </button>
            ) : null}
          </div>
        </div>
        {!compact ? (
          <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto] md:items-start">
            <div className="rounded-2xl bg-paper/70 px-4 py-3 text-sm text-ink/75">
              <p className="font-semibold text-ink">Why this is needed</p>
              <p className="mt-1">{item.why_needed}</p>
              <p className="mt-3 font-semibold text-ink">What to save now</p>
              <p className="mt-1">{item.what_to_save_now}</p>
              {item.conditional_reason ? (
                <>
                  <p className="mt-3 font-semibold text-ink">Conditional note</p>
                  <p className="mt-1">{item.conditional_reason}</p>
                </>
              ) : null}
            </div>
            {item.primaryRequirement ? (
              <div className="rounded-2xl border border-pine/10 bg-pine/6 px-4 py-3 text-sm text-ink/72 md:w-80">
                <p>
                  USCIS accepted edition:{" "}
                  <span className="font-semibold text-ink">
                    {item.primaryRequirement.accepted_edition || "n/a"}
                  </span>
                  {" "}• verified {formatDateLabel(item.primaryRequirement.verified_on)}
                </p>
                {item.detectedEditions.length ? (
                  <p className="mt-1">
                    Imported edition{item.detectedEditions.length > 1 ? "s" : ""}:{" "}
                    <span className="font-semibold text-ink">{item.detectedEditions.join(", ")}</span>
                    {item.editionMatches ? " • matches USCIS reference" : ""}
                  </p>
                ) : (
                  <p className="mt-1 text-ink/65">
                    No imported form edition detected yet for this checklist item.
                  </p>
                )}
                <a
                  href={item.primaryRequirement.official_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 inline-block text-pine underline-offset-2 hover:underline"
                >
                  View USCIS source
                </a>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    );
  }

  const nextAction = caseSummary
    ? missingFields.length
      ? {
          title: "Finish the intake details",
          description: `${missingFields.length} required field${missingFields.length === 1 ? "" : "s"} still need a value before the packet plan is trustworthy.`,
          buttonLabel: "Open intake",
          buttonAction: () => setActiveTab("intake" as WorkspaceTab),
        }
      : !checklist.length
        ? {
            title: "Generate the personalized checklist",
            description: "Turn the saved intake into the backend-owned filing plan before working on uploads.",
            buttonLabel: "Generate checklist",
            buttonAction: handleGenerateChecklist,
          }
        : !uploads.length
          ? {
              title: "Start linking evidence to the checklist",
              description: "Once documents are attached to checklist items, the packet becomes much easier to review.",
              buttonLabel: "Open uploads",
              buttonAction: () => setActiveTab("review" as WorkspaceTab),
            }
          : !qa
            ? {
                title: "Run the packet QA pass",
                description: "Let the backend check missing required items, translation gaps, and escalation triggers.",
                buttonLabel: "Run QA",
                buttonAction: handleRunQa,
              }
            : unresolvedIssues.length
              ? {
                  title: "Resolve the open QA issues",
                  description: "The highest-signal review items are already surfaced. Work through them before final assembly.",
                  buttonLabel: "Review issues",
                  buttonAction: () => setActiveTab("review" as WorkspaceTab),
                }
              : incompleteRequiredItems.length
                ? {
                    title: "Finish the remaining required packet items",
                    description: "The packet is mostly shaped, but a few required checklist items still need attention.",
                    buttonLabel: "Open packet view",
                    buttonAction: () => setActiveTab("packet" as WorkspaceTab),
                  }
                : {
                    title: "Do a final source check",
                    description: "The packet looks steady. Use the references tab to confirm the latest form details before printing.",
                    buttonLabel: "Open references",
                    buttonAction: () => setActiveTab("references" as WorkspaceTab),
                  }
    : null;

  const createCaseForm = (
    <form className="grid gap-4 md:grid-cols-2" onSubmit={handleCreateCase}>
      <label className="md:col-span-2">
        <span className="mb-2 block text-sm font-semibold text-ink">Case name</span>
        <input
          value={createForm.case_name}
          onChange={(event) => setCreateForm((current) => ({ ...current, case_name: event.target.value }))}
          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3 text-ink outline-none transition focus:border-pine"
        />
      </label>
      <label>
        <span className="mb-2 block text-sm font-semibold text-ink">Petitioner email</span>
        <input
          type="email"
          value={createForm.petitioner_email}
          onChange={(event) => setCreateForm((current) => ({ ...current, petitioner_email: event.target.value }))}
          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3 text-ink outline-none transition focus:border-pine"
        />
      </label>
      <label>
        <span className="mb-2 block text-sm font-semibold text-ink">Beneficiary email</span>
        <input
          type="email"
          value={createForm.beneficiary_email}
          onChange={(event) => setCreateForm((current) => ({ ...current, beneficiary_email: event.target.value }))}
          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3 text-ink outline-none transition focus:border-pine"
        />
      </label>
      <label className="md:col-span-2">
        <span className="mb-2 block text-sm font-semibold text-ink">Country of focus</span>
        <input
          value={createForm.country_of_focus}
          onChange={(event) => setCreateForm((current) => ({ ...current, country_of_focus: event.target.value }))}
          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3 text-ink outline-none transition focus:border-pine"
        />
      </label>
      <div className="md:col-span-2 flex flex-col gap-4 rounded-[1.75rem] border border-ink/10 bg-paper/70 p-4 md:flex-row md:items-center md:justify-between">
        <p className="max-w-xl text-sm leading-6 text-ink/68">
          A new case starts with an empty checklist, no uploads, and its own intake workspace.
        </p>
        <button
          type="submit"
          disabled={isPending}
          className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:bg-pine disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isPending ? "Creating..." : "Create case"}
        </button>
      </div>
    </form>
  );

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 py-6 md:px-8 md:py-8">
      <section className="relative overflow-hidden rounded-[2.4rem] border border-white/50 bg-gradient-to-br from-paper via-[#fbf7ef] to-mist px-6 py-8 shadow-panel md:px-10 md:py-10">
        <div className="absolute inset-y-0 right-0 w-1/2 bg-[radial-gradient(circle_at_top,rgba(37,103,93,0.16),transparent_54%)]" />
        <div className="relative z-10 grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-pine/75">Phase 1 packet workspace</p>
            <h1 className="mt-3 max-w-3xl font-display text-4xl leading-tight text-ink md:text-5xl">
              A shorter, calmer way to prepare the packet.
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-ink/72 md:text-lg">
              Keep the next action visible, tuck the long reference material behind focused sections,
              and only open the details you need for the task in front of you.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {[
                { href: "/", label: "Landing" },
                { href: "/prescreen", label: "Prescreen" },
                { href: "/packet-assembly", label: "Packet Assembly" },
                { href: "/manage-tasks", label: "Manage Tasks" },
                { href: "/legal-disclaimer", label: "Not legal advice" },
              ].map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="rounded-full border border-ink/10 bg-white/72 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink/62 transition hover:border-pine/30 hover:text-pine"
                >
                  {link.label}
                </Link>
              ))}
            </div>
            <div className="mt-5 rounded-[1.6rem] border border-ink/10 bg-white/72 px-4 py-3 text-sm leading-6 text-ink/75">
              {isBootstrapping ? "Loading the latest workspace, packet state, and source references." : message}
            </div>
            {caseSummary ? (
              <div className="mt-5 grid gap-3 rounded-[1.8rem] border border-ink/10 bg-white/72 p-4 md:grid-cols-2">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-ink/45">Open case</p>
                  <p className="mt-2 font-semibold text-ink">{caseSummary.case_name}</p>
                  <p className="mt-1 text-sm text-ink/62">
                    {petitionerName} + {beneficiaryName}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="rounded-[1.25rem] bg-paper/70 px-3 py-3">
                    <p className="text-xs uppercase tracking-[0.14em] text-ink/45">Country</p>
                    <p className="mt-1 font-medium text-ink">{countryFocusLabel}</p>
                  </div>
                  <div className="rounded-[1.25rem] bg-paper/70 px-3 py-3">
                    <p className="text-xs uppercase tracking-[0.14em] text-ink/45">Workflow</p>
                    <p className="mt-1 font-medium text-ink">{caseSummary.workflow_type.replaceAll("_", " ")}</p>
                  </div>
                </div>
              </div>
            ) : null}
            <div className="mt-4 rounded-[1.5rem] border border-ink/10 bg-white/72 p-4">
              <div className="flex flex-col gap-3 md:flex-row md:items-end">
                <div className="flex-1">
                  <CaseSelector
                    selectedCaseId={caseSummary?.id ?? ""}
                    onSelect={handleCaseSelect}
                    disabled={isPending}
                    label="Switch workspace case"
                  />
                </div>
                {caseSummary ? (
                  <button
                    type="button"
                    onClick={() => setIsCreateCaseOpen((current) => !current)}
                    disabled={isPending}
                    className="rounded-full border border-ink/12 bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:bg-pine disabled:cursor-not-allowed disabled:opacity-60 md:mb-0.5"
                  >
                    {isCreateCaseOpen ? "Close new case" : "New case"}
                  </button>
                ) : null}
              </div>
              {caseSummary && isCreateCaseOpen ? (
                <div className="mt-4 border-t border-ink/10 pt-4">{createCaseForm}</div>
              ) : null}
            </div>
            {caseSummary && nextAction ? (
              <div className="mt-6 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={nextAction.buttonAction}
                  disabled={isPending}
                  className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:bg-pine disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isPending ? "Working..." : nextAction.buttonLabel}
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("overview")}
                  className="rounded-full border border-ink/12 bg-white/72 px-5 py-3 text-sm font-semibold text-ink/75 transition hover:border-ink/25 hover:text-ink"
                >
                  Open action plan
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("references")}
                  className="rounded-full border border-ink/12 bg-white/72 px-5 py-3 text-sm font-semibold text-ink/75 transition hover:border-ink/25 hover:text-ink"
                >
                  Check sources
                </button>
              </div>
            ) : null}
          </div>

          <div className="rounded-[2rem] border border-ink/10 bg-white/74 p-6 backdrop-blur">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-pine/80">Readiness</p>
                <p className="mt-3 font-display text-4xl text-ink">
                  {caseSummary?.readiness_score ?? 0}
                  <span className="text-lg text-ink/45">/100</span>
                </p>
                <p className="mt-1 text-base text-ink/70">
                  {qa?.summary.label ?? caseSummary?.readiness_label ?? "Not started"}
                </p>
              </div>
              <div className="rounded-full border border-pine/15 bg-pine/10 px-4 py-2 text-sm text-pine">
                {progressPercent}% checklist progress
              </div>
            </div>
            <div className="mt-4 h-3 overflow-hidden rounded-full bg-ink/8">
              <div
                className="h-full rounded-full bg-gradient-to-r from-pine to-sand transition-all"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <MetricTile label="Checklist" value={checklist.length} detail="tracked items" />
              <MetricTile label="Uploads" value={uploads.length} detail="linked files" />
              <MetricTile
                label="Open QA"
                value={unresolvedIssues.length}
                detail={unresolvedIssues.length ? "issues to review" : "nothing flagged"}
              />
            </div>
          </div>
        </div>
      </section>

      {isBootstrapping ? (
        <Card title="Restoring the workspace" eyebrow="Please wait">
          <p className="text-sm leading-6 text-ink/72">
            Pulling the latest case, checklist, uploads, QA state, and official-reference content into one view.
          </p>
        </Card>
      ) : null}

      {!isBootstrapping && !caseSummary ? (
        <Card title="Create the case" eyebrow="Start here" className="mx-auto w-full max-w-3xl">
          {createCaseForm}
        </Card>
      ) : null}

      {!isBootstrapping && caseSummary ? (
        <>
          <div className="sticky top-4 z-20">
            <div className="overflow-x-auto rounded-full border border-white/60 bg-white/82 p-1 shadow-sm backdrop-blur">
              <div className="inline-flex min-w-full gap-1">
                {WORKSPACE_TABS.map((tab) => (
                  <TabButton
                    key={tab.id}
                    label={tab.label}
                    detail={tab.detail}
                    isActive={activeTab === tab.id}
                    onClick={() => setActiveTab(tab.id)}
                  />
                ))}
              </div>
            </div>
          </div>

          {activeTab === "overview" ? (
            <div className="grid gap-6 xl:grid-cols-[1.08fr_0.92fr]">
              <div className="flex flex-col gap-6">
                <Card title="What needs attention" eyebrow="Today">
                  {nextAction ? (
                    <div className="rounded-[1.75rem] bg-ink px-5 py-5 text-white">
                      <p className="text-xs uppercase tracking-[0.18em] text-white/62">Primary next step</p>
                      <h3 className="mt-3 font-display text-3xl leading-tight">{nextAction.title}</h3>
                      <p className="mt-3 max-w-2xl text-sm leading-6 text-white/78">{nextAction.description}</p>
                      <button
                        type="button"
                        onClick={nextAction.buttonAction}
                        disabled={isPending}
                        className="mt-5 rounded-full bg-white px-5 py-3 text-sm font-semibold text-ink transition hover:bg-paper disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {isPending ? "Working..." : nextAction.buttonLabel}
                      </button>
                    </div>
                  ) : null}
                  <div className="mt-4 grid gap-3">
                    {priorityNotes.map((note) => (
                      <button
                        key={note.title}
                        type="button"
                        onClick={() => setActiveTab(note.tab)}
                        className="rounded-[1.5rem] border border-ink/10 bg-paper/70 px-4 py-4 text-left transition hover:border-pine/30 hover:bg-white/78"
                      >
                        <p className="font-semibold text-ink">{note.title}</p>
                        <p className="mt-1 text-sm leading-6 text-ink/68">{note.detail}</p>
                      </button>
                    ))}
                  </div>
                </Card>

                <Card
                  title="Packet momentum"
                  eyebrow="By form"
                  action={
                    <button
                      type="button"
                      onClick={() => setActiveTab("packet")}
                      className="rounded-full border border-ink/12 bg-white/72 px-4 py-2 text-sm font-semibold text-ink/75 transition hover:border-ink/25 hover:text-ink"
                    >
                      Open packet view
                    </button>
                  }
                >
                  {formPacketPlans.length ? (
                    <div className="grid gap-3 md:grid-cols-2">
                      {formPacketPlans.map((packet) => {
                        const packetProgress = packet.requiredCount
                          ? Math.round((packet.completedRequired / packet.requiredCount) * 100)
                          : 0;

                        return (
                          <button
                            key={packet.code}
                            type="button"
                            onClick={() => setActiveTab("packet")}
                            className="rounded-[1.5rem] border border-ink/10 bg-white/74 p-4 text-left transition hover:border-pine/30"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="font-semibold text-ink">{packet.label}</p>
                                <p className="mt-1 text-sm text-ink/62">
                                  {packet.completedRequired}/{packet.requiredCount} required milestones covered
                                </p>
                              </div>
                              <span className="rounded-full bg-pine/10 px-3 py-1 text-xs uppercase tracking-[0.16em] text-pine">
                                {packetProgress}%
                              </span>
                            </div>
                            <p className="mt-3 text-sm leading-6 text-ink/68">
                              {packet.nextMissing.length
                                ? `Still needed: ${packet.nextMissing.join(", ")}`
                                : "Required milestones for this packet are currently covered."}
                            </p>
                          </button>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-sm leading-6 text-ink/72">
                      Generate the checklist after saving intake to see the form-by-form packet plan.
                    </p>
                  )}
                </Card>
              </div>

              <div className="flex flex-col gap-6">
                <Card title="Case snapshot" eyebrow="Checklist-driving facts">
                  <div className="rounded-[1.75rem] border border-ink/10 bg-paper/65 px-5 py-4">
                    <SnapshotRow label="Case" value={caseSummary.case_name} />
                    <SnapshotRow label="Petitioner" value={petitionerName} />
                    <SnapshotRow label="Beneficiary" value={beneficiaryName} />
                    <SnapshotRow
                      label="Marriage date"
                      value={intakeValues.marriage_date ? formatDateLabel(intakeValues.marriage_date) : "Not set"}
                    />
                    <SnapshotRow label="Country focus" value={countryFocusLabel} />
                    <SnapshotRow label="Filing track" value={filingTrackLabel} />
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <span className="rounded-full bg-white/78 px-3 py-1 text-xs uppercase tracking-[0.16em] text-ink/68 ring-1 ring-ink/10">
                      {intakeValues.first_marriage_for_both ? "First marriage" : "Prior marriage history"}
                    </span>
                    <span className="rounded-full bg-white/78 px-3 py-1 text-xs uppercase tracking-[0.16em] text-ink/68 ring-1 ring-ink/10">
                      {intakeValues.needs_translation ? "Needs translations" : "English-ready"}
                    </span>
                    {intakeValues.wants_i765 ? (
                      <span className="rounded-full bg-white/78 px-3 py-1 text-xs uppercase tracking-[0.16em] text-ink/68 ring-1 ring-ink/10">
                        Includes I-765
                      </span>
                    ) : null}
                    {intakeValues.wants_i131 ? (
                      <span className="rounded-full bg-white/78 px-3 py-1 text-xs uppercase tracking-[0.16em] text-ink/68 ring-1 ring-ink/10">
                        Includes I-131
                      </span>
                    ) : null}
                    {hasRiskFlags ? (
                      <span className="rounded-full bg-clay/12 px-3 py-1 text-xs uppercase tracking-[0.16em] text-clay ring-1 ring-clay/20">
                        Risk review needed
                      </span>
                    ) : null}
                  </div>
                </Card>

                <Card title="Recent activity" eyebrow="Uploads and QA">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <MetricTile
                      label="Latest QA"
                      value={qa?.summary.label ?? "Not run"}
                      detail={qa ? `${qa.summary.required_completion_pct}% required completion` : "Run QA after a few uploads"}
                    />
                    <MetricTile
                      label="Missing required"
                      value={incompleteRequiredItems.length}
                      detail="checklist items still open"
                    />
                  </div>
                  <div className="mt-4 space-y-3">
                    {recentUploads.length ? (
                      recentUploads.map((upload) => (
                        <div key={upload.id} className="rounded-[1.4rem] border border-ink/10 bg-white/74 px-4 py-4">
                          <p className="font-semibold text-ink">{upload.original_filename}</p>
                          <p className="mt-1 text-sm text-ink/62">
                            {getSatisfiedChecklistCodes(upload).join(", ") || "unassigned"} •{" "}
                            {upload.document_language}
                          </p>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-[1.4rem] border border-ink/10 bg-white/74 px-4 py-4 text-sm leading-6 text-ink/68">
                        No uploads are linked yet. The review tab is the quickest place to start assigning files.
                      </div>
                    )}
                  </div>
                </Card>
              </div>
            </div>
          ) : null}

          {activeTab === "intake" ? (
            <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
              <Card
                title="Intake and case profile"
                eyebrow="Workflow 1"
                action={
                  <button
                    type="button"
                    onClick={handleGenerateChecklist}
                    disabled={isPending}
                    className="rounded-full bg-pine px-5 py-3 text-sm font-semibold text-white transition hover:bg-ink disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isPending ? "Working..." : "Generate checklist"}
                  </button>
                }
              >
                <form className="space-y-5" onSubmit={handleSaveIntake}>
                  <FieldGroup
                    title="People"
                    description="These names and contact details show up everywhere, so keeping them clean pays off quickly."
                  >
                    <div className="grid gap-4 md:grid-cols-2">
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Petitioner first name</span>
                        <input
                          value={intakeValues.petitioner_first_name}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              petitioner_first_name: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Petitioner middle name</span>
                        <input
                          value={intakeValues.petitioner_middle_name}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              petitioner_middle_name: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Petitioner last name</span>
                        <input
                          value={intakeValues.petitioner_last_name}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              petitioner_last_name: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Petitioner date of birth</span>
                        <input
                          type="date"
                          value={intakeValues.petitioner_date_of_birth}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              petitioner_date_of_birth: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Petitioner email</span>
                        <input
                          type="email"
                          value={intakeValues.petitioner_email}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              petitioner_email: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Petitioner phone</span>
                        <input
                          value={intakeValues.petitioner_phone}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              petitioner_phone: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label className="md:col-span-2">
                        <span className="mb-2 block text-sm font-semibold text-ink">Petitioner current address</span>
                        <textarea
                          value={intakeValues.petitioner_current_address}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              petitioner_current_address: event.target.value,
                            }))
                          }
                          rows={2}
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Annual sponsor income</span>
                        <input
                          type="number"
                          min="0"
                          value={intakeValues.annual_income}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              annual_income: Number(event.target.value),
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Beneficiary first name</span>
                        <input
                          value={intakeValues.beneficiary_first_name}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_first_name: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Beneficiary middle name</span>
                        <input
                          value={intakeValues.beneficiary_middle_name}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_middle_name: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Beneficiary last name</span>
                        <input
                          value={intakeValues.beneficiary_last_name}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_last_name: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Beneficiary date of birth</span>
                        <input
                          type="date"
                          value={intakeValues.beneficiary_date_of_birth}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_date_of_birth: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Beneficiary email</span>
                        <input
                          type="email"
                          value={intakeValues.beneficiary_email}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_email: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Beneficiary phone</span>
                        <input
                          value={intakeValues.beneficiary_phone}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_phone: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                    </div>
                  </FieldGroup>

                  <FieldGroup
                    title="Case basics"
                    description="These facts determine the likely filing flow, country guidance, and several checklist requirements."
                  >
                    <div className="grid gap-4 md:grid-cols-2">
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Marriage date</span>
                        <input
                          type="date"
                          value={intakeValues.marriage_date}
                          onChange={(event) =>
                            setIntakeValues((current) => ({ ...current, marriage_date: event.target.value }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Country of birth</span>
                        <input
                          value={intakeValues.beneficiary_country_of_birth}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_country_of_birth: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Country of citizenship</span>
                        <input
                          value={intakeValues.beneficiary_country_of_citizenship}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_country_of_citizenship: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Beneficiary location</span>
                        <select
                          value={intakeValues.beneficiary_location}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_location: event.target.value as "usa" | "abroad",
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        >
                          <option value="usa">Already in the U.S.</option>
                          <option value="abroad">Outside the U.S.</option>
                        </select>
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Current immigration status</span>
                        <input
                          value={intakeValues.beneficiary_current_immigration_status}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_current_immigration_status: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">A-Number, if any</span>
                        <input
                          value={intakeValues.beneficiary_a_number}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_a_number: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">I-94 number</span>
                        <input
                          value={intakeValues.beneficiary_i94_number}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_i94_number: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Passport number</span>
                        <input
                          value={intakeValues.beneficiary_passport_number}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_passport_number: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Passport country</span>
                        <input
                          value={intakeValues.beneficiary_passport_country}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_passport_country: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Passport expiration</span>
                        <input
                          type="date"
                          value={intakeValues.beneficiary_passport_expiration}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_passport_expiration: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Household size</span>
                        <input
                          type="number"
                          min="1"
                          value={intakeValues.household_size}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              household_size: Number(event.target.value),
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                    </div>
                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <BooleanField
                        label="Entered the U.S. legally"
                        description="Important for a standard adjustment-of-status flow."
                        checked={intakeValues.beneficiary_entered_us_legally}
                        onChange={(value) =>
                          setIntakeValues((current) => ({
                            ...current,
                            beneficiary_entered_us_legally: value,
                          }))
                        }
                      />
                      <BooleanField
                        label="First marriage for both spouses"
                        checked={intakeValues.first_marriage_for_both}
                        onChange={(value) =>
                          setIntakeValues((current) => ({ ...current, first_marriage_for_both: value }))
                        }
                      />
                    </div>
                  </FieldGroup>

                  <FieldGroup
                    title="Beneficiary address and work history"
                    description="USCIS forms often ask for recent address and employment history. Saving it here also gives QA something concrete to compare against uploaded forms."
                  >
                    <div className="grid gap-4 md:grid-cols-2">
                      <label className="md:col-span-2">
                        <span className="mb-2 block text-sm font-semibold text-ink">Current physical address</span>
                        <textarea
                          value={intakeValues.beneficiary_current_address}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_current_address: event.target.value,
                            }))
                          }
                          rows={2}
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Current address since</span>
                        <input
                          type="date"
                          value={intakeValues.beneficiary_current_address_since}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_current_address_since: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label className="md:col-span-2">
                        <span className="mb-2 block text-sm font-semibold text-ink">Prior address 1</span>
                        <textarea
                          value={intakeValues.beneficiary_prior_address_1}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_prior_address_1: event.target.value,
                            }))
                          }
                          rows={2}
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Prior address 1 from</span>
                        <input
                          type="date"
                          value={intakeValues.beneficiary_prior_address_1_from}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_prior_address_1_from: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Prior address 1 to</span>
                        <input
                          type="date"
                          value={intakeValues.beneficiary_prior_address_1_to}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_prior_address_1_to: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label className="md:col-span-2">
                        <span className="mb-2 block text-sm font-semibold text-ink">Prior address 2</span>
                        <textarea
                          value={intakeValues.beneficiary_prior_address_2}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_prior_address_2: event.target.value,
                            }))
                          }
                          rows={2}
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Prior address 2 from</span>
                        <input
                          type="date"
                          value={intakeValues.beneficiary_prior_address_2_from}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_prior_address_2_from: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Prior address 2 to</span>
                        <input
                          type="date"
                          value={intakeValues.beneficiary_prior_address_2_to}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_prior_address_2_to: event.target.value,
                            }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                      <label className="md:col-span-2">
                        <span className="mb-2 block text-sm font-semibold text-ink">Employment history notes</span>
                        <textarea
                          value={intakeValues.beneficiary_employment_history}
                          onChange={(event) =>
                            setIntakeValues((current) => ({
                              ...current,
                              beneficiary_employment_history: event.target.value,
                            }))
                          }
                          rows={3}
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                          placeholder="Employer names, dates, and gaps to review before form fill."
                        />
                      </label>
                    </div>
                  </FieldGroup>

                  <FieldGroup
                    title="Filing choices"
                    description="Keep the high-signal preferences visible here and move deeper evidence review out of the way."
                  >
                    <div className="grid gap-4 md:grid-cols-2">
                      <BooleanField
                        label="Needs certified translations"
                        checked={intakeValues.needs_translation}
                        onChange={(value) =>
                          setIntakeValues((current) => ({ ...current, needs_translation: value }))
                        }
                      />
                      <BooleanField
                        label="Include Form I-765"
                        description="Use this if the spouse wants work authorization while waiting."
                        checked={intakeValues.wants_i765}
                        onChange={(value) =>
                          setIntakeValues((current) => ({ ...current, wants_i765: value }))
                        }
                      />
                      <BooleanField
                        label="Include Form I-131"
                        description="Use this if advance parole may be needed."
                        checked={intakeValues.wants_i131}
                        onChange={(value) =>
                          setIntakeValues((current) => ({ ...current, wants_i131: value }))
                        }
                      />
                      <BooleanField
                        label="Children involved in the case"
                        checked={intakeValues.has_children}
                        onChange={(value) =>
                          setIntakeValues((current) => ({ ...current, has_children: value }))
                        }
                      />
                    </div>
                  </FieldGroup>

                  <DisclosurePanel
                    title="Evidence and risk review"
                    subtitle="This section stays available, but it no longer needs to dominate the whole page."
                    defaultOpen={hasRiskFlags}
                    meta={
                      hasRiskFlags ? (
                        <span className="rounded-full bg-clay/12 px-3 py-1 text-xs uppercase tracking-[0.16em] text-clay ring-1 ring-clay/20">
                          Review flagged
                        </span>
                      ) : undefined
                    }
                  >
                    <div className="grid gap-4 md:grid-cols-2">
                      <BooleanField
                        label="Joint lease available"
                        checked={intakeValues.has_joint_lease}
                        onChange={(value) =>
                          setIntakeValues((current) => ({ ...current, has_joint_lease: value }))
                        }
                      />
                      <BooleanField
                        label="Joint bank evidence available"
                        checked={intakeValues.has_joint_bank_account}
                        onChange={(value) =>
                          setIntakeValues((current) => ({ ...current, has_joint_bank_account: value }))
                        }
                      />
                      <BooleanField
                        label="Relationship photos available"
                        checked={intakeValues.has_relationship_photos}
                        onChange={(value) =>
                          setIntakeValues((current) => ({
                            ...current,
                            has_relationship_photos: value,
                          }))
                        }
                      />
                      <BooleanField
                        label="Affidavits available"
                        checked={intakeValues.has_affidavits}
                        onChange={(value) =>
                          setIntakeValues((current) => ({ ...current, has_affidavits: value }))
                        }
                      />
                      <BooleanField
                        label="Reviewed current USCIS fees"
                        checked={intakeValues.reviewed_current_fees}
                        onChange={(value) =>
                          setIntakeValues((current) => ({ ...current, reviewed_current_fees: value }))
                        }
                      />
                      <BooleanField
                        label="Reviewed current form editions"
                        checked={intakeValues.reviewed_current_form_editions}
                        onChange={(value) =>
                          setIntakeValues((current) => ({
                            ...current,
                            reviewed_current_form_editions: value,
                          }))
                        }
                      />
                      <BooleanField
                        label="Prior immigration denials"
                        checked={intakeValues.prior_immigration_denials}
                        onChange={(value) =>
                          setIntakeValues((current) => ({
                            ...current,
                            prior_immigration_denials: value,
                          }))
                        }
                      />
                      <BooleanField
                        label="Criminal history"
                        checked={intakeValues.criminal_history}
                        onChange={(value) =>
                          setIntakeValues((current) => ({ ...current, criminal_history: value }))
                        }
                      />
                      <BooleanField
                        label="Removal or deportation history"
                        checked={intakeValues.removal_history}
                        onChange={(value) =>
                          setIntakeValues((current) => ({ ...current, removal_history: value }))
                        }
                      />
                      <BooleanField
                        label="Identity records are inconsistent"
                        checked={intakeValues.identity_inconsistencies}
                        onChange={(value) =>
                          setIntakeValues((current) => ({
                            ...current,
                            identity_inconsistencies: value,
                          }))
                        }
                      />
                    </div>
                  </DisclosurePanel>

                  <div className="flex flex-col gap-4 rounded-[1.75rem] border border-ink/10 bg-white/75 p-4">
                    <div className="flex flex-wrap items-center gap-3">
                      <button
                        type="submit"
                        disabled={isPending}
                        className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:bg-pine disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {isPending ? "Saving..." : "Save intake"}
                      </button>
                      <button
                        type="button"
                        onClick={handleGenerateChecklist}
                        disabled={isPending}
                        className="rounded-full border border-pine/20 bg-pine/10 px-5 py-3 text-sm font-semibold text-pine transition hover:bg-pine hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {isPending ? "Working..." : "Generate checklist"}
                      </button>
                    </div>
                    {missingFields.length ? (
                      <div className="rounded-[1.4rem] bg-clay/10 px-4 py-3 text-sm leading-6 text-clay">
                        Missing required fields: {missingFields.join(", ")}
                      </div>
                    ) : (
                      <div className="rounded-[1.4rem] bg-pine/10 px-4 py-3 text-sm leading-6 text-pine">
                        Required intake fields are filled in.
                      </div>
                    )}
                    <p className="text-sm leading-6 text-ink/65">
                      Keep the intake factual and calm. When higher-risk answers stay visible here,
                      the QA pass can surface strategy-review warnings without burying the essentials.
                    </p>
                  </div>
                </form>
              </Card>

              <div className="flex flex-col gap-6">
                <Card title="Checklist signals" eyebrow="Live from intake">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <MetricTile
                      label="Likely path"
                      value={intakeValues.beneficiary_location === "usa" ? "Inside U.S." : "Outside U.S."}
                      detail={
                        intakeValues.beneficiary_entered_us_legally
                          ? "Lawful entry marked"
                          : "Lawful entry not confirmed"
                      }
                    />
                    <MetricTile
                      label="Optional forms"
                      value={`${intakeValues.wants_i765 ? "I-765" : ""}${intakeValues.wants_i765 && intakeValues.wants_i131 ? " + " : ""}${intakeValues.wants_i131 ? "I-131" : ""}` || "None"}
                      detail="Selected from intake"
                    />
                  </div>
                  <div className="mt-4 rounded-[1.5rem] border border-ink/10 bg-paper/70 px-4 py-4 text-sm leading-6 text-ink/68">
                    <p className="font-semibold text-ink">What changes after saving</p>
                    <p className="mt-2">
                      The backend uses these facts to decide form applicability, evidence needs,
                      translation expectations, and whether certain answers should trigger legal-review caution.
                    </p>
                  </div>
                </Card>

                <Card title="Reference reminders" eyebrow="Keep claims careful">
                  <div className="space-y-3 text-sm leading-6 text-ink/74">
                    {(explanations?.disclaimers ?? []).slice(0, 3).map((item) => (
                      <p key={item} className="rounded-[1.4rem] border border-ink/10 bg-paper/70 px-4 py-3">
                        {item}
                      </p>
                    ))}
                    <div className="rounded-[1.4rem] border border-clay/15 bg-clay/8 px-4 py-4">
                      <p className="font-semibold text-ink">Escalate for legal review when you see:</p>
                      <p className="mt-2 text-ink/70">
                        {explanations?.escalation_triggers.join(", ") || "higher-risk answers in intake"}
                      </p>
                    </div>
                  </div>
                </Card>
              </div>
            </div>
          ) : null}

          {activeTab === "packet" ? (
            <div className="flex flex-col gap-6">
              <Card title="Form packet milestones" eyebrow="Workflow 2">
                {formPacketPlans.length ? (
                  <div className="space-y-3">
                    <p className="text-sm leading-6 text-ink/72">
                      Each packet below follows the official USCIS references currently stored in the
                      workspace. The milestones stay folded until you want the detail.
                    </p>
                    {formPacketPlans.map((packet, index) => (
                      <DisclosurePanel
                        key={packet.code}
                        title={packet.label}
                        subtitle={
                          packet.nextMissing.length
                            ? `Still needed: ${packet.nextMissing.join(", ")}`
                            : "Required milestones for this packet are currently covered."
                        }
                        defaultOpen={index === 0 && packet.nextMissing.length > 0}
                        meta={
                          packet.accepted_edition ? (
                            <span className="rounded-full bg-pine/10 px-3 py-1 text-xs uppercase tracking-[0.16em] text-pine">
                              Edition {packet.accepted_edition}
                            </span>
                          ) : undefined
                        }
                        aside={
                          <div className="rounded-[1.25rem] border border-ink/10 bg-paper/75 px-4 py-3 text-center">
                            <p className="text-xs uppercase tracking-[0.16em] text-ink/45">Required</p>
                            <p className="mt-1 text-lg font-semibold text-ink">
                              {packet.completedRequired}/{packet.requiredCount || 0}
                            </p>
                          </div>
                        }
                      >
                        <div className="flex flex-wrap gap-3 text-sm">
                          <a
                            href={packet.official_url}
                            target="_blank"
                            rel="noreferrer"
                            className="rounded-full border border-ink/10 bg-paper/70 px-3 py-2 text-ink transition hover:border-pine hover:text-pine"
                          >
                            USCIS source
                          </a>
                          {packet.fee_url ? (
                            <a
                              href={packet.fee_url}
                              target="_blank"
                              rel="noreferrer"
                              className="rounded-full border border-ink/10 bg-paper/70 px-3 py-2 text-ink transition hover:border-pine hover:text-pine"
                            >
                              Fee reference
                            </a>
                          ) : null}
                        </div>
                        <div className="mt-4 space-y-3">
                          {packet.milestones.map((milestone) => (
                            <div
                              key={`${packet.code}-${milestone.checklist_code}`}
                              className="rounded-[1.5rem] border border-ink/10 bg-paper/65 p-4"
                            >
                              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                <div>
                                  <div className="flex flex-wrap items-center gap-2">
                                    <h4 className="font-semibold text-ink">{milestone.label}</h4>
                                    <span
                                      className={classNames(
                                        "rounded-full px-3 py-1 text-xs uppercase tracking-[0.16em] ring-1",
                                        getStatusTone(milestone.necessity),
                                      )}
                                    >
                                      {formatStatus(milestone.necessity)}
                                    </span>
                                    <span className="rounded-full bg-white/85 px-3 py-1 text-xs uppercase tracking-[0.16em] text-ink/65 ring-1 ring-ink/10">
                                      {formatRequirementType(milestone.requirement_type)}
                                    </span>
                                  </div>
                                  <p className="mt-2 text-sm leading-6 text-ink/72">{milestone.notes}</p>
                                  {milestone.conditional_note ? (
                                    <p className="mt-2 text-sm leading-6 text-ink/62">
                                      {milestone.conditional_note}
                                    </p>
                                  ) : null}
                                  {milestone.linkedUploads.length ? (
                                    <p className="mt-2 text-sm text-pine">
                                      Linked upload{milestone.linkedUploads.length > 1 ? "s" : ""}:{" "}
                                      {milestone.linkedUploads
                                        .slice(0, 3)
                                        .map((upload) => upload.original_filename)
                                        .join(", ")}
                                    </p>
                                  ) : null}
                                </div>
                                <div className="min-w-40">
                                  <p className="text-xs uppercase tracking-[0.18em] text-ink/45">Status</p>
                                  <p
                                    className={classNames(
                                      "mt-2 inline-flex rounded-full px-3 py-1 text-sm capitalize ring-1",
                                      getStatusTone(milestone.status),
                                    )}
                                  >
                                    {formatStatus(milestone.status)}
                                  </p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </DisclosurePanel>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm leading-6 text-ink/72">
                    Generate the checklist after saving intake to see form-by-form packet milestones.
                  </p>
                )}
              </Card>

              <Card title="Checklist workspace" eyebrow="Board and filters">
                {visibleChecklistCards.length ? (
                  <div className="space-y-6">
                    <div className="grid gap-3 xl:grid-cols-[minmax(0,1.4fr)_repeat(3,minmax(0,0.8fr))_auto]">
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Search tasks</span>
                        <input
                          value={searchQuery}
                          onChange={(event) => setSearchQuery(event.target.value)}
                          placeholder="Search forms, evidence, owners, or notes"
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3 text-ink"
                        />
                      </label>
                      <div className="xl:col-span-5">
                        <span className="mb-2 block text-sm font-semibold text-ink">Workflow status</span>
                        <ChoiceChips
                          options={CHECKLIST_STATUS_FILTER_OPTIONS}
                          value={statusFilter}
                          onChange={setStatusFilter}
                        />
                      </div>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Document state</span>
                        <select
                          value={documentFilter}
                          onChange={(event) => setDocumentFilter(event.target.value as ChecklistDocumentFilter)}
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3 text-ink"
                        >
                          <option value="all">All document states</option>
                          <option value="missing">Missing</option>
                          <option value="requested">Requested</option>
                          <option value="uploaded">Uploaded</option>
                          <option value="confirmed">Confirmed</option>
                        </select>
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Category</span>
                        <select
                          value={categoryFilter}
                          onChange={(event) => setCategoryFilter(event.target.value)}
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3 text-ink"
                        >
                          <option value="all">All categories</option>
                          {Array.from(new Set(visibleChecklistCards.map((item) => item.category))).map((category) => (
                            <option key={category} value={category}>
                              {formatCategory(category)}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div>
                        <span className="mb-2 block text-sm font-semibold text-ink">View</span>
                        <div className="flex rounded-2xl border border-ink/10 bg-white p-1">
                          {(["board", "list"] as ChecklistViewMode[]).map((view) => (
                            <button
                              key={view}
                              type="button"
                              onClick={() => setChecklistView(view)}
                              className={classNames(
                                "flex-1 rounded-[1rem] px-4 py-3 text-sm transition",
                                checklistView === view ? "bg-ink text-white" : "text-ink/65",
                              )}
                            >
                              {view === "board" ? "Board" : "List"}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="grid gap-3 md:grid-cols-4">
                      <div className="rounded-2xl border border-ink/10 bg-paper/80 px-4 py-4">
                        <p className="text-xs uppercase tracking-[0.18em] text-ink/45">Visible tasks</p>
                        <p className="mt-2 text-3xl font-semibold text-ink">{filteredChecklistCards.length}</p>
                      </div>
                      <div className="rounded-2xl border border-ink/10 bg-paper/80 px-4 py-4">
                        <p className="text-xs uppercase tracking-[0.18em] text-ink/45">Need uploads</p>
                        <p className="mt-2 text-3xl font-semibold text-ink">
                          {filteredChecklistCards.filter((item) => item.documentStatus === "missing").length}
                        </p>
                      </div>
                      <div className="rounded-2xl border border-ink/10 bg-paper/80 px-4 py-4">
                        <p className="text-xs uppercase tracking-[0.18em] text-ink/45">Ready to review</p>
                        <p className="mt-2 text-3xl font-semibold text-ink">
                          {
                            filteredChecklistCards.filter((item) =>
                              ["uploaded", "almost_done", "approved"].includes(item.displayStatus),
                            ).length
                          }
                        </p>
                      </div>
                      <div className="rounded-2xl border border-ink/10 bg-paper/80 px-4 py-4">
                        <p className="text-xs uppercase tracking-[0.18em] text-ink/45">Confirmed docs</p>
                        <p className="mt-2 text-3xl font-semibold text-ink">
                          {filteredChecklistCards.filter((item) => item.documentStatus === "confirmed").length}
                        </p>
                      </div>
                    </div>

                    {checklistView === "board" ? (
                      <div className="grid auto-cols-[18rem] grid-flow-col gap-4 overflow-x-auto pb-2">
                        {CHECKLIST_BOARD_ORDER.map((status) => (
                          <section
                            key={status}
                            onDragOver={(event) => {
                              event.preventDefault();
                              if (dragTargetStatus !== status) {
                                setDragTargetStatus(status);
                              }
                            }}
                            onDragLeave={() => {
                              if (dragTargetStatus === status) {
                                setDragTargetStatus(null);
                              }
                            }}
                            onDrop={(event) => {
                              event.preventDefault();
                              handleChecklistBoardDrop(status);
                            }}
                            className={classNames(
                              "rounded-[1.8rem] border border-ink/10 bg-paper/70 p-4 transition",
                              dragTargetStatus === status ? "border-pine/35 bg-pine/8" : "",
                            )}
                          >
                            <div className="flex items-center justify-between gap-3">
                              <div>
                                <p className="text-xs uppercase tracking-[0.18em] text-ink/45">Lane</p>
                                <h3 className="mt-1 font-display text-xl text-ink">{formatStatus(status)}</h3>
                              </div>
                              <span
                                className={classNames(
                                  "rounded-full px-3 py-1 text-xs uppercase tracking-[0.16em] ring-1",
                                  getStatusTone(status),
                                )}
                              >
                                {checklistBoardColumns[status].length}
                              </span>
                            </div>
                            <div className="mt-4 min-h-24 space-y-3">
                              {checklistBoardColumns[status].length ? (
                                checklistBoardColumns[status].map((item) => renderChecklistCard(item, true))
                              ) : (
                                <div className="rounded-3xl border border-dashed border-ink/12 bg-white/60 px-4 py-6 text-sm text-ink/55">
                                  Drop a task here or use the lane for status changes.
                                </div>
                              )}
                            </div>
                          </section>
                        ))}
                      </div>
                    ) : (
                      <div className="space-y-6">
                        {Object.entries(filteredChecklistGroups).map(([category, items]) => (
                          <div key={category}>
                            <div className="mb-3 flex items-center justify-between">
                              <h3 className="font-display text-xl capitalize text-ink">{formatCategory(category)}</h3>
                              <span className="text-sm text-ink/55">{items.length} items</span>
                            </div>
                            <div className="space-y-3">{items.map((item) => renderChecklistCard(item))}</div>
                          </div>
                        ))}
                      </div>
                    )}

                    {!filteredChecklistCards.length ? (
                      <div className="rounded-3xl border border-dashed border-ink/15 bg-white/60 px-4 py-6 text-sm text-ink/60">
                        No checklist items match the current filters.
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <p className="text-sm leading-6 text-ink/72">
                    Generate the checklist after saving intake. The rules engine will split forms,
                    civil records, financial evidence, marriage evidence, optional filings, and later-stage items.
                  </p>
                )}
              </Card>
            </div>
          ) : null}

          {activeTab === "review" ? (
            <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
              <div className="flex flex-col gap-6">
                <Card
                  title="Upload a document"
                  eyebrow="Linked to checklist"
                  action={
                    <button
                      type="button"
                      onClick={handleUpload}
                      disabled={isPending || !selectedFile}
                      className="rounded-full bg-clay px-5 py-3 text-sm font-semibold text-white transition hover:bg-ink disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isPending ? "Uploading..." : "Upload file"}
                    </button>
                  }
                >
                  <div className="grid gap-4">
                    <label>
                      <span className="mb-2 block text-sm font-semibold text-ink">Checklist item</span>
                      <select
                        value={uploadForm.checklistCode}
                        onChange={(event) =>
                          setUploadForm((current) => ({ ...current, checklistCode: event.target.value }))
                        }
                        className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                      >
                        <option value="">Select an item</option>
                        {uploadableItems.map((item) => (
                          <option key={item.id} value={item.code}>
                            {item.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="grid gap-4 md:grid-cols-2">
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Document language</span>
                        <select
                          value={uploadForm.language}
                          onChange={(event) =>
                            setUploadForm((current) => ({ ...current, language: event.target.value }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        >
                          <option value="english">English</option>
                          <option value="spanish">Spanish</option>
                          <option value="other">Other</option>
                        </select>
                      </label>
                      <label>
                        <span className="mb-2 block text-sm font-semibold text-ink">Document type tag</span>
                        <input
                          value={uploadForm.documentType}
                          onChange={(event) =>
                            setUploadForm((current) => ({ ...current, documentType: event.target.value }))
                          }
                          className="w-full rounded-2xl border border-ink/10 bg-white px-4 py-3"
                        />
                      </label>
                    </div>
                    <BooleanField
                      label="Certified translation attached"
                      checked={uploadForm.hasTranslation}
                      onChange={(value) =>
                        setUploadForm((current) => ({ ...current, hasTranslation: value }))
                      }
                      description="Turn this on when the upload package includes the English translation certification."
                    />
                    <label>
                      <span className="mb-2 block text-sm font-semibold text-ink">Choose file</span>
                      <input
                        key={uploadInputKey}
                        type="file"
                        accept=".pdf,.jpg,.jpeg,.png"
                        onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                        className="block w-full rounded-2xl border border-dashed border-ink/20 bg-paper/75 px-4 py-4 text-sm text-ink/70"
                      />
                    </label>
                  </div>
                </Card>

                <Card title="Uploads in workspace" eyebrow="Recent files">
                  <div className="space-y-3">
                    {uploads.length ? (
                      uploads.map((upload) => {
                        const linkedCodes = getSatisfiedChecklistCodes(upload);
                        return (
                          <div key={upload.id} className="rounded-[1.5rem] border border-ink/10 bg-white/74 p-4">
                            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                              <div>
                                <p className="font-semibold text-ink">{upload.original_filename}</p>
                                <p className="mt-1 text-sm text-ink/62">
                                  {(linkedCodes.join(", ") || "unassigned")} • {upload.document_language} • version{" "}
                                  {upload.version}
                                </p>
                                {upload.extracted_fields.source_path ? (
                                  <p className="mt-1 text-xs text-ink/55">
                                    Imported from {String(upload.extracted_fields.source_path)}
                                  </p>
                                ) : null}
                                {upload.extracted_fields.form_edition ? (
                                  <p className="mt-1 text-xs text-ink/55">
                                    Detected edition {String(upload.extracted_fields.form_edition)}
                                  </p>
                                ) : null}
                              </div>
                              <div className="flex items-center gap-2">
                                <span
                                  className={classNames(
                                    "rounded-full px-3 py-1 text-xs uppercase tracking-[0.16em] ring-1",
                                    getStatusTone(upload.upload_status),
                                  )}
                                >
                                  {formatStatus(upload.upload_status)}
                                </span>
                                <button
                                  type="button"
                                  onClick={() => handleDeleteUpload(upload.id)}
                                  className="rounded-full border border-clay/15 bg-clay/8 px-4 py-2 text-sm text-clay transition hover:bg-clay hover:text-white"
                                >
                                  Delete
                                </button>
                              </div>
                            </div>
                          </div>
                        );
                      })
                    ) : (
                      <p className="text-sm text-ink/70">No uploads yet.</p>
                    )}
                  </div>
                </Card>
              </div>

              <Card
                title="Packet QA"
                eyebrow="Completeness and risk check"
                action={
                  <button
                    type="button"
                    onClick={handleRunQa}
                    disabled={isPending}
                    className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:bg-pine disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isPending ? "Running..." : "Run QA"}
                  </button>
                }
              >
                {qa ? (
                  <div className="space-y-5">
                    <div className="rounded-[1.75rem] border border-ink/10 bg-paper/80 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-4">
                        <div>
                          <p className="font-display text-3xl text-ink">{qa.summary.label}</p>
                          <p className="mt-2 text-sm leading-6 text-ink/72">{qa.summary.explanation}</p>
                        </div>
                        <div className="rounded-[1.5rem] bg-white/75 px-5 py-4 text-center">
                          <p className="text-xs uppercase tracking-[0.18em] text-ink/45">Required completion</p>
                          <p className="mt-2 text-3xl font-semibold text-ink">
                            {qa.summary.required_completion_pct}%
                          </p>
                        </div>
                      </div>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-3 text-center">
                      {Object.entries(qa.summary.issue_counts).map(([key, value]) => (
                        <div key={key} className="rounded-[1.4rem] border border-ink/10 bg-white/75 px-3 py-4">
                          <p className="text-2xl font-semibold text-ink">{value}</p>
                          <p className="text-sm capitalize text-ink/65">{key}</p>
                        </div>
                      ))}
                    </div>
                    <div className="space-y-3">
                      {qa.issues.length ? (
                        qa.issues.map((issue) => (
                          <div key={issue.id} className="rounded-[1.5rem] border border-ink/10 bg-white/75 p-4">
                            <div className="flex flex-wrap items-center gap-2">
                              <span
                                className={classNames(
                                  "rounded-full px-3 py-1 text-xs uppercase tracking-[0.16em] ring-1",
                                  getStatusTone(issue.severity),
                                )}
                              >
                                {issue.severity}
                              </span>
                              <p className="font-semibold text-ink">{issue.title}</p>
                            </div>
                            <p className="mt-2 text-sm leading-6 text-ink/72">{issue.description}</p>
                          </div>
                        ))
                      ) : (
                        <div className="rounded-[1.5rem] border border-pine/15 bg-pine/8 px-4 py-4 text-sm text-pine">
                          No QA issues are currently open.
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="text-sm leading-6 text-ink/72">
                    Run QA after a few uploads are in place. The backend will check missing required
                    items, translation gaps, likely signature issues, and escalation triggers from intake.
                  </p>
                )}
              </Card>
            </div>
          ) : null}

          {activeTab === "references" ? (
            <div className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
              <div className="flex flex-col gap-6">
                <Card title="Guardrails" eyebrow="Keep claims careful">
                  <div className="space-y-3 text-sm leading-6 text-ink/75">
                    {(explanations?.disclaimers ?? []).map((item) => (
                      <p key={item} className="rounded-[1.4rem] border border-ink/10 bg-paper/70 px-4 py-3">
                        {item}
                      </p>
                    ))}
                    <div className="rounded-[1.4rem] border border-clay/15 bg-clay/8 px-4 py-4">
                      <p className="font-semibold text-ink">Escalate for legal review when you see:</p>
                      <p className="mt-2 text-ink/70">
                        {explanations?.escalation_triggers.join(", ") || "higher-risk answers in intake"}
                      </p>
                    </div>
                    {Object.entries(explanations?.issue_severity_help ?? {}).length ? (
                      <div className="rounded-[1.4rem] border border-ink/10 bg-white/72 px-4 py-4">
                        <p className="font-semibold text-ink">Severity guide</p>
                        <div className="mt-3 space-y-2">
                          {Object.entries(explanations?.issue_severity_help ?? {}).map(([severity, detail]) => (
                            <div key={severity} className="rounded-[1.1rem] bg-paper/70 px-3 py-3">
                              <p className="text-xs uppercase tracking-[0.16em] text-ink/48">{severity}</p>
                              <p className="mt-1 text-sm text-ink/68">{detail}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                </Card>

                <Card title="Country guidance" eyebrow="Civil documents and translations">
                  {guidance ? (
                    <div className="space-y-4">
                      <div className="rounded-[1.5rem] border border-ink/10 bg-paper/70 px-4 py-4">
                        <p className="text-sm uppercase tracking-[0.2em] text-pine/70">{guidance.country_name}</p>
                        <p className="mt-2 text-sm leading-6 text-ink/75">{guidance.overview}</p>
                      </div>
                      <div className="space-y-3">
                        {guidance.documents.map((document) => (
                          <DisclosurePanel
                            key={document.code}
                            title={document.label}
                            subtitle={`Translation required: ${document.translation_required ? "Yes" : "No"}`}
                            meta={
                              <span className="rounded-full bg-sand/35 px-3 py-1 text-xs uppercase tracking-[0.15em] text-ink/75">
                                {document.common_name}
                              </span>
                            }
                          >
                            <ul className="space-y-2 text-sm text-ink/70">
                              {document.tips.map((tip) => (
                                <li key={tip} className="rounded-[1.2rem] bg-paper/70 px-3 py-3">
                                  {tip}
                                </li>
                              ))}
                            </ul>
                          </DisclosurePanel>
                        ))}
                      </div>
                      <div className="rounded-[1.5rem] border border-ink/10 bg-mist/50 px-4 py-4 text-sm leading-6 text-ink/75">
                        <p>{guidance.translation_note}</p>
                        <p className="mt-2">{guidance.availability_note}</p>
                      </div>
                      {(guidance.sources ?? []).length ? (
                        <div className="rounded-[1.5rem] border border-ink/10 bg-white/74 px-4 py-4">
                          <p className="font-semibold text-ink">Country sources</p>
                          <div className="mt-3 flex flex-wrap gap-3 text-sm">
                            {guidance.sources.map((source) =>
                              source.url ? (
                                <a
                                  key={`${source.label}-${source.url}`}
                                  href={source.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="rounded-full border border-ink/10 bg-paper/70 px-3 py-2 text-ink transition hover:border-pine hover:text-pine"
                                >
                                  {source.label}
                                </a>
                              ) : (
                                <span
                                  key={source.label}
                                  className="rounded-full border border-ink/10 bg-paper/70 px-3 py-2 text-ink/70"
                                >
                                  {source.label}
                                </span>
                              ),
                            )}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <p className="text-sm text-ink/70">Country guidance will appear once a case is created.</p>
                  )}
                </Card>
              </div>

              <Card title="USCIS requirement references" eyebrow="Source-backed form details">
                {uscisRequirements ? (
                  <div className="space-y-4">
                    <div className="rounded-[1.5rem] border border-ink/10 bg-paper/70 px-4 py-4 text-sm leading-6 text-ink/72">
                      Verified from official USCIS pages on {formatDateLabel(uscisRequirements.verified_on)}.
                      Filing fees should still be confirmed again right before mailing.
                    </div>
                    {(uscisRequirements.general_rules ?? []).length ? (
                      <DisclosurePanel
                        title="General filing rules"
                        subtitle="Repository-wide rules that apply across forms."
                        defaultOpen
                      >
                        <div className="space-y-3">
                          {uscisRequirements.general_rules.map((rule) => (
                            <div key={rule.code} className="rounded-[1.4rem] border border-ink/10 bg-white/74 p-4">
                              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                <div>
                                  <p className="font-semibold text-ink">{rule.label}</p>
                                  <p className="mt-1 text-sm leading-6 text-ink/70">{rule.summary}</p>
                                </div>
                                <a
                                  href={rule.official_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="rounded-full border border-ink/10 bg-paper/70 px-3 py-2 text-sm text-ink transition hover:border-pine hover:text-pine"
                                >
                                  USCIS source
                                </a>
                              </div>
                              {(rule.important_notes ?? []).length ? (
                                <div className="mt-3 space-y-2">
                                  {rule.important_notes.map((note) => (
                                    <p key={note} className="rounded-[1.1rem] bg-paper/70 px-3 py-3 text-sm text-ink/68">
                                      {note}
                                    </p>
                                  ))}
                                </div>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      </DisclosurePanel>
                    ) : null}
                    <div className="space-y-3">
                      {uscisRequirements.forms.map((requirement) => (
                        <DisclosurePanel
                          key={requirement.code}
                          title={requirement.label}
                          subtitle={requirement.summary}
                          meta={
                            requirement.accepted_edition ? (
                              <span className="rounded-full bg-pine/10 px-3 py-1 text-xs uppercase tracking-[0.16em] text-pine">
                                Edition {requirement.accepted_edition}
                              </span>
                            ) : undefined
                          }
                        >
                          <div className="flex flex-wrap gap-3 text-sm">
                            <a
                              href={requirement.official_url}
                              target="_blank"
                              rel="noreferrer"
                              className="rounded-full border border-ink/10 bg-paper/70 px-3 py-2 text-ink transition hover:border-pine hover:text-pine"
                            >
                              USCIS source
                            </a>
                            {requirement.fee_url ? (
                              <a
                                href={requirement.fee_url}
                                target="_blank"
                                rel="noreferrer"
                                className="rounded-full border border-ink/10 bg-paper/70 px-3 py-2 text-ink transition hover:border-pine hover:text-pine"
                              >
                                Fee reference
                              </a>
                            ) : null}
                          </div>
                          {(requirement.important_notes ?? []).length ? (
                            <div className="mt-4 space-y-2 text-sm text-ink/70">
                              {requirement.important_notes.map((note) => (
                                <p key={note} className="rounded-[1.1rem] bg-paper/70 px-3 py-3">
                                  {note}
                                </p>
                              ))}
                            </div>
                          ) : null}
                          {requirement.initial_evidence.length ? (
                            <div className="mt-4 space-y-2">
                              <p className="text-xs uppercase tracking-[0.18em] text-ink/45">
                                Tracked packet evidence
                              </p>
                              <div className="space-y-2 text-sm text-ink/70">
                                {requirement.initial_evidence.map((evidence) => (
                                  <div
                                    key={`${requirement.code}-${evidence.checklist_code}`}
                                    className="rounded-[1.2rem] border border-ink/10 bg-paper/70 px-3 py-3"
                                  >
                                    <div className="flex flex-wrap items-center gap-2">
                                      <span className="font-semibold text-ink">{evidence.label}</span>
                                      <span
                                        className={classNames(
                                          "rounded-full px-3 py-1 text-xs uppercase tracking-[0.16em] ring-1",
                                          getStatusTone(evidence.necessity),
                                        )}
                                      >
                                        {formatStatus(evidence.necessity)}
                                      </span>
                                    </div>
                                    <p className="mt-2">{evidence.notes}</p>
                                    {evidence.conditional_note ? (
                                      <p className="mt-2 text-ink/60">{evidence.conditional_note}</p>
                                    ) : null}
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : null}
                        </DisclosurePanel>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-ink/70">USCIS requirement references are loading.</p>
                )}
              </Card>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

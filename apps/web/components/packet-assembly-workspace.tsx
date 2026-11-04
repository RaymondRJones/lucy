"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState, useTransition } from "react";

import { AppShell } from "@/components/app-shell";
import { CaseSelector } from "@/components/case-selector";
import {
  Badge,
  Card,
  Notice,
  PageHeader,
  SectionHeader,
  Spinner,
  StatusMessage,
  buttonClass,
  cardClass,
  cx,
  hintClass,
  inputClass,
  labelClass,
} from "@/components/ui";
import {
  apiUrl,
  confirmUpload,
  deleteUpload,
  generateChecklist,
  generatePacketAssembly,
  getCase,
  getChecklist,
  getG1450PaymentOptions,
  listCases,
  listUploads,
  requestUpload,
  uploadBinary,
} from "@/lib/api";
import { getSavedCaseId, rememberCaseId } from "@/lib/case-storage";
import { GENERATED_ONLY_UPLOAD_CODES, NOT_EVIDENCE_CODES, getSatisfiedChecklistCodes } from "@/lib/evidence";
import { formatFieldList, getG1450PaymentFieldIssues, getG1650PaymentFieldIssues } from "@/lib/g1450-validation";
import type {
  CaseSummary,
  ChecklistItem,
  ChecklistResponse,
  G1450PaymentOptions,
  G1650BankDetails,
  PacketAssemblyResponse,
  UploadRecord,
} from "@/lib/types";

const FORM_LABELS: Record<string, string> = {
  form_g1145: "G-1145 e-notification",
  form_i130: "I-130 petition",
  form_i130a: "I-130A spouse supplement",
  form_i485: "I-485 adjustment",
  form_i864: "I-864 support",
  form_i765: "I-765 work authorization",
  form_i131: "I-131 travel document",
  payment_g1450: "G-1450 or G-1650 payment",
  form_i693: "I-693 medical exam",
};

const CARD_TYPES = ["Visa", "Mastercard", "American Express", "Discover"];
const PACKET_PAYMENT_CODES = new Set(["form_i130", "form_i485", "form_i765", "form_i131"]);
const MAX_PACKET_UPLOAD_SIZE_MB = 100;

const DEFAULT_PAYMENT_FORM = {
  cardholder_name: "",
  credit_card_type: "Visa",
  credit_card_number: "",
  expiration_month: "",
  expiration_year: "",
  security_code: "",
  daytime_phone_number: "",
  email: "",
  billing_address: {
    street_1: "",
    street_2: "",
    city: "",
    state: "",
    postal_code: "",
  },
};

const DEFAULT_BANK_FORM: G1650BankDetails = {
  account_ownership: "personal",
  account_type: "checking",
  account_holder_name: "",
  business_name: "",
  bank_name: "",
  routing_number: "",
  account_number: "",
};

const US_LOCATIONS = [
  ["AL", "Alabama"],
  ["AK", "Alaska"],
  ["AZ", "Arizona"],
  ["AR", "Arkansas"],
  ["CA", "California"],
  ["CO", "Colorado"],
  ["CT", "Connecticut"],
  ["DE", "Delaware"],
  ["DC", "District of Columbia"],
  ["FL", "Florida"],
  ["GA", "Georgia"],
  ["GU", "Guam"],
  ["HI", "Hawaii"],
  ["ID", "Idaho"],
  ["IL", "Illinois"],
  ["IN", "Indiana"],
  ["IA", "Iowa"],
  ["KS", "Kansas"],
  ["KY", "Kentucky"],
  ["LA", "Louisiana"],
  ["ME", "Maine"],
  ["MD", "Maryland"],
  ["MA", "Massachusetts"],
  ["MI", "Michigan"],
  ["MN", "Minnesota"],
  ["MS", "Mississippi"],
  ["MO", "Missouri"],
  ["MT", "Montana"],
  ["NE", "Nebraska"],
  ["NV", "Nevada"],
  ["NH", "New Hampshire"],
  ["NJ", "New Jersey"],
  ["NM", "New Mexico"],
  ["NY", "New York"],
  ["NC", "North Carolina"],
  ["ND", "North Dakota"],
  ["MP", "Northern Mariana Islands"],
  ["OH", "Ohio"],
  ["OK", "Oklahoma"],
  ["OR", "Oregon"],
  ["PA", "Pennsylvania"],
  ["PR", "Puerto Rico"],
  ["RI", "Rhode Island"],
  ["SC", "South Carolina"],
  ["SD", "South Dakota"],
  ["TN", "Tennessee"],
  ["TX", "Texas"],
  ["UT", "Utah"],
  ["VT", "Vermont"],
  ["VI", "U.S. Virgin Islands"],
  ["VA", "Virginia"],
  ["WA", "Washington"],
  ["WV", "West Virginia"],
  ["WI", "Wisconsin"],
  ["WY", "Wyoming"],
];

type UploadDraft = {
  file: File | null;
  documentLanguage: string;
  hasTranslation: boolean;
};

type PaymentMode = "generate" | "existing";
type PaymentMethod = "card" | "ach";
type PaymentFormState = typeof DEFAULT_PAYMENT_FORM;
type PaymentTextField = Exclude<keyof PaymentFormState, "billing_address">;
type BillingField = keyof PaymentFormState["billing_address"];

function classNames(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

function formatCurrency(value: string) {
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return `$${value}`;
  }
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(parsed);
}

function packetDocumentKey(
  document: {
    source_type: string;
    filename: string | null;
    label: string;
    section: string | null;
    checklist_item_code: string | null;
    upload_id: string | null;
    form_key: string | null;
  },
  index: number,
) {
  return [
    index,
    document.source_type,
    document.section ?? "no-section",
    document.upload_id ?? document.form_key ?? document.checklist_item_code ?? "no-id",
    document.filename ?? "no-filename",
    document.label,
  ].join("|");
}

function formatStatus(value: string) {
  return value.replaceAll("_", " ");
}

function categoryLabel(value: string) {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(" ");
}

function itemGroupKey(item: ChecklistItem) {
  const formCodes = Array.isArray(item.item_metadata.form_codes)
    ? item.item_metadata.form_codes.filter((value): value is string => typeof value === "string")
    : [];
  return formCodes[0] || `category:${item.category}`;
}

function itemGroupLabel(key: string) {
  if (key.startsWith("category:")) {
    return categoryLabel(key.replace("category:", ""));
  }
  return FORM_LABELS[key] ?? categoryLabel(key.replace("form_", ""));
}

function defaultUploadDraft(): UploadDraft {
  return {
    file: null,
    documentLanguage: "english",
    hasTranslation: false,
  };
}

function fileExceedsUploadLimit(file: File) {
  return file.size > MAX_PACKET_UPLOAD_SIZE_MB * 1024 * 1024;
}

function paymentFormHasUserInput(form: PaymentFormState) {
  const textValues = [
    form.cardholder_name,
    form.credit_card_number,
    form.expiration_month,
    form.expiration_year,
    form.security_code,
    form.daytime_phone_number,
    form.email,
    form.billing_address.street_1,
    form.billing_address.street_2,
    form.billing_address.city,
    form.billing_address.state,
    form.billing_address.postal_code,
  ];
  return textValues.some((value) => value.trim().length > 0) || form.credit_card_type !== DEFAULT_PAYMENT_FORM.credit_card_type;
}

function bankFormHasUserInput(form: G1650BankDetails) {
  return [form.account_holder_name, form.business_name, form.bank_name, form.routing_number, form.account_number].some(
    (value) => value.trim().length > 0,
  );
}

function scenarioDefaults(caseName: string) {
  const normalized = caseName.toLowerCase();
  if (!normalized.startsWith("packet scenario - ")) {
    return null;
  }
  if (normalized.includes("california")) {
    return { stateCode: "CA", carrier: "usps" as const };
  }
  if (normalized.includes("texas")) {
    return { stateCode: "TX", carrier: "private" as const };
  }
  if (normalized.includes("georgia")) {
    return { stateCode: "GA", carrier: "usps" as const };
  }
  if (normalized.includes("arizona")) {
    return { stateCode: "AZ", carrier: "private" as const };
  }
  return null;
}

function scenarioShortLabel(caseName: string) {
  return caseName.replace("Packet scenario - ", "");
}

function uniqueScenarioCases(cases: CaseSummary[]) {
  const byName = new Map<string, CaseSummary>();
  for (const candidate of cases) {
    if (!scenarioDefaults(candidate.case_name) || byName.has(candidate.case_name)) {
      continue;
    }
    byName.set(candidate.case_name, candidate);
  }
  return Array.from(byName.values());
}

// Names a USCIS link from its last path segment, such as "g-1650" -> "USCIS G-1650 page".
function sourceLinkLabel(url: string) {
  const segment = url.replace(/\/+$/, "").split("/").pop() ?? "";
  if (/^[a-z]-?\d+[a-z]?$/i.test(segment)) {
    return `USCIS ${segment.toUpperCase()} page`;
  }
  const words = segment.replaceAll("-", " ");
  return words ? `USCIS: ${words.charAt(0).toUpperCase()}${words.slice(1)}` : "USCIS source";
}

// Renders backend guidance text with its source URLs as links.
function LinkedText({ text }: { text: string }) {
  const parts = text.split(/(https:\/\/[^\s]+?)(?=[.,;:]?(?:\s|$))/g);
  return (
    <>
      {parts.map((part, index) =>
        part.startsWith("https://") ? (
          <a key={index} href={part} target="_blank" rel="noreferrer" className="font-semibold text-pine underline-offset-4 hover:underline">
            {sourceLinkLabel(part)}
          </a>
        ) : (
          <span key={index}>{part}</span>
        ),
      )}
    </>
  );
}

export function PacketAssemblyWorkspace() {
  const [caseSummary, setCaseSummary] = useState<CaseSummary | null>(null);
  const [caseIdInput, setCaseIdInput] = useState("");
  const [scenarioCases, setScenarioCases] = useState<CaseSummary[]>([]);
  const [checklist, setChecklist] = useState<ChecklistResponse | null>(null);
  const [uploads, setUploads] = useState<UploadRecord[]>([]);
  const [uploadDrafts, setUploadDrafts] = useState<Record<string, UploadDraft>>({});
  const [replacingCodes, setReplacingCodes] = useState<Set<string>>(new Set());
  const [stateCode, setStateCode] = useState("");
  const [carrier, setCarrier] = useState<"usps" | "private">("usps");
  const [includeSupportingEvidence, setIncludeSupportingEvidence] = useState(true);
  const [paymentMode, setPaymentMode] = useState<PaymentMode>("generate");
  const [paymentOptions, setPaymentOptions] = useState<G1450PaymentOptions | null>(null);
  const [selectedPaymentCodes, setSelectedPaymentCodes] = useState<string[]>([]);
  const [paymentForm, setPaymentForm] = useState<PaymentFormState>(DEFAULT_PAYMENT_FORM);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("card");
  const [bankForm, setBankForm] = useState<G1650BankDetails>(DEFAULT_BANK_FORM);
  const [paymentUploadFile, setPaymentUploadFile] = useState<File | null>(null);
  const [result, setResult] = useState<PacketAssemblyResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const loadCaseArtifacts = useCallback(async (caseId: string) => {
    const [loadedChecklist, loadedUploads, loadedPaymentOptions] = await Promise.all([
      generateChecklist(caseId).catch(() => getChecklist(caseId)),
      listUploads(caseId).catch(() => []),
      getG1450PaymentOptions(caseId).catch(() => null),
    ]);
    return { loadedChecklist, loadedUploads, loadedPaymentOptions };
  }, []);

  const setActiveCase = useCallback(async (nextCase: CaseSummary) => {
    const { loadedChecklist, loadedUploads, loadedPaymentOptions } = await loadCaseArtifacts(nextCase.id);
    const defaults = scenarioDefaults(nextCase.case_name);
    const defaultPaymentCodes =
      loadedPaymentOptions?.options
        .filter((option) => option.is_payable && PACKET_PAYMENT_CODES.has(option.checklist_code))
        .map((option) => option.checklist_code) ?? [];
    setCaseSummary(nextCase);
    setCaseIdInput(nextCase.id);
    setChecklist(loadedChecklist);
    setUploads(loadedUploads);
    setPaymentOptions(loadedPaymentOptions);
    setSelectedPaymentCodes(defaultPaymentCodes);
    setPaymentUploadFile(null);
    setResult(null);
    if (defaults) {
      setStateCode(defaults.stateCode);
      setCarrier(defaults.carrier);
    }
    rememberCaseId(nextCase.id);
    const url = new URL(window.location.href);
    url.searchParams.set("caseId", nextCase.id);
    window.history.replaceState({}, "", url);
    setMessage(null);
  }, [loadCaseArtifacts]);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialState() {
      const searchParams = new URLSearchParams(window.location.search);
      const explicitCaseId = searchParams.get("caseId");
      const savedCaseId = explicitCaseId || getSavedCaseId();
      const cases = await listCases().catch(() => []);
      if (!cancelled) {
        setScenarioCases(uniqueScenarioCases(cases));
      }
      setCaseIdInput(savedCaseId ?? "");
      if (!savedCaseId) {
        setMessage("Paste a case ID to assemble a packet.");
        return;
      }

      try {
        const loadedCase = await getCase(savedCaseId);
        if (cancelled) {
          return;
        }
        await setActiveCase(loadedCase);
      } catch (error) {
        if (!cancelled) {
          setMessage(error instanceof Error ? error.message : "Could not load packet assembly data.");
        }
      }
    }

    void loadInitialState();
    return () => {
      cancelled = true;
    };
  }, [setActiveCase]);

  function loadCaseById(caseId: string) {
    const trimmedCaseId = caseId.trim();
    if (!trimmedCaseId) {
      setMessage("Paste a case ID first.");
      return;
    }
    startTransition(() => {
      getCase(trimmedCaseId)
        .then((loadedCase) => setActiveCase(loadedCase))
        .catch((error) => {
          setMessage(error instanceof Error ? error.message : "Could not load that case ID.");
        });
    });
  }

  function handleCaseSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    loadCaseById(caseIdInput);
  }

  function handleScenarioSelect(caseId: string) {
    const selectedCase = scenarioCases.find((scenario) => scenario.id === caseId);
    if (!selectedCase) {
      return;
    }
    startTransition(() => {
      setActiveCase(selectedCase).catch((error) => {
        setMessage(error instanceof Error ? error.message : "Could not load that scenario.");
      });
    });
  }

  function handleSavedCaseSelect(nextCase: CaseSummary) {
    startTransition(() => {
      setActiveCase(nextCase).catch((error) => {
        setMessage(error instanceof Error ? error.message : "Could not load that case.");
      });
    });
  }

  const uploadsByCode = useMemo(() => {
    const grouped = new Map<string, UploadRecord[]>();
    for (const upload of uploads) {
      for (const code of getSatisfiedChecklistCodes(upload)) {
        const existing = grouped.get(code) ?? [];
        existing.push(upload);
        grouped.set(code, existing);
      }
    }
    return grouped;
  }, [uploads]);

  const groupedItems = useMemo(() => {
    const groups = new Map<string, ChecklistItem[]>();
    for (const item of checklist?.items ?? []) {
      if (item.applicability === "not_applicable" || item.code.startsWith("review_")) {
        continue;
      }
      const key = itemGroupKey(item);
      const existing = groups.get(key) ?? [];
      existing.push(item);
      groups.set(key, existing);
    }
    return Array.from(groups.entries()).map(([key, items]) => ({
      key,
      label: itemGroupLabel(key),
      items: items.sort((left, right) => left.sort_order - right.sort_order),
    }));
  }, [checklist]);

  const activeScenarioCaseId = scenarioCases.some((scenario) => scenario.id === caseSummary?.id)
    ? caseSummary?.id ?? ""
    : "";
  const totalManualUploadItems = groupedItems.reduce(
    (sum, group) =>
      sum + group.items.filter((item) => !GENERATED_ONLY_UPLOAD_CODES.has(item.code) && !NOT_EVIDENCE_CODES.has(item.code)).length,
    0,
  );
  const confirmedPdfUploads = uploads.filter(
    (upload) => upload.upload_status === "confirmed" && upload.mime_type === "application/pdf",
  ).length;
  const paymentUploads = uploadsByCode.get("payment_g1450") ?? [];
  const packetPaymentOptions = useMemo(
    () =>
      paymentOptions?.options.filter(
        (option) => option.is_payable && PACKET_PAYMENT_CODES.has(option.checklist_code),
      ) ?? [],
    [paymentOptions],
  );
  const selectedPaymentTotal = useMemo(() => {
    const selected = new Set(selectedPaymentCodes);
    return packetPaymentOptions.reduce((total, option) => {
      if (!selected.has(option.checklist_code)) {
        return total;
      }
      const amount = Number(option.paper_fee);
      return total + (Number.isNaN(amount) ? 0 : amount);
    }, 0);
  }, [packetPaymentOptions, selectedPaymentCodes]);

  function updateDraft(itemCode: string, patch: Partial<UploadDraft>) {
    setUploadDrafts((current) => ({
      ...current,
      [itemCode]: {
        ...defaultUploadDraft(),
        ...(current[itemCode] ?? {}),
        ...patch,
      },
    }));
  }

  function togglePaymentCode(checklistCode: string) {
    setSelectedPaymentCodes((current) =>
      current.includes(checklistCode)
        ? current.filter((value) => value !== checklistCode)
        : [...current, checklistCode],
    );
  }

  function updatePaymentField(field: PaymentTextField, value: string) {
    setPaymentForm((current) => ({ ...current, [field]: value }));
  }

  function updateBankField(field: keyof G1650BankDetails, value: string) {
    setBankForm((current) => ({ ...current, [field]: value }));
  }

  function updateBillingField(field: BillingField, value: string) {
    setPaymentForm((current) => ({
      ...current,
      billing_address: {
        ...current.billing_address,
        [field]: value,
      },
    }));
  }

  function uploadForItem(item: ChecklistItem) {
    if (!caseSummary) {
      setMessage("Load a case before uploading evidence.");
      return;
    }
    const draft = uploadDrafts[item.code] ?? defaultUploadDraft();
    const file = draft.file;
    if (!file) {
      setMessage(`Choose a PDF for ${item.label}.`);
      return;
    }
    if (fileExceedsUploadLimit(file)) {
      setMessage(`Upload ${file.name} is larger than the ${MAX_PACKET_UPLOAD_SIZE_MB} MB local limit.`);
      return;
    }

    startTransition(() => {
      requestUpload(caseSummary.id, {
        checklist_item_code: item.code,
        original_filename: file.name,
        mime_type: file.type || "application/pdf",
        document_language: draft.documentLanguage,
        has_translation: draft.hasTranslation,
      })
        .then(async (request) => {
          await uploadBinary(request.upload_url, file);
          await confirmUpload(request.upload_id, {
            document_type: item.code,
            document_language: draft.documentLanguage,
            has_translation: draft.hasTranslation,
          });
          const { loadedChecklist, loadedUploads, loadedPaymentOptions } = await loadCaseArtifacts(caseSummary.id);
          setChecklist(loadedChecklist);
          setUploads(loadedUploads);
          setPaymentOptions(loadedPaymentOptions);
          setUploadDrafts((current) => ({
            ...current,
            [item.code]: defaultUploadDraft(),
          }));
          setReplacingCodes((current) => {
            const next = new Set(current);
            next.delete(item.code);
            return next;
          });
          setMessage(`Uploaded ${file.name}.`);
        })
        .catch((error) => {
          setMessage(error instanceof Error ? error.message : "Upload failed.");
        });
    });
  }

  function uploadPaymentG1450() {
    if (!caseSummary) {
      setMessage("Load a case before uploading a G-1450 PDF.");
      return;
    }
    if (!paymentUploadFile) {
      setMessage("Choose a G-1450 PDF first.");
      return;
    }
    const file = paymentUploadFile;
    if (fileExceedsUploadLimit(file)) {
      setMessage(`Upload ${file.name} is larger than the ${MAX_PACKET_UPLOAD_SIZE_MB} MB local limit.`);
      return;
    }

    startTransition(() => {
      requestUpload(caseSummary.id, {
        checklist_item_code: "payment_g1450",
        original_filename: file.name,
        mime_type: file.type || "application/pdf",
        document_language: "english",
        has_translation: false,
      })
        .then(async (request) => {
          await uploadBinary(request.upload_url, file);
          await confirmUpload(request.upload_id, {
            document_type: "payment_g1450",
            document_language: "english",
            has_translation: false,
          });
          const { loadedChecklist, loadedUploads, loadedPaymentOptions } = await loadCaseArtifacts(caseSummary.id);
          setChecklist(loadedChecklist);
          setUploads(loadedUploads);
          setPaymentOptions(loadedPaymentOptions);
          setPaymentUploadFile(null);
          setPaymentMode("existing");
          setMessage(`Uploaded ${file.name}.`);
        })
        .catch((error) => {
          setMessage(error instanceof Error ? error.message : "G-1450 upload failed.");
        });
    });
  }

  function removeUpload(upload: UploadRecord) {
    if (!caseSummary) {
      setMessage("Load a case before removing uploads.");
      return;
    }
    const confirmed = window.confirm(
      `Remove ${upload.original_filename}? This deletes the local uploaded file for this case.`,
    );
    if (!confirmed) {
      return;
    }

    startTransition(() => {
      deleteUpload(upload.id)
        .then(async () => {
          const { loadedChecklist, loadedUploads, loadedPaymentOptions } = await loadCaseArtifacts(caseSummary.id);
          setChecklist(loadedChecklist);
          setUploads(loadedUploads);
          setPaymentOptions(loadedPaymentOptions);
          setResult(null);
          setMessage(`Removed ${upload.original_filename}.`);
        })
        .catch((error) => {
          setMessage(error instanceof Error ? error.message : "Could not remove upload.");
        });
    });
  }

  function generateFullPacket() {
    if (!caseSummary) {
      setMessage("Load a case before generating the packet.");
      return;
    }
    if (!stateCode) {
      setMessage("Choose where the filer lives before generating the packet.");
      return;
    }
    const payingByBank = paymentMethod === "ach";
    const paymentFormName = payingByBank ? "G-1650" : "G-1450";
    const shouldGeneratePayment =
      paymentMode === "generate" && (payingByBank ? bankFormHasUserInput(bankForm) : paymentFormHasUserInput(paymentForm));
    if (shouldGeneratePayment) {
      if (!selectedPaymentCodes.length) {
        setMessage(`Select at least one ${paymentFormName} payment form, clear the payment fields to generate without payment, or use an uploaded payment PDF.`);
        return;
      }
      if (paymentOptions && !(payingByBank ? paymentOptions.g1650_template_exists : paymentOptions.template_exists)) {
        setMessage(`The local ${paymentFormName} template is missing. Upload your own signed ${paymentFormName} PDF instead.`);
        return;
      }
      const fieldIssues = payingByBank ? getG1650PaymentFieldIssues(bankForm) : getG1450PaymentFieldIssues(paymentForm);
      if (fieldIssues.length) {
        setMessage(`Complete ${formatFieldList(fieldIssues)} before generating the packet.`);
        return;
      }
    }

    startTransition(() => {
      generatePacketAssembly(caseSummary.id, {
        state_code: stateCode,
        carrier,
        include_supporting_evidence: includeSupportingEvidence,
        include_generated_forms: true,
        allow_incomplete: true,
        ...(shouldGeneratePayment
          ? {
              ...(payingByBank ? { g1650_payment: bankForm } : { g1450_payment: { ...paymentForm } }),
              g1450_selected_checklist_codes: selectedPaymentCodes,
            }
          : paymentMode === "generate"
            ? { g1450_selected_checklist_codes: selectedPaymentCodes }
            : {}),
      })
        .then((payload) => {
          setResult(payload);
          const paymentSkipped = payload.skipped_documents.some(
            (document) => document.source_type === "generated_payment_form",
          );
          const skippedUploadCount = payload.skipped_documents.filter(
            (document) => document.source_type === "upload",
          ).length;
          setMessage(
            paymentSkipped
              ? `Generated ${includeSupportingEvidence ? "full" : "forms-only"} packet with ${payload.included_documents.length} PDF section(s). Payment PDFs were skipped because no card details or uploaded G-1450 were provided.`
              : skippedUploadCount
                ? `Generated ${includeSupportingEvidence ? "full" : "forms-only"} packet with ${payload.included_documents.length} PDF section(s). ${skippedUploadCount} uploaded file${skippedUploadCount === 1 ? "" : "s"} need attention below.`
                : `Generated ${includeSupportingEvidence ? "full" : "forms-only"} packet with ${payload.included_documents.length} PDF section(s).`,
          );
        })
        .catch((error) => {
          setMessage(error instanceof Error ? error.message : "Could not generate the full packet.");
        });
    });
  }

  const evidenceItemsWithFiles = groupedItems.reduce(
    (sum, group) =>
      sum +
      group.items.filter(
        (item) =>
          !GENERATED_ONLY_UPLOAD_CODES.has(item.code) && !NOT_EVIDENCE_CODES.has(item.code) && (uploadsByCode.get(item.code) ?? []).length,
      ).length,
    0,
  );
  const paymentFormName = paymentMethod === "ach" ? "G-1650" : "G-1450";
  const paymentReady =
    paymentMode === "existing"
      ? paymentUploads.length > 0
      : paymentMethod === "ach"
        ? bankFormHasUserInput(bankForm)
        : paymentFormHasUserInput(paymentForm);

  function segmented<T extends string>(
    label: string,
    options: Array<[T, string]>,
    current: T,
    onSelect: (value: T) => void,
    className?: string,
  ) {
    return (
      <div role="radiogroup" aria-label={label} className={classNames("inline-grid grid-cols-2 gap-1 rounded-lg border border-line-strong bg-paper p-1 text-sm", className)}>
        {options.map(([value, optionLabel]) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={current === value}
            onClick={() => onSelect(value)}
            className={classNames(
              "rounded-md px-3 py-2 font-semibold transition-colors",
              current === value ? "bg-white text-pine-strong shadow-card ring-2 ring-pine" : "text-muted hover:bg-white/60 hover:text-ink",
            )}
          >
            {optionLabel}
          </button>
        ))}
      </div>
    );
  }

  function textInput(
    label: string,
    value: string,
    onChange: (value: string) => void,
    props: { autoComplete?: string; inputMode?: "numeric" | "text" | "email" | "tel"; className?: string } = {},
  ) {
    return (
      <label className={classNames("grid gap-1.5", props.className)}>
        <span className={labelClass}>{label}</span>
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          autoComplete={props.autoComplete}
          inputMode={props.inputMode}
          className={inputClass}
        />
      </label>
    );
  }

  function fileChip(upload: UploadRecord, showStatus: boolean) {
    return (
      <li
        key={upload.id}
        className="inline-flex max-w-full items-center gap-2 rounded-lg border border-line bg-white py-1 pl-3 pr-1 text-xs text-ink"
      >
        <span aria-hidden="true" className="text-pine">
          {"\u25A4"}
        </span>
        <span className="truncate font-medium">{upload.original_filename}</span>
        {showStatus ? <Badge tone="success" className="capitalize">{formatStatus(upload.upload_status)}</Badge> : null}
        <button
          type="button"
          onClick={() => removeUpload(upload)}
          disabled={isPending}
          className="rounded-md px-2 py-1 font-semibold text-muted transition-colors hover:bg-red-50 hover:text-red-800 disabled:opacity-50"
          aria-label={`Remove ${upload.original_filename}`}
        >
          Remove
        </button>
      </li>
    );
  }

  return (
    <AppShell step="packet" caseId={caseSummary?.id} caseName={caseSummary?.case_name} readinessLabel={caseSummary?.readiness_label}>
      <PageHeader
        eyebrow="Step 5"
        title="Print packet"
        description="Attach your evidence, add payment, and choose where you mail it. Lucy assembles one printable PDF in USCIS order."
        actions={
          caseSummary ? (
            <a href="#assemble" className={buttonClass("secondary", "md", "xl:hidden")}>
              Jump to assemble
            </a>
          ) : null
        }
      />

      <StatusMessage message={message} />

      {result ? (
        <section aria-labelledby="result-heading" className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
          <Card className="border-pine/30">
            <SectionHeader
              id="result-heading"
              eyebrow="Packet ready"
              title={`${includeSupportingEvidence ? "Full packet" : "Forms-only packet"} \u00b7 ${result.total_page_count} pages`}
              description="Open the PDF and check every page before printing single-sided on letter paper."
              actions={
                <>
                  <a href={apiUrl(result.manifest_download_url)} target="_blank" rel="noreferrer" className={buttonClass("secondary", "md")}>
                    Manifest
                  </a>
                  <a href={apiUrl(result.download_url)} target="_blank" rel="noreferrer" className={buttonClass("primary", "md")}>
                    Open packet PDF
                  </a>
                </>
              }
            />
            <ol className="mt-4 divide-y divide-line overflow-hidden rounded-lg border border-line">
              {result.included_documents.map((document, index) => (
                <li key={packetDocumentKey(document, index)} className="grid grid-cols-[2rem_minmax(0,1fr)_auto] items-start gap-3 bg-white px-4 py-2.5 text-sm">
                  <span className="text-xs font-semibold tabular-nums text-muted">{index + 1}</span>
                  <span className="min-w-0">
                    <span className="block font-semibold text-ink">{document.label}</span>
                    {document.section ? <span className="block text-xs text-muted">{document.section}</span> : null}
                  </span>
                  <span className="whitespace-nowrap text-xs tabular-nums text-muted">
                    {document.page_count} page{document.page_count === 1 ? "" : "s"}
                  </span>
                </li>
              ))}
            </ol>
            <p className="mt-3 break-all text-xs text-muted">Saved to {result.generated_pdf}</p>
          </Card>

          <Card as="aside" aria-labelledby="mailing-heading" className="h-fit">
            <SectionHeader id="mailing-heading" eyebrow="Mail to" title={result.mailing_recommendation?.lockbox ?? "Mailing address"} level={3} />
            {result.mailing_recommendation ? (
              <>
                <address className="mt-3 rounded-lg border border-line bg-paper px-4 py-3 text-sm not-italic leading-7 text-ink">
                  {result.mailing_recommendation.address_lines.map((line, index) => (
                    <span key={`${index}-${line}`} className="block">
                      {line}
                    </span>
                  ))}
                </address>
                <p className="mt-3 text-xs leading-5 text-muted">
                  USCIS last reviewed this page {result.mailing_recommendation.source_last_reviewed}. Lucy checked it{" "}
                  {result.mailing_recommendation.verified_on}.
                </p>
                <a
                  href={result.mailing_recommendation.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className={buttonClass("ghost", "sm", "mt-2 -ml-3")}
                >
                  Check the USCIS address page {"\u2197"}
                </a>
              </>
            ) : (
              <p className="mt-2 text-sm text-muted">Choose a filer location to see where to mail the packet.</p>
            )}
          </Card>

          {result.warnings.length ? (
            <Notice tone="warning" title="Before you print and mail" className="lg:col-span-2">
              <ul className="mt-1 list-disc space-y-1.5 pl-5">
                {result.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </Notice>
          ) : null}

          {result.skipped_documents.length ? (
            <details className={classNames(cardClass, "group lg:col-span-2")}>
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-xl px-5 py-4 text-sm hover:bg-paper [&::-webkit-details-marker]:hidden">
                <span>
                  <span className="font-semibold text-ink">Files left out of the packet</span>
                  <span className="ml-2 text-muted">{result.skipped_documents.length} with reasons</span>
                </span>
                <span aria-hidden="true" className="text-muted transition-transform group-open:rotate-180">
                  {"\u25BE"}
                </span>
              </summary>
              <ul className="grid gap-2 border-t border-line px-5 py-4">
                {result.skipped_documents.map((document, index) => (
                  <li key={`${packetDocumentKey(document, index)}|${document.reason}`} className="rounded-lg border border-line bg-paper px-4 py-3 text-sm">
                    <p className="font-semibold text-ink">{document.label}</p>
                    <p className="mt-0.5 leading-6 text-muted">{document.reason}</p>
                    {document.filename ? <p className="mt-0.5 break-all text-xs text-muted">{document.filename}</p> : null}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </section>
      ) : null}

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="grid min-w-0 content-start gap-6">
          {!caseSummary ? (
            <Card>
              <SectionHeader title="No case open" description="Open a saved case to attach evidence and assemble its packet." />
              <div className="mt-4 max-w-xl">
                <CaseSelector selectedCaseId={caseIdInput} onSelect={handleSavedCaseSelect} disabled={isPending} label="Saved cases" />
              </div>
            </Card>
          ) : null}

          <Card aria-labelledby="evidence-heading">
            <SectionHeader
              id="evidence-heading"
              eyebrow="Part 1"
              title="Evidence"
              description="Attach a PDF for each item. Lucy generates the USCIS forms itself, so those rows need no upload."
              actions={
                <Badge tone={evidenceItemsWithFiles === totalManualUploadItems && totalManualUploadItems ? "success" : "neutral"}>
                  {evidenceItemsWithFiles} of {totalManualUploadItems} evidence files attached
                </Badge>
              }
            />
            <p className="mt-2 text-xs text-muted">
              PDF only, up to {MAX_PACKET_UPLOAD_SIZE_MB} MB per file. {confirmedPdfUploads} PDF{confirmedPdfUploads === 1 ? "" : "s"} uploaded so far.
            </p>
            {!groupedItems.length ? (
              <Notice tone="warning" className="mt-4" title="No checklist yet">
                Build the checklist on the Review page to see which evidence to attach.
              </Notice>
            ) : null}
            <div className="mt-5 grid gap-3">
              {groupedItems
                .filter((group) => group.items.some((item) => !NOT_EVIDENCE_CODES.has(item.code)))
                .map((group) => {
                  const generatedItems = group.items.filter((item) => GENERATED_ONLY_UPLOAD_CODES.has(item.code));
                  const uploadItems = group.items.filter((item) => !GENERATED_ONLY_UPLOAD_CODES.has(item.code) && !NOT_EVIDENCE_CODES.has(item.code));
                  const evidenceItems = uploadItems.filter((item) => !NOT_EVIDENCE_CODES.has(item.code));
                  const attachedCount = evidenceItems.filter((item) => (uploadsByCode.get(item.code) ?? []).length).length;
                  const missingNames = evidenceItems
                    .filter((item) => !(uploadsByCode.get(item.code) ?? []).length)
                    .map((item) => item.label);
                  const requiredMissing = evidenceItems.filter(
                    (item) => item.applicability === "required" && !(uploadsByCode.get(item.code) ?? []).length,
                  ).length;
                  return (
                    <details
                      key={group.key}
                      open={missingNames.length > 0 || undefined}
                      className={classNames("group/evidence rounded-lg border", requiredMissing ? "border-amber-300" : "border-line")}
                    >
                      <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-2 rounded-lg px-4 py-3 hover:bg-paper [&::-webkit-details-marker]:hidden">
                        <span className="flex items-center gap-2">
                          <span aria-hidden="true" className="text-muted transition-transform group-open/evidence:rotate-90">
                            {"\u25B8"}
                          </span>
                          <span className="text-base font-semibold text-ink">{group.label}</span>
                        </span>
                        <span className="flex items-center gap-2">
                          {requiredMissing ? <Badge tone="warning">{requiredMissing} required missing</Badge> : null}
                          <span
                            className={classNames(
                              "text-xs font-semibold tabular-nums",
                              requiredMissing ? "text-amber-800" : "text-muted",
                            )}
                          >
                            {evidenceItems.length
                              ? `${attachedCount} of ${evidenceItems.length} attached`
                              : uploadItems.length
                                ? "Added in the Payment section"
                                : "Generated by Lucy"}
                          </span>
                        </span>
                      </summary>
                      {missingNames.length ? (
                        <p className="px-4 pb-3 pl-10 text-xs leading-5 text-muted group-open/evidence:hidden">
                          No file yet: {missingNames.join(", ")}
                        </p>
                      ) : null}
                      <div className="border-t border-line px-4">
                        {generatedItems.length ? (
                          <div className="flex flex-wrap items-start gap-x-3 gap-y-2 py-3 text-sm">
                            <Badge tone="success">Generated by Lucy</Badge>
                            <span className="min-w-0 flex-1 text-muted">
                              {generatedItems.map((item) => item.label).join(", ")} {generatedItems.length === 1 ? "is" : "are"} built from your
                              saved answers.
                            </span>
                            {generatedItems.some((item) => (uploadsByCode.get(item.code) ?? []).length) ? (
                              <div className="w-full">
                                <p className="text-xs text-muted">Older uploaded copies are skipped. Remove them if you no longer need them.</p>
                                <ul className="mt-1.5 flex flex-wrap gap-2">
                                  {Array.from(
                                    new Map(
                                      generatedItems.flatMap((item) => (uploadsByCode.get(item.code) ?? []).map((upload) => [upload.id, upload] as const)),
                                    ).values(),
                                  ).map((upload) => fileChip(upload, false))}
                                </ul>
                              </div>
                            ) : null}
                          </div>
                        ) : null}
                        <ul className="divide-y divide-line border-line [&:not(:first-child)]:border-t">
                          {uploadItems.map((item) => {
                            const itemUploads = uploadsByCode.get(item.code) ?? [];
                            const draft = uploadDrafts[item.code] ?? defaultUploadDraft();
                            const fileInputId = `upload-${item.code}`;
                            return (
                              <li key={item.id} className="grid gap-3 py-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)] lg:gap-6">
                                <div className="min-w-0">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <h4 className="font-semibold text-ink">{item.label}</h4>
                                    <Badge tone={item.applicability === "required" ? "strong" : "neutral"} className="capitalize">
                                      {formatStatus(item.applicability)}
                                    </Badge>
                                    {itemUploads.length ? <Badge tone="success">Attached</Badge> : null}
                                  </div>
                                  <p className="mt-1 text-sm leading-6 text-muted">{item.what_to_save_now || item.description}</p>
                                  {itemUploads.length ? (
                                    <ul className="mt-2 flex flex-wrap gap-2">{itemUploads.map((upload) => fileChip(upload, true))}</ul>
                                  ) : null}
                                </div>
                                {item.code === "payment_g1450" ? (
                                  <p className="self-center text-sm leading-6 text-muted">
                                    Add payment in the{" "}
                                    <a href="#payment-heading" className="font-semibold text-pine underline-offset-4 hover:underline">
                                      Payment
                                    </a>{" "}
                                    section below.
                                  </p>
                                ) : itemUploads.length && !replacingCodes.has(item.code) ? (
                                  <div className="self-center">
                                    <button
                                      type="button"
                                      onClick={() => setReplacingCodes((current) => new Set(current).add(item.code))}
                                      className={buttonClass("secondary", "sm")}
                                    >
                                      Add or replace a file
                                    </button>
                                  </div>
                                ) : (
                                  <div className="grid content-start gap-2">
                                    <div className="flex items-center gap-2">
                                      <input
                                        id={fileInputId}
                                        type="file"
                                        accept="application/pdf,.pdf"
                                        onChange={(event) => updateDraft(item.code, { file: event.target.files?.[0] ?? null })}
                                        className="peer sr-only"
                                      />
                                      <label
                                        htmlFor={fileInputId}
                                        className={buttonClass(
                                          "secondary",
                                          "sm",
                                          "min-w-0 flex-1 cursor-pointer justify-start peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-pine",
                                        )}
                                      >
                                        <span className="truncate">
                                          {draft.file ? draft.file.name : itemUploads.length ? "Replace or add a PDF" : "Choose a PDF"}
                                        </span>
                                        <span className="sr-only"> for {item.label}</span>
                                      </label>
                                      <button
                                        type="button"
                                        onClick={() => uploadForItem(item)}
                                        disabled={isPending || !caseSummary || !draft.file}
                                        className={buttonClass("primary", "sm", "shrink-0")}
                                      >
                                        Upload
                                      </button>
                                    </div>
                                    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                                      <label className="flex items-center gap-2 text-xs font-medium text-ink">
                                        Language
                                        <select
                                          value={draft.documentLanguage}
                                          onChange={(event) => updateDraft(item.code, { documentLanguage: event.target.value })}
                                          className="h-8 rounded-md border border-line-strong bg-white px-2 text-xs"
                                        >
                                          <option value="english">English</option>
                                          <option value="spanish">Spanish</option>
                                          <option value="other">Other</option>
                                          <option value="unknown">Unknown</option>
                                        </select>
                                      </label>
                                      <label className="flex items-center gap-2 text-xs font-medium text-ink">
                                        <input
                                          type="checkbox"
                                          checked={draft.hasTranslation}
                                          onChange={(event) => updateDraft(item.code, { hasTranslation: event.target.checked })}
                                          className="h-4 w-4"
                                        />
                                        Includes certified English translation
                                      </label>
                                    </div>
                                  </div>
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    </details>
                  );
                })}
            </div>
          </Card>

          <Card aria-labelledby="payment-heading">
            <SectionHeader
              id="payment-heading"
              eyebrow="Part 2"
              title="Payment"
              description={paymentOptions?.payment_note ? <LinkedText text={paymentOptions.payment_note} /> : null}
              actions={segmented<PaymentMode>(
                "Payment source",
                [
                  ["generate", "Fill in for me"],
                  ["existing", "I have a signed PDF"],
                ],
                paymentMode,
                setPaymentMode,
              )}
            />
            {paymentOptions && !paymentOptions.template_exists ? (
              <Notice tone="warning" className="mt-4">
                Local template missing at {paymentOptions.template_pdf}
              </Notice>
            ) : null}

            {paymentMode === "generate" ? (
              <div className="mt-5 grid gap-5">
                <fieldset>
                  <legend className={labelClass}>Fees to pay</legend>
                  <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                    {packetPaymentOptions.length ? (
                      packetPaymentOptions.map((option) => {
                        const checked = selectedPaymentCodes.includes(option.checklist_code);
                        return (
                          <label
                            key={option.checklist_code}
                            className={classNames(
                              "flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm transition-colors",
                              checked ? "border-pine bg-pine-soft" : "border-line bg-white hover:bg-paper",
                            )}
                          >
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => togglePaymentCode(option.checklist_code)}
                              className="mt-0.5 h-4 w-4"
                            />
                            <span>
                              <span className="block font-semibold text-ink">{option.form_code}</span>
                              <span className="block text-base font-semibold tabular-nums text-ink">{formatCurrency(option.paper_fee)}</span>
                              <span className="block text-xs text-muted">Fee verified {option.verified_on}</span>
                            </span>
                          </label>
                        );
                      })
                    ) : (
                      <p className="rounded-lg border border-line bg-paper p-3 text-sm text-muted sm:col-span-2 lg:col-span-4">
                        No payable forms are in this packet.
                      </p>
                    )}
                  </div>
                </fieldset>

                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  {segmented<PaymentMethod>(
                    "Payment method",
                    [
                      ["card", "Card (G-1450)"],
                      ["ach", "U.S. bank account (G-1650)"],
                    ],
                    paymentMethod,
                    setPaymentMethod,
                    "w-full sm:w-auto",
                  )}
                  <p className="text-sm text-muted">
                    Total <span className="text-lg font-semibold tabular-nums text-ink">{formatCurrency(selectedPaymentTotal.toFixed(2))}</span>
                  </p>
                </div>

                {paymentMethod === "card" ? (
                  <fieldset className="grid gap-4">
                    <legend className="sr-only">Card and billing details</legend>
                    <div className="grid gap-4 md:grid-cols-2">
                      {textInput("Cardholder name", paymentForm.cardholder_name, (value) => updatePaymentField("cardholder_name", value), {
                        autoComplete: "cc-name",
                      })}
                      <label className="grid gap-1.5">
                        <span className={labelClass}>Card type</span>
                        <select
                          value={paymentForm.credit_card_type}
                          onChange={(event) => updatePaymentField("credit_card_type", event.target.value)}
                          className={inputClass}
                        >
                          {CARD_TYPES.map((type) => (
                            <option key={type} value={type}>
                              {type}
                            </option>
                          ))}
                        </select>
                      </label>
                      {textInput("Card number", paymentForm.credit_card_number, (value) => updatePaymentField("credit_card_number", value), {
                        autoComplete: "cc-number",
                        inputMode: "numeric",
                      })}
                      <div className="grid grid-cols-3 gap-3">
                        {textInput("Month", paymentForm.expiration_month, (value) => updatePaymentField("expiration_month", value), {
                          autoComplete: "cc-exp-month",
                          inputMode: "numeric",
                        })}
                        {textInput("Year", paymentForm.expiration_year, (value) => updatePaymentField("expiration_year", value), {
                          autoComplete: "cc-exp-year",
                          inputMode: "numeric",
                        })}
                        {textInput("CVV", paymentForm.security_code, (value) => updatePaymentField("security_code", value), {
                          autoComplete: "cc-csc",
                          inputMode: "numeric",
                        })}
                      </div>
                      {textInput("Daytime phone", paymentForm.daytime_phone_number, (value) => updatePaymentField("daytime_phone_number", value), {
                        autoComplete: "tel",
                        inputMode: "tel",
                      })}
                      {textInput("Email", paymentForm.email, (value) => updatePaymentField("email", value), {
                        autoComplete: "email",
                        inputMode: "email",
                      })}
                    </div>
                    <p className="pt-2 text-sm font-semibold text-ink">Billing address</p>
                    <div className="grid gap-4 md:grid-cols-2">
                      {textInput("Street address", paymentForm.billing_address.street_1, (value) => updateBillingField("street_1", value), {
                        autoComplete: "billing address-line1",
                      })}
                      {textInput("Apt, suite, or floor", paymentForm.billing_address.street_2, (value) => updateBillingField("street_2", value), {
                        autoComplete: "billing address-line2",
                      })}
                      {textInput("City", paymentForm.billing_address.city, (value) => updateBillingField("city", value), {
                        autoComplete: "billing address-level2",
                      })}
                      <div className="grid grid-cols-[minmax(0,0.7fr)_minmax(0,1fr)] gap-3">
                        {textInput("State", paymentForm.billing_address.state, (value) => updateBillingField("state", value), {
                          autoComplete: "billing address-level1",
                        })}
                        {textInput("ZIP code", paymentForm.billing_address.postal_code, (value) => updateBillingField("postal_code", value), {
                          autoComplete: "billing postal-code",
                          inputMode: "numeric",
                        })}
                      </div>
                    </div>
                    <p className={hintClass}>
                      These details only fill in Form G-1450 on this computer. Lucy does not charge your card. Leave them blank to
                      assemble the packet without a payment form.
                    </p>
                  </fieldset>
                ) : (
                  <fieldset className="grid gap-4">
                    <legend className="sr-only">Bank account details</legend>
                    <Notice tone="info">
                      The account must be with a U.S. bank, and the account holder signs each printed Form G-1650. Ask the bank to
                      remove any ACH debit block for the Department of Homeland Security. Lucy keeps these details out of case records,
                      but they are printed on the generated PDFs in local storage.
                    </Notice>
                    <div className="grid gap-4 md:grid-cols-2">
                      <label className="grid gap-1.5">
                        <span className={labelClass}>Account ownership</span>
                        <select
                          value={bankForm.account_ownership}
                          onChange={(event) => updateBankField("account_ownership", event.target.value)}
                          className={inputClass}
                        >
                          <option value="personal">Personal</option>
                          <option value="business">Business</option>
                        </select>
                      </label>
                      <label className="grid gap-1.5">
                        <span className={labelClass}>Account type</span>
                        <select
                          value={bankForm.account_type}
                          onChange={(event) => updateBankField("account_type", event.target.value)}
                          className={inputClass}
                        >
                          <option value="checking">Checking</option>
                          <option value="savings">Savings</option>
                        </select>
                      </label>
                      {textInput("Account holder name, as on the account", bankForm.account_holder_name, (value) => updateBankField("account_holder_name", value), {
                        autoComplete: "off",
                      })}
                      {bankForm.account_ownership === "business"
                        ? textInput("Business name", bankForm.business_name, (value) => updateBankField("business_name", value), { autoComplete: "off" })
                        : null}
                      {textInput("Bank name", bankForm.bank_name, (value) => updateBankField("bank_name", value), { autoComplete: "off" })}
                      {textInput("Routing number", bankForm.routing_number, (value) => updateBankField("routing_number", value), {
                        autoComplete: "off",
                        inputMode: "numeric",
                      })}
                      {textInput("Account number", bankForm.account_number, (value) => updateBankField("account_number", value), {
                        autoComplete: "off",
                        inputMode: "numeric",
                      })}
                    </div>
                  </fieldset>
                )}
              </div>
            ) : (
              <div className="mt-5 grid gap-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
                <div className="min-w-0">
                  <label className="grid gap-1.5">
                    <span className={labelClass}>Signed Form G-1450 or G-1650 (PDF)</span>
                    <input
                      type="file"
                      accept="application/pdf,.pdf"
                      onChange={(event) => setPaymentUploadFile(event.target.files?.[0] ?? null)}
                      className="w-full min-w-0 rounded-lg border border-line-strong bg-white p-2 text-sm text-muted"
                    />
                  </label>
                  <p className="mt-1.5 text-xs text-muted">Up to {MAX_PACKET_UPLOAD_SIZE_MB} MB.</p>
                  {paymentUploads.length ? <ul className="mt-3 flex flex-wrap gap-2">{paymentUploads.map((upload) => fileChip(upload, false))}</ul> : null}
                </div>
                <button
                  type="button"
                  onClick={uploadPaymentG1450}
                  disabled={isPending || !caseSummary || !paymentUploadFile}
                  className={buttonClass("primary", "md")}
                >
                  Upload payment PDF
                </button>
              </div>
            )}
          </Card>
        </div>

        <aside id="assemble" aria-labelledby="assemble-heading" className="scroll-mt-24 xl:sticky xl:top-20 xl:h-fit">
          <Card className="border-pine/30">
            <SectionHeader
              id="assemble-heading"
              eyebrow="Last step"
              title="Mail and assemble"
              description="Lucy uses where the filer lives to pick the USCIS lockbox."
              level={2}
            />
            <div className="mt-4 grid gap-4">
              <label className="grid gap-1.5">
                <span className={labelClass}>Where the filer lives</span>
                <select id="filer-state" value={stateCode} onChange={(event) => setStateCode(event.target.value)} className={inputClass}>
                  <option value="">Choose a state or territory</option>
                  {US_LOCATIONS.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="grid gap-1.5">
                <span className={labelClass} id="carrier-label">
                  Delivery method
                </span>
                {segmented<"usps" | "private">(
                  "Delivery method",
                  [
                    ["usps", "USPS"],
                    ["private", "FedEx, UPS, DHL"],
                  ],
                  carrier,
                  setCarrier,
                  "w-full",
                )}
              </div>
              <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-line bg-paper p-3 text-sm">
                <input
                  type="checkbox"
                  checked={includeSupportingEvidence}
                  onChange={(event) => setIncludeSupportingEvidence(event.target.checked)}
                  className="mt-0.5 h-4 w-4"
                />
                <span>
                  <span className="block font-semibold text-ink">Include evidence PDFs</span>
                  <span className="block text-xs leading-5 text-muted">Turn off to print only the forms and payment pages.</span>
                </span>
              </label>
              <ul className="divide-y divide-line rounded-lg border border-line text-sm" aria-label="Before you assemble">
                {[
                  {
                    label: "Filer's state",
                    value: stateCode ? US_LOCATIONS.find(([value]) => value === stateCode)?.[1] ?? stateCode : "Not chosen",
                    ok: Boolean(stateCode),
                    href: "#filer-state",
                  },
                  { label: "Delivery", value: carrier === "usps" ? "USPS" : "FedEx, UPS, or DHL", ok: true, href: null },
                  {
                    label: "Payment",
                    value: paymentReady
                      ? paymentMode === "existing"
                        ? "Uploaded PDF"
                        : `${paymentFormName}, ${formatCurrency(selectedPaymentTotal.toFixed(2))}`
                      : "Not added",
                    ok: paymentReady,
                    href: "#payment-heading",
                  },
                  {
                    label: "Evidence",
                    value: `${evidenceItemsWithFiles} of ${totalManualUploadItems} attached`,
                    ok: evidenceItemsWithFiles === totalManualUploadItems,
                    href: "#evidence-heading",
                  },
                ].map((row) => (
                  <li key={row.label} className="flex items-center justify-between gap-3 px-3 py-2">
                    <span className="flex items-center gap-2 text-muted">
                      <span
                        aria-hidden="true"
                        className={cx(
                          "flex h-4 w-4 items-center justify-center rounded-full text-[0.625rem] font-bold",
                          row.ok ? "bg-pine text-white" : "border border-amber-500 text-amber-700",
                        )}
                      >
                        {row.ok ? "\u2713" : "!"}
                      </span>
                      {row.label}
                    </span>
                    {row.href && !row.ok ? (
                      <a href={row.href} className="text-right font-semibold text-amber-900 underline-offset-4 hover:underline">
                        {row.value}
                      </a>
                    ) : (
                      <span className="text-right font-semibold text-ink">{row.value}</span>
                    )}
                  </li>
                ))}
              </ul>
              <button
                type="button"
                onClick={generateFullPacket}
                disabled={!caseSummary || !stateCode || isPending}
                className={buttonClass("primary", "lg", "w-full")}
              >
                {isPending ? (
                  <>
                    <Spinner /> Working...
                  </>
                ) : !stateCode ? (
                  "Choose the filer's state first"
                ) : includeSupportingEvidence ? (
                  "Assemble full packet"
                ) : (
                  "Assemble forms only"
                )}
              </button>
              {stateCode && caseSummary && !paymentReady ? (
                <p className="text-xs leading-5 text-amber-900">
                  No payment is added yet, so the packet will have no payment form. Add it in Payment, or include your own signed
                  payment form before mailing.
                </p>
              ) : null}
            </div>
          </Card>
        </aside>
      </div>

      {caseSummary ? (
        <div className="sticky bottom-0 z-20 -mx-4 flex items-center justify-between gap-3 border-t border-line bg-white/95 px-4 py-3 backdrop-blur xl:hidden">
          <p className="min-w-0 text-xs leading-5 text-muted">
            <span className="font-semibold tabular-nums text-ink">
              {evidenceItemsWithFiles} of {totalManualUploadItems}
            </span>{" "}
            files attached
            <span aria-hidden="true">{" \u00b7 "}</span>
            {stateCode ? US_LOCATIONS.find(([value]) => value === stateCode)?.[1] : "No state chosen"}
          </p>
          <a href="#assemble" className={buttonClass("primary", "sm", "shrink-0")}>
            Assemble
          </a>
        </div>
      ) : null}

      <form onSubmit={handleCaseSearch} className="border-t border-line pt-4">
        <details className="group">
          <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-sm font-semibold text-muted hover:text-ink [&::-webkit-details-marker]:hidden">
            Test scenarios and case ID
            <span aria-hidden="true" className="transition-transform group-open:rotate-180">
              {"\u25BE"}
            </span>
          </summary>
          <div className="mt-3 grid gap-4 rounded-lg border border-line bg-white p-4 md:grid-cols-2">
            <label className="grid gap-1.5">
              <span className={labelClass}>Test scenario</span>
              <select
                value={activeScenarioCaseId}
                onChange={(event) => handleScenarioSelect(event.target.value)}
                disabled={!scenarioCases.length || isPending}
                className={inputClass}
              >
                <option value="">{scenarioCases.length ? "Choose a seeded scenario" : "Run npm run seed:packet-scenarios"}</option>
                {scenarioCases.map((scenario) => {
                  const defaults = scenarioDefaults(scenario.case_name);
                  const carrierLabel = defaults?.carrier === "private" ? "Private carrier" : "USPS";
                  return (
                    <option key={scenario.id} value={scenario.id}>
                      {`${scenarioShortLabel(scenario.case_name)} \u00b7 ${defaults?.stateCode ?? "?"} \u00b7 ${carrierLabel}`}
                    </option>
                  );
                })}
              </select>
            </label>
            <div className="grid gap-1.5">
              <label htmlFor="case-id-input" className={labelClass}>
                Case ID
              </label>
              <div className="flex gap-2">
                <input
                  id="case-id-input"
                  value={caseIdInput}
                  onChange={(event) => setCaseIdInput(event.target.value)}
                  placeholder="Paste a case ID"
                  className={inputClass}
                />
                <button type="submit" disabled={isPending} className={buttonClass("secondary", "md", "shrink-0")}>
                  Open
                </button>
              </div>
            </div>
          </div>
        </details>
      </form>
    </AppShell>
  );
}

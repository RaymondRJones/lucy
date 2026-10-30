"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState, useTransition } from "react";

import { CaseSelector } from "@/components/case-selector";
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
};

const CARD_TYPES = ["Visa", "Mastercard", "American Express", "Discover"];
const PACKET_PAYMENT_CODES = new Set(["form_i485", "form_i765", "form_i131"]);
const GENERATED_ONLY_UPLOAD_CODES = new Set(["form_g1145", "form_i485", "form_i864", "form_i765", "form_i131"]);
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

function getSatisfiedChecklistCodes(upload: UploadRecord) {
  const extraCodes = Array.isArray(upload.extracted_fields.satisfies_checklist_codes)
    ? upload.extracted_fields.satisfies_checklist_codes
        .filter((value): value is string => typeof value === "string" && value.length > 0)
    : [];
  return Array.from(
    new Set([...(upload.checklist_item_code ? [upload.checklist_item_code] : []), ...extraCodes]),
  );
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

export function PacketAssemblyWorkspace() {
  const [caseSummary, setCaseSummary] = useState<CaseSummary | null>(null);
  const [caseIdInput, setCaseIdInput] = useState("");
  const [scenarioCases, setScenarioCases] = useState<CaseSummary[]>([]);
  const [checklist, setChecklist] = useState<ChecklistResponse | null>(null);
  const [uploads, setUploads] = useState<UploadRecord[]>([]);
  const [uploadDrafts, setUploadDrafts] = useState<Record<string, UploadDraft>>({});
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
  const [message, setMessage] = useState("Loading the current case.");
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
    setMessage(`Loaded ${nextCase.case_name}. Upload PDFs by item, then generate the full packet.`);
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

  const caseQuery = caseSummary ? `?caseId=${encodeURIComponent(caseSummary.id)}` : "";
  const activeScenarioCaseId = scenarioCases.some((scenario) => scenario.id === caseSummary?.id)
    ? caseSummary?.id ?? ""
    : "";
  const totalUploadableItems = groupedItems.reduce((sum, group) => sum + group.items.length, 0);
  const totalManualUploadItems = groupedItems.reduce(
    (sum, group) => sum + group.items.filter((item) => !GENERATED_ONLY_UPLOAD_CODES.has(item.code)).length,
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

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 py-6 text-ink md:px-8 md:py-8">
      <nav className="flex flex-col gap-3 border-b border-ink/10 pb-5 md:flex-row md:items-center md:justify-between">
        <Link href="/" className="font-display text-2xl">
          Lucy
        </Link>
        <div className="flex flex-wrap gap-2">
          <Link className="rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm font-semibold" href={`/prescreen${caseQuery}`}>
            Prescreen
          </Link>
          <Link className="rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm font-semibold" href={`/manage-tasks${caseQuery}`}>
            Manage tasks
          </Link>
        </div>
      </nav>

      <section className="grid gap-5 border-b border-ink/10 py-6 lg:grid-cols-[1fr_auto] lg:items-end">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-pine">Generate full packet</p>
          <h1 className="mt-3 font-display text-4xl leading-tight md:text-5xl">
            Consolidate forms and PDF evidence into one printable file.
          </h1>
        </div>
        <div className="rounded-lg border border-ink/10 bg-white px-4 py-3 text-sm">
          <p className="text-xs uppercase tracking-[0.16em] text-ink/50">Selected case</p>
          <p className="mt-1 font-semibold">{caseSummary?.case_name ?? "None loaded"}</p>
          {caseSummary ? <p className="mt-1 max-w-80 break-all text-xs text-ink/55">{caseSummary.id}</p> : null}
        </div>
      </section>

      {message ? <p className="rounded-lg border border-ink/10 bg-white p-3 text-sm text-ink/75">{message}</p> : null}

      <section className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <form className="rounded-lg border border-ink/10 bg-white p-5" onSubmit={handleCaseSearch}>
          <h2 className="text-lg font-semibold">Case</h2>
          <div className="mt-4">
            <CaseSelector
              selectedCaseId={caseSummary?.id ?? caseIdInput}
              onSelect={handleSavedCaseSelect}
              disabled={isPending}
              label="Choose saved case"
            />
          </div>
          <label className="mt-4 block">
            <span className="text-sm font-semibold">Test scenarios</span>
            <select
              value={activeScenarioCaseId}
              onChange={(event) => handleScenarioSelect(event.target.value)}
              disabled={!scenarioCases.length || isPending}
              className="mt-2 h-11 w-full rounded-lg border border-ink/15 bg-white px-3 text-sm disabled:opacity-55"
            >
              <option value="">
                {scenarioCases.length ? "Choose seeded scenario" : "Run npm run seed:packet-scenarios"}
              </option>
              {scenarioCases.map((scenario) => {
                const defaults = scenarioDefaults(scenario.case_name);
                const carrierLabel = defaults?.carrier === "private" ? "Private carrier" : "USPS";
                return (
                  <option key={scenario.id} value={scenario.id}>
                    {scenarioShortLabel(scenario.case_name)} · {defaults?.stateCode ?? "?"} · {carrierLabel}
                  </option>
                );
              })}
            </select>
          </label>
          <div className="mt-4 flex flex-col gap-2 sm:flex-row">
            <input
              value={caseIdInput}
              onChange={(event) => setCaseIdInput(event.target.value)}
              placeholder="Paste case ID"
              className="min-h-11 flex-1 rounded-lg border border-ink/15 bg-white px-3 text-sm text-ink"
            />
            <button
              type="submit"
              disabled={isPending}
              className="rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-white disabled:opacity-55"
            >
              Use this case
            </button>
          </div>
        </form>

        <div className="grid grid-cols-2 gap-3 rounded-lg border border-ink/10 bg-white p-5 text-sm">
          <div>
            <p className="text-xs uppercase tracking-[0.16em] text-ink/45">Upload buckets</p>
            <p className="mt-1 font-display text-3xl">{totalManualUploadItems}</p>
            {totalManualUploadItems !== totalUploadableItems ? (
              <p className="mt-1 text-xs text-ink/55">Generated forms are handled by Lucy.</p>
            ) : null}
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.16em] text-ink/45">PDF uploads</p>
            <p className="mt-1 font-display text-3xl">{confirmedPdfUploads}</p>
          </div>
        </div>
      </section>

      <section className="grid gap-4 rounded-lg border border-ink/10 bg-white p-5">
        <div className="flex flex-col gap-3 border-b border-ink/10 pb-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.16em] text-pine">Payment</p>
            <h2 className="mt-1 text-xl font-semibold">Form G-1450 or G-1650</h2>
            {paymentOptions?.payment_note ? (
              <p className="mt-2 max-w-2xl text-sm leading-6 text-ink/65">{paymentOptions.payment_note}</p>
            ) : null}
            {paymentOptions && !paymentOptions.template_exists ? (
              <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950">
                Local template missing at {paymentOptions.template_pdf}
              </p>
            ) : null}
          </div>
          <div className="grid grid-cols-2 rounded-lg border border-ink/15 bg-paper p-1 text-sm">
            {[
              ["generate", "Generate"],
              ["existing", "Use saved/uploaded"],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setPaymentMode(value as PaymentMode)}
                className={classNames(
                  "rounded-md px-3 py-2 font-semibold",
                  paymentMode === value ? "bg-ink text-white" : "text-ink/65",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {paymentMode === "generate" ? (
          <div className="grid gap-5">
            <div className="grid gap-3 md:grid-cols-3">
              {packetPaymentOptions.length ? (
                packetPaymentOptions.map((option) => {
                  const checked = selectedPaymentCodes.includes(option.checklist_code);
                  return (
                    <label
                      key={option.checklist_code}
                      className="grid gap-2 rounded-lg border border-ink/10 bg-paper/55 p-3 text-sm"
                    >
                      <span className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => togglePaymentCode(option.checklist_code)}
                          className="mt-1 h-4 w-4 rounded border-ink/30 text-pine"
                        />
                        <span>
                          <span className="block font-semibold">
                            {option.form_code} {formatCurrency(option.paper_fee)}
                          </span>
                          <span className="mt-1 block text-xs leading-5 text-ink/55">
                            Verified {option.verified_on}
                          </span>
                        </span>
                      </span>
                    </label>
                  );
                })
              ) : (
                <p className="rounded-lg border border-ink/10 bg-paper/55 p-3 text-sm text-ink/65 md:col-span-3">
                  No payable I-485 packet options are available for this case.
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 rounded-lg border border-ink/15 bg-paper p-1 text-sm sm:max-w-md">
              {[
                ["card", "Card (G-1450)"],
                ["ach", "U.S. bank account (G-1650)"],
              ].map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setPaymentMethod(value as PaymentMethod)}
                  className={classNames(
                    "rounded-md px-3 py-2 font-semibold",
                    paymentMethod === value ? "bg-ink text-white" : "text-ink/65",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>

            {paymentMethod === "card" ? (
              <div className="grid gap-4 rounded-lg border border-ink/10 bg-paper/45 p-4">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <h3 className="font-semibold">Card and billing details</h3>
                  <p className="text-sm font-semibold text-pine">
                    {formatCurrency(selectedPaymentTotal.toFixed(2))}
                  </p>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="grid gap-2 text-sm font-medium">
                    Cardholder name
                    <input
                      value={paymentForm.cardholder_name}
                      onChange={(event) => updatePaymentField("cardholder_name", event.target.value)}
                      autoComplete="cc-name"
                      className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                    />
                  </label>
                  <label className="grid gap-2 text-sm font-medium">
                    Card type
                    <select
                      value={paymentForm.credit_card_type}
                      onChange={(event) => updatePaymentField("credit_card_type", event.target.value)}
                      className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                    >
                      {CARD_TYPES.map((type) => (
                        <option key={type} value={type}>
                          {type}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="grid gap-2 text-sm font-medium">
                    Card number
                    <input
                      value={paymentForm.credit_card_number}
                      onChange={(event) => updatePaymentField("credit_card_number", event.target.value)}
                      inputMode="numeric"
                      autoComplete="cc-number"
                      className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                    />
                  </label>
                  <div className="grid gap-4 sm:grid-cols-3">
                    <label className="grid gap-2 text-sm font-medium">
                      Month
                      <input
                        value={paymentForm.expiration_month}
                        onChange={(event) => updatePaymentField("expiration_month", event.target.value)}
                        inputMode="numeric"
                        autoComplete="cc-exp-month"
                        className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                      />
                    </label>
                    <label className="grid gap-2 text-sm font-medium">
                      Year
                      <input
                        value={paymentForm.expiration_year}
                        onChange={(event) => updatePaymentField("expiration_year", event.target.value)}
                        inputMode="numeric"
                        autoComplete="cc-exp-year"
                        className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                      />
                    </label>
                    <label className="grid gap-2 text-sm font-medium">
                      CVV
                      <input
                        value={paymentForm.security_code}
                        onChange={(event) => updatePaymentField("security_code", event.target.value)}
                        inputMode="numeric"
                        autoComplete="cc-csc"
                        className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                      />
                    </label>
                  </div>
                  <label className="grid gap-2 text-sm font-medium">
                    Phone
                    <input
                      value={paymentForm.daytime_phone_number}
                      onChange={(event) => updatePaymentField("daytime_phone_number", event.target.value)}
                      autoComplete="tel"
                      className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                    />
                  </label>
                  <label className="grid gap-2 text-sm font-medium">
                    Email
                    <input
                      value={paymentForm.email}
                      onChange={(event) => updatePaymentField("email", event.target.value)}
                      autoComplete="email"
                      className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                    />
                  </label>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="grid gap-2 text-sm font-medium">
                    Street address
                    <input
                      value={paymentForm.billing_address.street_1}
                      onChange={(event) => updateBillingField("street_1", event.target.value)}
                      autoComplete="billing street-address"
                      className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                    />
                  </label>
                  <label className="grid gap-2 text-sm font-medium">
                    Apt, suite, or floor
                    <input
                      value={paymentForm.billing_address.street_2}
                      onChange={(event) => updateBillingField("street_2", event.target.value)}
                      className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                    />
                  </label>
                  <label className="grid gap-2 text-sm font-medium">
                    City
                    <input
                      value={paymentForm.billing_address.city}
                      onChange={(event) => updateBillingField("city", event.target.value)}
                      autoComplete="billing address-level2"
                      className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                    />
                  </label>
                  <div className="grid gap-4 sm:grid-cols-[0.7fr_1fr]">
                    <label className="grid gap-2 text-sm font-medium">
                      State
                      <input
                        value={paymentForm.billing_address.state}
                        onChange={(event) => updateBillingField("state", event.target.value)}
                        autoComplete="billing address-level1"
                        className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                      />
                    </label>
                    <label className="grid gap-2 text-sm font-medium">
                      ZIP code
                      <input
                        value={paymentForm.billing_address.postal_code}
                        onChange={(event) => updateBillingField("postal_code", event.target.value)}
                        autoComplete="billing postal-code"
                        className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                      />
                    </label>
                  </div>
                </div>
              </div>
            ) : (
              <div className="grid gap-4 rounded-lg border border-ink/10 bg-paper/45 p-4">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <h3 className="font-semibold">Bank account details</h3>
                  <p className="text-sm font-semibold text-pine">
                    {formatCurrency(selectedPaymentTotal.toFixed(2))}
                  </p>
                </div>
                <p className="text-sm leading-6 text-ink/65">
                  The account must be with a U.S. bank, and the account holder signs each printed Form G-1650. Ask the
                  bank to remove any ACH debit block for the Department of Homeland Security. Lucy keeps these details
                  out of case records, but they are printed on the generated PDFs in local storage.
                </p>
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="grid gap-2 text-sm font-medium">
                    Account ownership
                    <select
                      value={bankForm.account_ownership}
                      onChange={(event) => updateBankField("account_ownership", event.target.value)}
                      className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                    >
                      <option value="personal">Personal</option>
                      <option value="business">Business</option>
                    </select>
                  </label>
                  <label className="grid gap-2 text-sm font-medium">
                    Account type
                    <select
                      value={bankForm.account_type}
                      onChange={(event) => updateBankField("account_type", event.target.value)}
                      className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                    >
                      <option value="checking">Checking</option>
                      <option value="savings">Savings</option>
                    </select>
                  </label>
                  <label className="grid gap-2 text-sm font-medium">
                    Account holder name, as on the account
                    <input
                      value={bankForm.account_holder_name}
                      onChange={(event) => updateBankField("account_holder_name", event.target.value)}
                      autoComplete="off"
                      className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                    />
                  </label>
                  {bankForm.account_ownership === "business" ? (
                    <label className="grid gap-2 text-sm font-medium">
                      Business name
                      <input
                        value={bankForm.business_name}
                        onChange={(event) => updateBankField("business_name", event.target.value)}
                        autoComplete="off"
                        className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                      />
                    </label>
                  ) : null}
                  <label className="grid gap-2 text-sm font-medium">
                    Bank name
                    <input
                      value={bankForm.bank_name}
                      onChange={(event) => updateBankField("bank_name", event.target.value)}
                      autoComplete="off"
                      className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                    />
                  </label>
                  <label className="grid gap-2 text-sm font-medium">
                    Routing number
                    <input
                      value={bankForm.routing_number}
                      onChange={(event) => updateBankField("routing_number", event.target.value)}
                      inputMode="numeric"
                      autoComplete="off"
                      className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                    />
                  </label>
                  <label className="grid gap-2 text-sm font-medium">
                    Account number
                    <input
                      value={bankForm.account_number}
                      onChange={(event) => updateBankField("account_number", event.target.value)}
                      inputMode="numeric"
                      autoComplete="off"
                      className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 font-normal"
                    />
                  </label>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
            <div>
              <label className="grid gap-2 text-sm font-medium">
                Upload signed Form G-1450 or G-1650 PDF
                <input
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={(event) => setPaymentUploadFile(event.target.files?.[0] ?? null)}
                  className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 py-2 font-normal"
                />
              </label>
              <p className="mt-2 text-xs text-ink/55">Local upload limit: {MAX_PACKET_UPLOAD_SIZE_MB} MB per file.</p>
              {paymentUploads.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {paymentUploads.map((upload) => (
                    <span
                      key={upload.id}
                      className="inline-flex max-w-full items-center gap-2 rounded-full border border-pine/20 bg-paper px-3 py-1 text-xs text-pine"
                    >
                      <span className="truncate">{upload.original_filename}</span>
                      <button
                        type="button"
                        onClick={() => removeUpload(upload)}
                        disabled={isPending}
                        className="rounded-full border border-pine/20 px-1.5 py-0.5 text-[11px] font-semibold text-pine/80 transition hover:border-pine/40 hover:text-pine disabled:opacity-50"
                        aria-label={`Remove ${upload.original_filename}`}
                      >
                        Remove
                      </button>
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
            <button
              type="button"
              onClick={uploadPaymentG1450}
              disabled={isPending || !caseSummary || !paymentUploadFile}
              className="min-h-11 rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-white disabled:opacity-55"
            >
              Upload payment PDF
            </button>
          </div>
        )}
      </section>

      <section className="grid gap-4 rounded-lg border border-ink/10 bg-white p-5 lg:grid-cols-[1fr_1fr_1fr_auto] lg:items-end">
        <label>
          <span className="text-sm font-semibold">Filer location</span>
          <select
            value={stateCode}
            onChange={(event) => setStateCode(event.target.value)}
            className="mt-2 h-11 w-full rounded-lg border border-ink/15 bg-white px-3 text-sm"
          >
            <option value="">Choose state or territory</option>
            {US_LOCATIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <div>
          <p className="text-sm font-semibold">Delivery method</p>
          <div className="mt-2 grid grid-cols-2 rounded-lg border border-ink/15 bg-paper p-1">
            {[
              ["usps", "USPS"],
              ["private", "FedEx / UPS / DHL"],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setCarrier(value as "usps" | "private")}
                className={classNames(
                  "rounded-md px-3 py-2 text-sm font-semibold",
                  carrier === value ? "bg-ink text-white" : "text-ink/65",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <label className="grid min-h-20 gap-2 rounded-lg border border-ink/10 bg-paper/50 p-3 text-sm">
          <span className="flex items-start justify-between gap-3">
            <span>
              <span className="block font-semibold">Include evidence PDFs</span>
              <span className="mt-1 block text-xs leading-5 text-ink/55">
                Turn off to print generated forms and payment pages only.
              </span>
            </span>
            <input
              type="checkbox"
              checked={includeSupportingEvidence}
              onChange={(event) => setIncludeSupportingEvidence(event.target.checked)}
              className="mt-1 h-5 w-5 rounded border-ink/30 text-pine"
            />
          </span>
        </label>
        <button
          type="button"
          onClick={generateFullPacket}
          disabled={!caseSummary || !stateCode || isPending}
          className="min-h-11 rounded-lg bg-pine px-5 py-3 text-sm font-semibold text-white disabled:opacity-55"
        >
          {isPending ? "Working..." : includeSupportingEvidence ? "Generate full packet" : "Generate forms only"}
        </button>
      </section>

      {result ? (
        <section className="grid gap-4 lg:grid-cols-[1fr_0.8fr]">
          <div className="rounded-lg border border-pine/25 bg-white p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.16em] text-pine">Packet ready</p>
                <h2 className="mt-1 text-xl font-semibold">Full packet PDF</h2>
                <p className="mt-2 break-all text-sm text-ink/65">{result.generated_pdf}</p>
                <p className="mt-1 text-xs text-ink/55">{result.total_page_count} total pages</p>
              </div>
              <div className="flex flex-col gap-2 sm:min-w-36">
                <a
                  href={apiUrl(result.download_url)}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-lg border border-pine bg-pine px-4 py-2 text-center text-sm font-semibold text-white"
                >
                  Open PDF
                </a>
                <a
                  href={apiUrl(result.manifest_download_url)}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-lg border border-ink/15 bg-white px-4 py-2 text-center text-sm font-semibold text-ink"
                >
                  Manifest JSON
                </a>
              </div>
            </div>
            <div className="mt-4 rounded-lg border border-ink/10 bg-paper/60 p-3 text-sm">
              <p className="font-semibold">Packet manifest</p>
              <p className="mt-1 break-all text-xs text-ink/55">{result.manifest_json}</p>
            </div>
            <div className="mt-4 grid gap-2">
              {result.included_documents.map((document, index) => (
                <div key={packetDocumentKey(document, index)} className="rounded-lg border border-ink/10 bg-paper/60 p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold">{document.label}</span>
                    <span className="text-xs uppercase tracking-[0.14em] text-ink/45">
                      {document.page_count} page{document.page_count === 1 ? "" : "s"}
                    </span>
                  </div>
                  {document.section ? <p className="mt-1 text-xs font-semibold text-pine">{document.section}</p> : null}
                  <p className="mt-1 break-all text-xs text-ink/55">{document.filename}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-ink/10 bg-white p-5">
            <p className="text-xs uppercase tracking-[0.16em] text-pine">Mailing</p>
            {result.mailing_recommendation ? (
              <>
                <h2 className="mt-1 text-xl font-semibold">{result.mailing_recommendation.lockbox}</h2>
                <div className="mt-4 rounded-lg border border-ink/10 bg-paper/70 p-4 text-sm leading-7">
                  {result.mailing_recommendation.address_lines.map((line, index) => (
                    <p key={`${index}-${line}`}>{line}</p>
                  ))}
                </div>
                <p className="mt-3 text-xs leading-5 text-ink/55">
                  Source last reviewed by USCIS {result.mailing_recommendation.source_last_reviewed}; app verified {result.mailing_recommendation.verified_on}.
                </p>
                <a
                  href={result.mailing_recommendation.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-3 inline-flex rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm font-semibold"
                >
                  USCIS lockbox source
                </a>
              </>
            ) : (
              <p className="mt-2 text-sm text-ink/65">Choose a filer location to see lockbox guidance.</p>
            )}
          </div>
        </section>
      ) : null}

      {result?.warnings.length ? (
        <section className="rounded-lg border border-amber-200 bg-amber-50 p-5 text-sm leading-7 text-amber-950">
          <p className="font-semibold">Review notes</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {result.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {result?.skipped_documents.length ? (
        <section className="rounded-lg border border-ink/10 bg-white p-5">
          <h2 className="text-lg font-semibold">Skipped files</h2>
          <div className="mt-4 grid gap-2">
            {result.skipped_documents.map((document, index) => (
              <div key={`${packetDocumentKey(document, index)}|${document.reason}`} className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
                <p className="font-semibold">{document.label}</p>
                <p className="mt-1">{document.reason}</p>
                {document.filename ? <p className="mt-1 break-all text-xs opacity-75">{document.filename}</p> : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="grid gap-4">
        {groupedItems.map((group) => (
          <div key={group.key} className="rounded-lg border border-ink/10 bg-white p-5">
            <div className="flex flex-col gap-2 border-b border-ink/10 pb-4 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.16em] text-pine">Evidence category</p>
                <h2 className="mt-1 text-xl font-semibold">{group.label}</h2>
              </div>
              <span className="text-sm text-ink/55">
                {group.items.length} item{group.items.length === 1 ? "" : "s"}
              </span>
            </div>
            <div className="mt-4 grid gap-3">
              {group.items.map((item) => {
                const itemUploads = uploadsByCode.get(item.code) ?? [];
                const draft = uploadDrafts[item.code] ?? defaultUploadDraft();
                const generatedOnly = GENERATED_ONLY_UPLOAD_CODES.has(item.code);
                return (
                  <div key={item.id} className="rounded-lg border border-ink/10 bg-paper/50 p-4">
                    <div className="grid gap-4 lg:grid-cols-[1fr_1.25fr]">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="font-semibold">{item.label}</h3>
                          <span className="rounded-full bg-white px-2 py-1 text-xs font-semibold text-ink/55">
                            {formatStatus(item.applicability)}
                          </span>
                          <span className="rounded-full bg-white px-2 py-1 text-xs font-semibold text-ink/55">
                            {formatStatus(item.completion_status)}
                          </span>
                        </div>
                        <p className="mt-2 text-sm leading-6 text-ink/65">
                          {item.what_to_save_now || item.description}
                        </p>
                        {itemUploads.length ? (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {itemUploads.map((upload) => (
                              <span
                                key={upload.id}
                                className="inline-flex max-w-full items-center gap-2 rounded-full border border-pine/20 bg-white px-3 py-1 text-xs text-pine"
                              >
                                <span className="truncate">{upload.original_filename}</span>
                                <span className="rounded-full bg-pine/10 px-1.5 py-0.5 text-[10px] uppercase tracking-[0.12em]">
                                  {formatStatus(upload.upload_status)}
                                </span>
                                <button
                                  type="button"
                                  onClick={() => removeUpload(upload)}
                                  disabled={isPending}
                                  className="rounded-full border border-pine/20 px-1.5 py-0.5 text-[11px] font-semibold text-pine/80 transition hover:border-pine/40 hover:text-pine disabled:opacity-50"
                                  aria-label={`Remove ${upload.original_filename}`}
                                >
                                  Remove
                                </button>
                              </span>
                            ))}
                          </div>
                        ) : null}
                      </div>
                      {generatedOnly ? (
                        <div className="rounded-lg border border-pine/15 bg-white p-3 text-sm leading-6 text-ink/68">
                          This form is generated from the saved case answers. Uploaded copies are shown here only so you can remove old files; they are skipped during packet assembly.
                        </div>
                      ) : (
                        <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                          <input
                            type="file"
                            accept="application/pdf,.pdf"
                            onChange={(event) => updateDraft(item.code, { file: event.target.files?.[0] ?? null })}
                            className="min-h-11 rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm"
                          />
                          <button
                            type="button"
                            onClick={() => uploadForItem(item)}
                            disabled={isPending || !caseSummary || !draft.file}
                            className="rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-white disabled:opacity-55"
                          >
                            Upload
                          </button>
                          <p className="text-xs text-ink/55 sm:col-span-2">
                            Local upload limit: {MAX_PACKET_UPLOAD_SIZE_MB} MB per file.
                          </p>
                          <select
                            value={draft.documentLanguage}
                            onChange={(event) => updateDraft(item.code, { documentLanguage: event.target.value })}
                            className="h-10 rounded-lg border border-ink/15 bg-white px-3 text-sm"
                          >
                            <option value="english">English</option>
                            <option value="spanish">Spanish</option>
                            <option value="other">Other</option>
                            <option value="unknown">Unknown</option>
                          </select>
                          <label className="flex min-h-10 items-center gap-2 rounded-lg border border-ink/15 bg-white px-3 text-sm">
                            <input
                              type="checkbox"
                              checked={draft.hasTranslation}
                              onChange={(event) => updateDraft(item.code, { hasTranslation: event.target.checked })}
                            />
                            Translation attached
                          </label>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </section>
    </main>
  );
}

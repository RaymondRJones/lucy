export type PacketFormKey = "i130" | "i130a" | "i485" | "i864" | "i765" | "i131";

export type PacketFormFlowOption = {
  formCode: string;
  formKey: PacketFormKey;
  label: string;
  detail: string;
  phase: string;
};

export const PACKET_FORM_FLOW: PacketFormFlowOption[] = [
  { formCode: "form_i130", formKey: "i130", label: "I-130", detail: "Spouse petition", phase: "Petition" },
  {
    formCode: "form_i130a",
    formKey: "i130a",
    label: "I-130A",
    detail: "Spouse biographic supplement",
    phase: "Petition",
  },
  { formCode: "form_i485", formKey: "i485", label: "I-485", detail: "Adjustment application", phase: "Green card" },
  { formCode: "form_i864", formKey: "i864", label: "I-864", detail: "Sponsor support", phase: "Financial" },
  { formCode: "form_i765", formKey: "i765", label: "I-765", detail: "Work authorization", phase: "Optional" },
  { formCode: "form_i131", formKey: "i131", label: "I-131", detail: "Advance parole", phase: "Optional" },
];

export function packetFormHref(formKey: PacketFormKey, caseId?: string | null) {
  const caseQuery = caseId ? `caseId=${encodeURIComponent(caseId)}` : "";
  if (formKey === "i485") {
    return caseQuery ? `/i485-ingestion?${caseQuery}` : "/i485-ingestion";
  }
  const formQuery = `form=${encodeURIComponent(formKey)}`;
  return `/form-ingestion?${caseQuery ? `${formQuery}&${caseQuery}` : formQuery}`;
}

export function packetFormsForIncluded(includedForms?: string[] | null) {
  if (!includedForms?.length) {
    return PACKET_FORM_FLOW;
  }
  const included = new Set(includedForms);
  return PACKET_FORM_FLOW.filter((option) => included.has(option.formCode));
}

export function packetFormOptionForKey(formKey: string) {
  return PACKET_FORM_FLOW.find((option) => option.formKey === formKey);
}

export function ensurePacketFormOption(options: PacketFormFlowOption[], formKey: string) {
  const currentOption = packetFormOptionForKey(formKey);
  if (!currentOption || options.some((option) => option.formKey === currentOption.formKey)) {
    return options;
  }
  return [currentOption, ...options];
}

export function nextPacketFormOption(options: PacketFormFlowOption[], currentFormKey: string) {
  const currentIndex = options.findIndex((option) => option.formKey === currentFormKey);
  if (currentIndex < 0) {
    return options[0] ?? null;
  }
  return options[currentIndex + 1] ?? null;
}

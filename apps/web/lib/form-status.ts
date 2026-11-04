import { getFormFillPreview, getI485FormFillPreview, getPrescreenState } from "@/lib/api";
import { packetFormsForIncluded, type PacketFormKey } from "@/lib/packet-form-flow";

export type FormStatus = { missing: number };
export type FormStatuses = Partial<Record<PacketFormKey, FormStatus>>;

const cache = new Map<string, Promise<FormStatuses>>();

// Missing required answers per packet form, from the backend fill previews. Shared by the
// step bar and the form tabs so one page load asks once.
export function loadFormStatuses(caseId: string): Promise<FormStatuses> {
  const cached = cache.get(caseId);
  if (cached) {
    return cached;
  }
  const request = getPrescreenState(caseId)
    .catch(() => null)
    .then(async (prescreen) => {
      const options = packetFormsForIncluded(prescreen?.evaluation.included_forms);
      const entries = await Promise.all(
        options.map(async (option) => {
          const preview = await (option.formKey === "i485"
            ? getI485FormFillPreview(caseId)
            : getFormFillPreview(caseId, option.formKey)
          ).catch(() => null);
          return preview ? ([option.formKey, { missing: preview.missing_required_count }] as const) : null;
        }),
      );
      return Object.fromEntries(entries.filter((entry) => entry !== null)) as FormStatuses;
    });
  cache.set(caseId, request);
  return request;
}

export function forgetFormStatuses(caseId: string) {
  cache.delete(caseId);
}

import { FormIngestionWorkspace } from "@/components/form-ingestion-workspace";

export default async function FormIngestionPage({
  searchParams,
}: {
  searchParams: Promise<{ caseId?: string; form?: string }>;
}) {
  const params = await searchParams;
  return <FormIngestionWorkspace initialCaseId={params.caseId} initialFormKey={params.form} />;
}

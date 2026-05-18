import { I485IngestionWorkspace } from "@/components/i485-ingestion-workspace";

export default async function I485IngestionPage({
  searchParams,
}: {
  searchParams: Promise<{ caseId?: string }>;
}) {
  const params = await searchParams;
  return <I485IngestionWorkspace initialCaseId={params.caseId} />;
}

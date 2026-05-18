import { PublicCard, PublicPage } from "@/components/public-page";

const STEPS = [
  {
    title: "Create or open a case",
    body: "Lucy starts with a local case workspace for the petitioner, beneficiary, checklist, uploads, and review issues.",
  },
  {
    title: "Complete intake or ingest existing forms",
    body: "Clients who have not started can answer structured questions. Clients with existing PDFs can import a packet folder and let ingestion extract reviewable facts.",
  },
  {
    title: "Generate the checklist",
    body: "The API derives conservative case facts, evaluates checklist rules, and marks which forms and evidence appear applicable.",
  },
  {
    title: "Upload and link documents",
    body: "Files are attached to checklist items so one document can satisfy more than one requirement when the mapping is explainable.",
  },
  {
    title: "Run QA",
    body: "The backend checks for missing required items, translation support, selected form-edition signals, source-backed mismatches, and higher-risk intake answers.",
  },
  {
    title: "Prepare for final review",
    body: "Lucy can help organize what to print and review, but a human still confirms sources, signatures, dates, fees, and legal strategy before mailing.",
  },
];

export default function HowItWorksPage() {
  return (
    <PublicPage
      eyebrow="Workflow"
      title="Lucy keeps the packet process inspectable instead of magical."
      description="Every major action should leave behind saved data: intake answers, extracted fields, checklist status, upload metadata, QA issues, and source reminders."
    >
      <div className="grid gap-4 md:grid-cols-2">
        {STEPS.map((step, index) => (
          <PublicCard key={step.title} title={step.title} eyebrow={`Step ${index + 1}`}>
            {step.body}
          </PublicCard>
        ))}
      </div>
    </PublicPage>
  );
}

import { PublicCard, PublicPage } from "@/components/public-page";

const STEPS = [
  {
    title: "Prescreen",
    body: "Answer a short set of questions about your marriage and immigration history. Lucy tells you whether your case fits the standard path and which forms your packet needs.",
  },
  {
    title: "Forms",
    body: "Fill in each USCIS form page by page. Facts you have already given, like names and addresses, carry over so you confirm them instead of retyping.",
  },
  {
    title: "Checklist",
    body: "See every document each form needs, such as birth certificates, photos, and proof of your relationship, and tick items off as you collect them.",
  },
  {
    title: "Review",
    body: "Lucy checks for missing answers, mismatches between forms, and answers outside the standard path, and links each issue to where you fix it.",
  },
  {
    title: "Print packet",
    body: "Attach your evidence, add payment, and choose where you live. Lucy assembles one PDF in USCIS order and shows the mailing address to use.",
  },
];

export default function HowItWorksPage() {
  return (
    <PublicPage
      eyebrow="Workflow"
      title="Five steps from first question to a mail-ready packet."
      description="Everything you enter is saved on your computer, so you can stop and pick up where you left off. You stay in control of what gets signed and mailed."
    >
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {STEPS.map((step, index) => (
          <PublicCard key={step.title} title={step.title} eyebrow={`Step ${index + 1}`}>
            {step.body}
          </PublicCard>
        ))}
      </div>
    </PublicPage>
  );
}

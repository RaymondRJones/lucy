import Link from "next/link";

import { PublicPage } from "@/components/public-page";
import { buttonClass, cardClass, cx } from "@/components/ui";

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
      <ol className={cx(cardClass, "divide-y divide-line")}>
        {STEPS.map((step, index) => (
          <li key={step.title} className="grid grid-cols-[2rem_minmax(0,1fr)] gap-4 p-5 md:p-6">
            <span
              aria-hidden="true"
              className="flex h-8 w-8 items-center justify-center rounded-full bg-pine-soft text-sm font-bold tabular-nums text-pine-strong"
            >
              {index + 1}
            </span>
            <div>
              <h2 className="text-base font-semibold text-ink">
                <span className="sr-only">Step {index + 1}: </span>
                {step.title}
              </h2>
              <p className="mt-1 text-sm leading-6 text-muted">{step.body}</p>
            </div>
          </li>
        ))}
      </ol>
      <div className="flex flex-wrap items-center gap-3">
        <Link href="/prescreen" className={buttonClass("primary", "lg")}>
          Start a new packet
        </Link>
        <Link href="/legal-disclaimer" className={buttonClass("ghost", "lg")}>
          Read what Lucy is not
        </Link>
      </div>
    </PublicPage>
  );
}

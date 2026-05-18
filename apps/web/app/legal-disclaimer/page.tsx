import { PublicCard, PublicPage } from "@/components/public-page";

export default function LegalDisclaimerPage() {
  return (
    <PublicPage
      eyebrow="Legal boundary"
      title="Lucy organizes information. It does not provide legal advice."
      description="Immigration filings can be high-stakes. Lucy can help collect facts, track documents, and flag review items, but it cannot decide legal strategy or replace a licensed immigration attorney."
    >
      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <PublicCard title="What Lucy can do" eyebrow="Organizational support">
          <p>
            Lucy can save factual intake answers, organize uploads, generate a conservative
            checklist from stored rules, and surface possible inconsistencies for human review.
          </p>
          <p className="mt-3">
            It can also point to stored source references when the content layer has official URLs and
            verification dates.
          </p>
        </PublicCard>
        <PublicCard title="What Lucy cannot do" eyebrow="Not legal advice">
          <p>
            Lucy does not create an attorney-client relationship, decide eligibility, choose legal
            strategy, guarantee USCIS acceptance, or confirm that a packet is safe to file.
          </p>
          <p className="mt-3">
            Users should seek qualified legal help for unlawful entry, criminal history, prior denials,
            removal history, identity inconsistencies, complex finances, or any fact pattern they do not
            fully understand.
          </p>
        </PublicCard>
      </div>
    </PublicPage>
  );
}

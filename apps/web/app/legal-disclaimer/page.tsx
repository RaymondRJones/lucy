import { PublicCard, PublicPage } from "@/components/public-page";

export default function LegalDisclaimerPage() {
  return (
    <PublicPage
      eyebrow="Legal boundary"
      title="Lucy organizes information. It does not provide legal advice."
      description="Immigration filings can be high-stakes. Lucy can help collect facts, track documents, and flag review items, but it cannot decide legal strategy or replace a licensed immigration attorney."
    >
      <div className="grid max-w-5xl gap-6 md:grid-cols-2">
        <PublicCard title="What Lucy can do" eyebrow="Organizational support">
          <p>
            Lucy saves your answers, fills in the USCIS forms, organizes your documents, builds a checklist,
            and points out answers that look inconsistent or unusual so you can check them.
          </p>
          <p className="mt-3">
            Where Lucy states a USCIS rule, fee, or address, it links the official USCIS page and the date it was
            last checked, so you can confirm it yourself.
          </p>
        </PublicCard>
        <PublicCard title="What Lucy cannot do" eyebrow="Not legal advice">
          <p>
            Lucy does not create an attorney-client relationship, decide eligibility, choose legal
            strategy, guarantee USCIS acceptance, or confirm that a packet is safe to file.
          </p>
          <p className="mt-3">
            Talk to an immigration attorney or accredited representative about unlawful entry, criminal history, prior denials,
            removal history, identity inconsistencies, complex finances, or any fact pattern they do not
            fully understand.
          </p>
        </PublicCard>
      </div>
    </PublicPage>
  );
}

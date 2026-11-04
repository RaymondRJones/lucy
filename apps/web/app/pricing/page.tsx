import Link from "next/link";

import { PublicCard, PublicPage } from "@/components/public-page";

export default function PricingPage() {
  return (
    <PublicPage
      eyebrow="Pricing"
      title="Lucy is free, open source, and locally run."
      description="No subscription, hosted account, or payment integration is needed. Lucy is built to run on your own personal computer while the MVP proves the happy-path I-485 packet workflow."
    >
      <section className="rounded-[2.4rem] border border-pine/15 bg-white/78 p-6 shadow-panel md:p-8">
        <p className="text-xs uppercase tracking-[0.24em] text-pine">Current plan</p>
        <div className="mt-3 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h2 className="font-display text-5xl text-ink">$0</h2>
            <p className="mt-2 text-sm leading-7 text-ink/80">Free access to the local Lucy MVP workspace.</p>
          </div>
          <Link
            href="/prescreen"
            className="rounded-full bg-ink px-5 py-3 text-center text-sm font-semibold text-white transition hover:bg-pine"
          >
            Start prescreen
          </Link>
        </div>
      </section>

      <div className="grid gap-6 md:grid-cols-3">
        <PublicCard title="Included now">Case workspace, intake, checklist, local uploads, QA, source reminders, and packet assembly.</PublicCard>
        <PublicCard title="Not included yet">Production authentication, paid plans, attorney review, direct USCIS filing, or live payment processing.</PublicCard>
        <PublicCard title="Before launch">Add user ownership, deployment secrets, production storage, and locked-down debug/admin access.</PublicCard>
      </div>
    </PublicPage>
  );
}

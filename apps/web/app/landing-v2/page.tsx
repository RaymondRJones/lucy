import Link from "next/link";
import type { Metadata } from "next";

const GITHUB_URL = "https://github.com/your-org/lucy";

const PROBLEM_POINTS = [
  "You do not want to spend $5,000 just to organize a straightforward filing.",
  "Your marriage case is simple, documented, and inside the narrow happy-path scope.",
  "You are willing to do the work yourself, but you do not want to miss one small field.",
  "You know the packet still has to be reviewed, signed, printed, organized, and mailed.",
  "You want mistake-checking before print day, not after a rejection notice or delay.",
];

const PAIN_POINTS = [
  "You keep opening the same PDFs and still cannot tell what is actually finished.",
  "Every checklist online looks close, but none of them feel specific to your situation.",
  "You are confident enough to file, but not confident enough to trust a pile of downloads.",
  "The forms ask the same questions in slightly different ways, and you worry about inconsistent answers.",
  "You do not want to upload your family documents into another random web account.",
  "You want a roadmap that catches obvious issues without pretending to be your lawyer.",
];

const BENEFITS = [
  {
    title: "Turn the pile into a path",
    body: "Lucy turns the happy-path marriage packet into a guided sequence: prescreen, form intake, evidence, review, and final packet assembly.",
  },
  {
    title: "Reuse facts instead of retyping them",
    body: "Smart defaults carry reviewed answers across I-485, I-130, I-130A, I-864, I-765, I-131, and G-1145 whenever the same fact appears again.",
  },
  {
    title: "See what is unusual early",
    body: "Answers outside the MVP path are flagged clearly so you can pause, verify, and decide whether professional help makes sense.",
  },
  {
    title: "Keep the work on your computer",
    body: "The local app stores case data, generated drafts, and uploaded files on your own machine during development use.",
  },
];

const INCLUDED = [
  {
    title: "Happy-path prescreen",
    body: "A plain-English branch check for a U.S. citizen spouse, foreign spouse living in the United States, lawful-entry adjustment path.",
  },
  {
    title: "Guided form workspaces",
    body: "Structured intake for I-485, I-130, I-130A, I-864, I-765, I-131, and G-1145 with progress tracking and reusable answers.",
  },
  {
    title: "Draft PDF generation",
    body: "Local review drafts from the answers you saved, so you can inspect the forms before printing anything.",
  },
  {
    title: "Evidence checklist",
    body: "A packet-focused list for civil documents, financial support, relationship evidence, identity documents, and translations.",
  },
  {
    title: "Mistake-checking pass",
    body: "A conservative QA layer for missing items, inconsistent facts, unusual answers, and packet-readiness blockers.",
  },
  {
    title: "Packet assembly",
    body: "Cover letter, section pages, generated forms, optional supporting evidence, manifest, and print-oriented packet output.",
  },
  {
    title: "Local-first project",
    body: "Open-source code you can inspect, run, modify, and improve without subscribing to a hosted filing service.",
  },
  {
    title: "Clear boundaries",
    body: "Built-in reminders that Lucy organizes information and draft paperwork, but does not provide legal advice or guarantee approval.",
  },
];

const FAQS = [
  {
    question: "Is Lucy a law firm or legal service?",
    answer:
      "No. Lucy is an organizational software project. It can help you collect facts, generate draft forms, track evidence, and catch obvious missing pieces. It does not create an attorney-client relationship, choose legal strategy, or guarantee that USCIS will accept or approve a filing.",
  },
  {
    question: "Who is this built for?",
    answer:
      "The MVP is for the narrow happy path: a U.S. citizen spouse, a foreign spouse already residing in the United States, a straightforward marriage-based adjustment packet, clear evidence, and no major complicating facts.",
  },
  {
    question: "Who should not rely on the happy-path workflow?",
    answer:
      "Anyone with arrests, removal history, unlawful entry, prior denials, complex prior marriages, serious status questions, unusual financial sponsorship issues, or facts they do not fully understand should treat Lucy's warning flags as a reason to get qualified legal help.",
  },
  {
    question: "Does Lucy file anything with USCIS online?",
    answer:
      "No. Lucy helps prepare a local packet workspace and printable drafts. You still review the current USCIS instructions, confirm fees and editions, sign where required, and handle the actual filing process yourself.",
  },
  {
    question: "Why make this free and open source?",
    answer:
      "The point is to make a simple packet workflow inspectable. People should be able to see how the checklist, branching, form mapping, and packet assembly work instead of trusting a black box with sensitive family documents.",
  },
  {
    question: "Can Lucy replace careful review?",
    answer:
      "No. The best use of Lucy is to reduce avoidable mistakes before your human review. Every generated form and packet section still needs to be checked against your real documents, signatures, dates, fees, and current USCIS instructions.",
  },
  {
    question: "Will this work for I-130 and I-130A too?",
    answer:
      "Yes, when the prescreen branch says the spouse petition has not already been filed, Lucy can guide I-130 and I-130A draft preparation along with the I-485-centered packet workflow.",
  },
  {
    question: "What makes this different from a checklist PDF?",
    answer:
      "Lucy saves answers, branches based on the case path, reuses source-of-truth facts across forms, generates drafts, tracks uploaded evidence, and produces review warnings. A static checklist cannot do that.",
  },
  {
    question: "What makes this different from a paid filing service?",
    answer:
      "Lucy is local-first and open source. It is not trying to sell attorney review, hold your documents in a hosted account, or promise a legal outcome. It is trying to make a simple do-it-yourself packet easier to assemble and review.",
  },
  {
    question: "Is there urgency to use it?",
    answer:
      "The practical urgency is error reduction. The longer the packet lives across scattered PDFs, folders, and memory, the easier it is to miss a repeated field, stale answer, or missing evidence item before printing.",
  },
  {
    question: "What should I verify before mailing?",
    answer:
      "Confirm current USCIS form editions, filing addresses, fees, signatures, dates, evidence copies, translations, payment details, and whether your facts still fit the simple happy-path scope.",
  },
];

export const metadata: Metadata = {
  title: "Lucy Landing V2",
  description:
    "A free, open-source, locally run I-485 packet generator for happy-path married couples.",
};

export default function LandingV2Page() {
  return (
    <main className="min-h-screen bg-[#f6f6ef] text-ink">
      <section className="relative min-h-[86vh] overflow-hidden bg-ink">
        <div className="absolute inset-0 bg-[linear-gradient(120deg,#1f302d_0%,#25433d_54%,#91b6ad_100%)]" />
        <div className="absolute inset-y-0 right-[-50vw] w-[125vw] bg-[url('/lucy-landing-v2-preview.png')] bg-contain bg-right bg-no-repeat opacity-35 md:right-[-12vw] md:w-[64vw] md:opacity-95 lg:right-[-4vw] lg:w-[58vw]" />
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(31,48,45,0.98)_0%,rgba(31,48,45,0.96)_48%,rgba(31,48,45,0.78)_66%,rgba(31,48,45,0.18)_100%)]" />
        <nav className="relative z-10 mx-auto flex w-full max-w-7xl flex-col gap-3 px-4 py-4 text-white md:flex-row md:items-center md:justify-between md:px-8">
          <Link href="/" className="font-display text-3xl font-semibold tracking-normal">
            Lucy
          </Link>
          <div className="flex flex-wrap gap-2">
            <Link href="/prescreen" className="rounded-lg border border-white/25 px-3 py-2 text-sm font-semibold">
              Start packet
            </Link>
            <Link href="/packet-assembly" className="rounded-lg border border-white/25 px-3 py-2 text-sm font-semibold">
              Review packet
            </Link>
          </div>
        </nav>

        <div className="relative z-10 mx-auto flex min-h-[calc(86vh-4.5rem)] w-full max-w-7xl items-center px-4 pb-10 pt-6 md:px-8">
          <div className="max-w-3xl">
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[#bdd8d0]">
              For happy-path married couples doing the I-485 packet themselves
            </p>
            <h1 className="mt-4 font-display text-3xl leading-tight text-white sm:text-4xl md:text-5xl">
              A free local packet generator for your marriage green card filing.
            </h1>
            <p className="mt-4 max-w-3xl text-sm leading-6 text-white/80 md:mt-6 md:text-lg md:leading-8">
              Lucy is completely free, open-source software for U.S. citizen spouses and foreign spouses in the
              United States who have a straightforward case, clear evidence, and want to prepare a full
              I-485-centered packet from their own computer.
            </p>
            <p className="mt-4 max-w-2xl text-xl font-semibold leading-snug text-white md:mt-6 md:text-2xl">
              Build your packet with calm confidence.
            </p>
            <p className="mt-4 max-w-3xl text-xs leading-5 text-white/75 md:mt-5 md:text-base md:leading-7">
              Get instant access to happy-path prescreening, branch-based form selection, guided I-485 intake,
              I-130 and I-130A preparation when needed, I-864 sponsor intake, optional I-765 and I-131 workspaces,
              smart autofill from saved answers, evidence tracking, local PDF draft generation, packet QA, cover
              letter and section pages, forms-only printing, full packet assembly, and plain-English review flags.
            </p>
            <div className="mt-5 flex flex-col gap-3 sm:flex-row md:mt-8">
              <a
                href={GITHUB_URL}
                className="rounded-lg bg-white px-5 py-3 text-center text-sm font-semibold text-ink transition hover:bg-[#e7f0ec]"
              >
                Get it free on GitHub
              </a>
              <Link
                href="/prescreen"
                className="rounded-lg border border-white/30 px-5 py-3 text-center text-sm font-semibold text-white transition hover:bg-white/10"
              >
                Start packet locally
              </Link>
            </div>
            <p className="mt-5 hidden max-w-3xl text-xs leading-6 text-white/60 md:block">
              Lucy is not legal advice. It is intentionally scoped to the simple MVP path and flags unusual
              answers for review.
            </p>
          </div>
        </div>
      </section>

      <section className="mx-auto grid w-full max-w-7xl gap-8 px-4 py-16 md:px-8 lg:grid-cols-[0.9fr_1.1fr]">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-pine">Their problem</p>
          <h2 className="mt-3 font-display text-4xl leading-tight md:text-5xl">
            You do not need a giant legal machine for a simple packet.
          </h2>
          <p className="mt-5 text-base leading-8 text-ink/70">
            You need a reliable path through the exact forms, repeated fields, evidence categories, and print-day
            checks that make a do-it-yourself filing feel heavier than it should.
          </p>
        </div>
        <div className="grid gap-3">
          {PROBLEM_POINTS.map((point) => (
            <div key={point} className="rounded-lg border border-ink/10 bg-white p-4 text-sm font-semibold shadow-sm">
              {point}
            </div>
          ))}
        </div>
      </section>

      <section className="border-y border-ink/10 bg-white">
        <div className="mx-auto w-full max-w-7xl px-4 py-16 md:px-8">
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-clay">If any of this sounds like you</p>
          <div className="mt-8 grid gap-3 md:grid-cols-2">
            {PAIN_POINTS.map((point) => (
              <p key={point} className="rounded-lg border border-ink/10 bg-[#f8faf7] p-4 text-base leading-7 text-ink/75">
                {point}
              </p>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto w-full max-w-7xl px-4 py-16 md:px-8">
        <div className="max-w-4xl">
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-pine">The after</p>
          <h2 className="mt-3 font-display text-4xl leading-tight md:text-5xl">
            Go from scattered uncertainty to a reviewable packet workspace.
          </h2>
        </div>
        <div className="mt-8 grid gap-4 md:grid-cols-2">
          {BENEFITS.map((benefit) => (
            <article key={benefit.title} className="rounded-lg border border-ink/10 bg-white p-5 shadow-sm">
              <h3 className="font-display text-2xl">{benefit.title}</h3>
              <p className="mt-3 text-sm leading-7 text-ink/70">{benefit.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="bg-[#e6efe9]">
        <div className="mx-auto grid w-full max-w-7xl gap-8 px-4 py-16 md:px-8 lg:grid-cols-[0.8fr_1.2fr]">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-pine">Introducing</p>
            <h2 className="mt-3 font-display text-4xl leading-tight md:text-5xl">Lucy, the local I-485 packet workspace.</h2>
          </div>
          <div className="text-base leading-8 text-ink/75">
            <p>
              Lucy is the free, open-source packet generator you were looking for if your case is simple enough to do
              yourself, but important enough that you want branching, smart defaults, review warnings, and a final
              packet you can inspect before mailing.
            </p>
            <p className="mt-5">
              It came from the least glamorous part of the process: sitting with the actual forms, the actual repeated
              questions, the evidence categories, the signature traps, the payment workflow, and the emotional reality
              of preparing a family immigration packet without wanting to hand private documents to another service.
            </p>
            <p className="mt-5">
              Most tools either stay too generic or jump straight to paid legal help. Lucy is different because it is
              deliberately narrow. The product only tries to serve the happy path well: prescreen first, eliminate work
              that does not apply, ask one clear question at a time, reuse the facts you already confirmed, create
              draft PDFs locally, and flag the places where a simple packet may no longer be simple.
            </p>
            <p className="mt-5">
              That narrowness is the point. A broad immigration app has to speak vaguely. Lucy can speak plainly
              because it is built around one do-it-yourself journey: a U.S. citizen spouse helping a foreign spouse in
              the United States prepare a marriage-based adjustment packet with clear evidence and careful review.
            </p>
          </div>
        </div>
      </section>

      <section className="mx-auto w-full max-w-7xl px-4 py-16 md:px-8">
        <div className="max-w-4xl">
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-pine">What is included</p>
          <h2 className="mt-3 font-display text-4xl leading-tight md:text-5xl">
            The whole packet workflow, broken into small reviewable assets.
          </h2>
        </div>
        <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {INCLUDED.map((item) => (
            <article key={item.title} className="rounded-lg border border-ink/10 bg-white p-5 shadow-sm">
              <h3 className="font-display text-xl">{item.title}</h3>
              <p className="mt-3 text-sm leading-7 text-ink/70">{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-ink/10 bg-white">
        <div className="mx-auto w-full max-w-7xl px-4 py-16 md:px-8">
          <div className="max-w-4xl">
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-clay">FAQ</p>
            <h2 className="mt-3 font-display text-4xl leading-tight md:text-5xl">
              Clear answers before you trust the tool.
            </h2>
          </div>
          <div className="mt-8 grid gap-4 lg:grid-cols-2">
            {FAQS.map((faq) => (
              <article key={faq.question} className="rounded-lg border border-ink/10 bg-[#f8faf7] p-5">
                <h3 className="text-base font-semibold">{faq.question}</h3>
                <p className="mt-3 text-sm leading-7 text-ink/70">{faq.answer}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-14 md:flex-row md:items-center md:justify-between md:px-8">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-pine">Free, local, open source</p>
          <h2 className="mt-2 font-display text-3xl leading-tight">Start with the code. Keep control of the packet.</h2>
        </div>
        <a
          href={GITHUB_URL}
          className="rounded-lg bg-ink px-5 py-3 text-center text-sm font-semibold text-white transition hover:bg-pine"
        >
          Get it free on GitHub
        </a>
      </section>
    </main>
  );
}

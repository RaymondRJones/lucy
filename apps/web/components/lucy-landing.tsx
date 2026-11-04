"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { buttonClass, cardClass, cx, eyebrowClass } from "@/components/ui";
import { clearSavedCaseId, getSavedCaseId } from "@/lib/case-storage";

const NAV_LINKS = [
  { href: "/how-it-works", label: "How it works" },
  { href: "/legal-disclaimer", label: "Not legal advice" },
];

const HAPPY_PATH = [
  "A U.S. citizen spouse is the petitioner",
  "The foreign spouse already lives in the United States",
  "A marriage-based Form I-485 adjustment packet",
  "A first marriage with no children",
];

const STEPS = [
  { title: "Prescreen", body: "Check the case fits the standard path and see which forms you need." },
  { title: "Forms", body: "Answer each form once. Shared facts carry over to the others." },
  { title: "Checklist", body: "Track every document and piece of evidence each form needs." },
  { title: "Review", body: "Catch missing answers and mismatches before print day." },
  { title: "Print packet", body: "Assemble one PDF in USCIS order with the right mailing address." },
];

const VALUES = [
  {
    title: "Free and open source",
    body: "No subscription, hosted account, or filing service. The code is yours to inspect and change.",
  },
  {
    title: "Stays on your computer",
    body: "Case data, uploads, and generated forms are saved on your own machine, not in a hosted account.",
  },
  {
    title: "Built for one clear path",
    body: "Lucy focuses on the common marriage case, and flags unusual answers instead of guessing.",
  },
];

export function LucyLanding() {
  const router = useRouter();
  const [savedCaseId, setSavedCaseId] = useState<string | null>(null);

  useEffect(() => {
    setSavedCaseId(getSavedCaseId());
  }, []);

  function startPacket() {
    clearSavedCaseId();
    setSavedCaseId(null);
    router.push("/prescreen");
  }

  function resumePacket() {
    router.push(savedCaseId ? `/prescreen?caseId=${encodeURIComponent(savedCaseId)}` : "/prescreen");
  }

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <header className="border-b border-line bg-white/80">
        <nav aria-label="Main" className="mx-auto flex max-w-shell items-center gap-4 px-4 py-3 md:px-8">
          <Link href="/" className="font-display text-2xl font-semibold leading-none">
            Lucy
          </Link>
          <ul className="ml-auto hidden items-center gap-1 sm:flex">
            {NAV_LINKS.map((link) => (
              <li key={link.href}>
                <Link href={link.href} className="rounded-lg px-3 py-2 text-sm font-semibold text-muted transition-colors hover:bg-paper hover:text-ink">
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
          <button type="button" onClick={resumePacket} className={buttonClass("secondary", "sm", "ml-auto sm:ml-2")}>
            {savedCaseId ? "Open my case" : "Open workspace"}
          </button>
        </nav>
      </header>

      <main id="main">
        <section className="mx-auto grid max-w-shell gap-10 px-4 pb-12 pt-10 md:px-8 md:pt-16 lg:grid-cols-[minmax(0,1fr)_26rem] lg:items-center lg:gap-16">
          <div>
            <p className={eyebrowClass}>Free, local I-485 packet workspace</p>
            <h1 className="mt-4 max-w-3xl font-display text-4xl leading-[1.08] text-ink sm:text-5xl lg:text-6xl">
              Prepare your marriage green card packet with confidence.
            </h1>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-muted">
              Lucy walks you through the questions, fills in the USCIS forms, tracks your evidence, and assembles a
              printable packet, all on your own computer.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <button type="button" onClick={startPacket} className={buttonClass("primary", "lg")}>
                Start a new packet
              </button>
              <button type="button" onClick={resumePacket} className={buttonClass("secondary", "lg")}>
                {savedCaseId ? "Continue my packet" : "Open a saved case"}
              </button>
            </div>
            <p className="mt-6 max-w-2xl text-sm leading-6 text-muted">
              Lucy is not legal advice. It covers the common case of a U.S. citizen spouse and a foreign spouse living in
              the United States, and flags answers outside that path for review.
            </p>
          </div>

          <div className={cx(cardClass, "overflow-hidden shadow-panel")}>
            <div className="border-b border-line bg-paper px-5 py-4">
              <p className="text-sm font-semibold text-ink">Five steps to a mail-ready packet</p>
            </div>
            <ol className="divide-y divide-line">
              {STEPS.map((step, index) => (
                <li key={step.title} className="grid grid-cols-[2rem_1fr] gap-3 px-5 py-3.5">
                  <span
                    aria-hidden="true"
                    className="mt-0.5 flex h-7 w-7 items-center justify-center rounded-full bg-pine-soft text-sm font-bold tabular-nums text-pine-strong"
                  >
                    {index + 1}
                  </span>
                  <span>
                    <span className="block text-sm font-semibold text-ink">{step.title}</span>
                    <span className="mt-0.5 block text-sm leading-6 text-muted">{step.body}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section aria-label="Why Lucy" className="border-y border-line bg-white">
          <div className="mx-auto grid max-w-shell gap-8 px-4 py-12 md:grid-cols-3 md:px-8">
            {VALUES.map((value) => (
              <div key={value.title}>
                <h2 className="text-base font-semibold text-ink">{value.title}</h2>
                <p className="mt-2 text-sm leading-6 text-muted">{value.body}</p>
              </div>
            ))}
          </div>
        </section>

        <section aria-labelledby="scope-heading" className="mx-auto max-w-shell px-4 py-12 md:px-8">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] lg:items-start">
            <div>
              <h2 id="scope-heading" className="font-display text-2xl text-ink">
                Who Lucy is for
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted">
                Lucy is designed for this case. If yours is different, the prescreen tells you early.
              </p>
            </div>
            <ul className="grid gap-3 sm:grid-cols-2">
              {HAPPY_PATH.map((point) => (
                <li key={point} className={cx(cardClass, "flex items-start gap-3 px-4 py-3 text-sm font-medium text-ink")}>
                  <span aria-hidden="true" className="mt-0.5 text-pine">
                    {"✓"}
                  </span>
                  {point}
                </li>
              ))}
            </ul>
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-shell flex-col gap-2 px-4 py-6 text-sm text-muted sm:flex-row sm:justify-between md:px-8">
          <p>Lucy organizes information. It does not give legal advice.</p>
          <nav aria-label="Footer" className="flex gap-4">
            {NAV_LINKS.map((link) => (
              <Link key={link.href} href={link.href} className="font-semibold hover:text-ink">
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </footer>
    </div>
  );
}

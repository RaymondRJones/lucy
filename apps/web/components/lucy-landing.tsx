"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { clearSavedCaseId, getSavedCaseId } from "@/lib/case-storage";

const PROJECT_LINKS = [
  { href: "/prescreen", label: "Start packet" },
  { href: "/manage-tasks", label: "Checklist" },
  { href: "/packet-assembly", label: "Print packet" },
];

const HAPPY_PATH = [
  "U.S. citizen spouse petitioner",
  "Foreign spouse is already in the United States",
  "Marriage-based Form I-485 adjustment packet",
  "Simple first-marriage, no-children MVP path",
];

const PACKET_STEPS = ["Prescreen", "I-485", "I-864", "I-765", "I-131", "Mailing review"];

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
    <main className="min-h-screen bg-[#f7f7f2] text-ink">
      <nav className="mx-auto flex w-full max-w-7xl flex-col gap-3 px-4 py-5 md:flex-row md:items-center md:justify-between md:px-8">
        <Link href="/" className="font-display text-3xl font-semibold tracking-normal">
          Lucy
        </Link>
        <div className="flex flex-wrap gap-2">
          {PROJECT_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-lg border border-ink/15 bg-white px-3 py-2 text-sm font-semibold transition hover:border-pine/45"
            >
              {link.label}
            </Link>
          ))}
        </div>
      </nav>

      <section className="mx-auto grid w-full max-w-7xl gap-8 px-4 pb-8 pt-3 md:px-8 lg:grid-cols-[minmax(0,1fr)_440px] lg:items-center lg:pb-14">
        <div className="py-4">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-pine">
            Free local I-485 packet workspace
          </p>
          <h1 className="mt-4 font-display text-5xl leading-tight md:text-7xl">
            Lucy helps happy-path married couples prepare a mail-ready spouse packet.
          </h1>
          <p className="mt-5 max-w-3xl text-base leading-8 text-ink/72 md:text-lg">
            Lucy is a completely free, open-source application that runs on your own personal computer. It keeps
            your case data local while helping you answer the core questions, organize the forms, review gaps, and
            generate a printable Form I-485-centered packet for mailing. The local workflow includes intake,
            checklist, draft forms, evidence organization, packet review, and print-ready assembly.
          </p>
          <div className="mt-7 flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={startPacket}
              className="min-h-12 rounded-lg bg-ink px-5 py-3 text-left text-sm font-semibold text-white transition hover:bg-pine"
            >
              Start packet
            </button>
            <button
              type="button"
              onClick={resumePacket}
              className="min-h-12 rounded-lg border border-ink/15 bg-white px-5 py-3 text-left text-sm font-semibold text-ink transition hover:border-pine/45"
            >
              Continue / Resume
            </button>
          </div>
          <p className="mt-5 max-w-3xl text-xs leading-6 text-ink/55">
            Lucy is not legal advice. It is intentionally scoped to the common happy path: a U.S. citizen spouse and
            a foreign spouse residing in the United States. Unusual answers are flagged for review instead of being
            treated as a simple packet.
          </p>
        </div>

        <div className="overflow-hidden rounded-lg border border-ink/10 bg-white shadow-sm">
          <div className="border-b border-ink/10 bg-[#e6efe9] px-5 py-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-pine">Local workspace</p>
            <h2 className="mt-1 font-display text-2xl">I-485 packet draft</h2>
          </div>
          <div className="grid gap-3 p-5">
            {PACKET_STEPS.map((step, index) => (
              <div key={step} className="grid grid-cols-[2.5rem_1fr_auto] items-center gap-3 rounded-lg border border-ink/10 bg-paper/70 px-3 py-3">
                <span className="flex h-8 w-8 items-center justify-center rounded bg-white text-sm font-semibold text-pine">
                  {index + 1}
                </span>
                <span className="text-sm font-semibold">{step}</span>
                <span className="h-3 w-3 rounded-full bg-pine/70" />
              </div>
            ))}
          </div>
          <div className="grid grid-cols-3 border-t border-ink/10 bg-paper text-center text-xs font-semibold uppercase tracking-[0.12em] text-ink/55">
            <span className="border-r border-ink/10 px-2 py-3">Forms</span>
            <span className="border-r border-ink/10 px-2 py-3">Review</span>
            <span className="px-2 py-3">Mail</span>
          </div>
        </div>
      </section>

      <section className="mx-auto grid w-full max-w-7xl gap-4 px-4 pb-10 md:px-8 lg:grid-cols-3">
        <div className="rounded-lg border border-ink/10 bg-white p-5">
          <h2 className="font-display text-2xl">Free and open source</h2>
          <p className="mt-3 text-sm leading-7 text-ink/68">
            No subscription, no hosted account, and no paid filing service. The code and local workflow are meant to
            be inspectable, modifiable, and run from your own machine.
          </p>
        </div>
        <div className="rounded-lg border border-ink/10 bg-white p-5">
          <h2 className="font-display text-2xl">Built for one clear path</h2>
          <p className="mt-3 text-sm leading-7 text-ink/68">
            Lucy focuses on the happy-path married couple case so the questions, checklist, and document generation
            stay simple and predictable.
          </p>
        </div>
        <div className="rounded-lg border border-ink/10 bg-white p-5">
          <h2 className="font-display text-2xl">Ready to print and review</h2>
          <p className="mt-3 text-sm leading-7 text-ink/68">
            Generate draft USCIS forms, choose forms-only or full packet assembly, and review the mailing packet
            before anything is printed or sent.
          </p>
        </div>
      </section>

      <section className="mx-auto w-full max-w-7xl px-4 pb-14 md:px-8">
        <div className="rounded-lg border border-ink/10 bg-white p-5">
          <h2 className="font-display text-2xl">Happy-path scope</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {HAPPY_PATH.map((point) => (
              <div key={point} className="rounded-lg border border-ink/10 bg-paper/60 px-4 py-3 text-sm font-medium">
                {point}
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

import { Badge, cx } from "@/components/ui";
import { getCase } from "@/lib/api";

export type WorkflowStep = "prescreen" | "forms" | "checklist" | "review" | "packet";

const STEPS: Array<{ id: WorkflowStep; label: string; href: string }> = [
  { id: "prescreen", label: "Prescreen", href: "/prescreen" },
  { id: "forms", label: "Forms", href: "/i485-ingestion" },
  { id: "checklist", label: "Checklist", href: "/manage-tasks" },
  { id: "review", label: "Review", href: "/review" },
  { id: "packet", label: "Print packet", href: "/packet-assembly" },
];

function withCase(href: string, caseId?: string | null) {
  if (!caseId) {
    return href;
  }
  const separator = href.includes("?") ? "&" : "?";
  return `${href}${separator}caseId=${encodeURIComponent(caseId)}`;
}

function readinessTone(label?: string | null) {
  if (!label) {
    return "neutral" as const;
  }
  if (label.startsWith("Ready to print")) {
    return "success" as const;
  }
  if (label.startsWith("Not ready")) {
    return "danger" as const;
  }
  return "warning" as const;
}

export function AppShell({
  step,
  caseId,
  caseName,
  readinessLabel,
  children,
}: {
  step: WorkflowStep;
  caseId?: string | null;
  caseName?: string | null;
  readinessLabel?: string | null;
  children: ReactNode;
}) {
  const activeIndex = STEPS.findIndex((entry) => entry.id === step);
  const [fetchedCase, setFetchedCase] = useState<{ id: string; name: string; readiness: string } | null>(null);

  // Pages that only know the case ID still show which case is open.
  useEffect(() => {
    if (!caseId || caseName) {
      return;
    }
    let cancelled = false;
    getCase(caseId)
      .then((loaded) => {
        if (!cancelled) {
          setFetchedCase({ id: loaded.id, name: loaded.case_name, readiness: loaded.readiness_label });
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [caseId, caseName]);

  const fallback = fetchedCase && fetchedCase.id === caseId ? fetchedCase : null;
  const shownName = caseName ?? fallback?.name ?? null;
  const shownReadiness = readinessLabel ?? fallback?.readiness ?? null;
  return (
    <div className="min-h-screen bg-canvas text-ink">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:shadow-pop"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-30 border-b border-line bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/85">
        <div className="mx-auto flex max-w-shell items-center gap-4 px-4 py-2.5 md:px-8">
          <Link href="/" className="font-display text-2xl font-semibold leading-none text-ink">
            Lucy
          </Link>
          <nav aria-label="Packet steps" className="hidden flex-1 justify-center lg:flex">
            <StepList activeIndex={activeIndex} caseId={caseId} />
          </nav>
          <div className="ml-auto flex min-w-0 items-center gap-2 lg:ml-0">
            {shownName ? (
              <div className="flex min-w-0 items-center gap-2 rounded-lg border border-line bg-paper px-3 py-1.5">
                <span className="hidden text-xs font-semibold text-muted sm:inline">Case</span>
                <span className="max-w-[10rem] truncate text-sm font-semibold text-ink sm:max-w-[14rem]" title={shownName}>
                  {shownName}
                </span>
                {shownReadiness ? (
                  <Badge tone={readinessTone(shownReadiness)} className="hidden md:inline-flex">
                    {shownReadiness}
                  </Badge>
                ) : null}
              </div>
            ) : (
              <span className="text-sm text-muted">{caseId ? "" : "No case open"}</span>
            )}
          </div>
        </div>
        <nav aria-label="Packet steps" className="border-t border-line lg:hidden">
          <div className="relative mx-auto max-w-shell overflow-x-auto px-2 md:px-6">
            <StepList activeIndex={activeIndex} caseId={caseId} compact />
          </div>
        </nav>
      </header>
      <main id="main" className="mx-auto flex w-full max-w-shell flex-col gap-6 px-4 pb-16 pt-6 md:px-8 md:pt-8">
        {children}
      </main>
    </div>
  );
}

function StepList({ activeIndex, caseId, compact = false }: { activeIndex: number; caseId?: string | null; compact?: boolean }) {
  return (
    <ol className={cx("flex items-center", compact ? "gap-0.5 py-1.5" : "gap-1")}>
      {STEPS.map((entry, index) => {
        const isActive = index === activeIndex;
        const isPast = index < activeIndex;
        return (
          <li key={entry.id} className="flex items-center">
            {index > 0 && !compact ? <span aria-hidden="true" className="mx-1 h-px w-4 bg-line-strong" /> : null}
            <Link
              href={withCase(entry.href, caseId)}
              aria-current={isActive ? "step" : undefined}
              className={cx(
                "flex items-center gap-2 whitespace-nowrap rounded-lg px-2.5 py-1.5 text-sm font-semibold transition-colors",
                isActive ? "bg-pine-soft text-pine-strong" : "text-muted hover:bg-paper hover:text-ink",
              )}
            >
              <span
                aria-hidden="true"
                className={cx(
                  "flex h-5 w-5 items-center justify-center rounded-full text-[0.6875rem] font-bold tabular-nums",
                  isActive ? "bg-pine text-white" : isPast ? "bg-pine/15 text-pine-strong" : "border border-line-strong text-muted",
                )}
              >
                {index + 1}
              </span>
              {entry.label}
            </Link>
          </li>
        );
      })}
    </ol>
  );
}

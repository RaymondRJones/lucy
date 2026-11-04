"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

import { CaseSelector } from "@/components/case-selector";
import { Badge, Notice, ProgressBar, buttonClass, cardClass, cx } from "@/components/ui";
import { loadFormStatuses, type FormStatuses } from "@/lib/form-status";
import { packetFormHref, type PacketFormFlowOption } from "@/lib/packet-form-flow";
import type { CaseSummary } from "@/lib/types";

export function FormTabs({
  options,
  activeKey,
  caseId,
}: {
  options: PacketFormFlowOption[];
  activeKey: string;
  caseId?: string | null;
}) {
  const [statuses, setStatuses] = useState<{ caseId: string; value: FormStatuses } | null>(null);
  useEffect(() => {
    if (!caseId) {
      return;
    }
    let cancelled = false;
    loadFormStatuses(caseId)
      .then((value) => {
        if (!cancelled) {
          setStatuses({ caseId, value });
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [caseId]);
  const formStatuses = statuses && statuses.caseId === caseId ? statuses.value : {};

  function statusText(formKey: PacketFormFlowOption["formKey"]) {
    const status = formStatuses[formKey];
    if (!status) {
      return "";
    }
    return status.missing ? ` (${status.missing} left)` : " (done)";
  }

  return (
    <>
      <label className="grid gap-1.5 sm:hidden">
        <span className="text-sm font-semibold text-ink">Form</span>
        <select
          value={activeKey}
          onChange={(event) => window.location.assign(packetFormHref(event.target.value as PacketFormFlowOption["formKey"], caseId))}
          className="h-10 w-full rounded-lg border border-line-strong bg-white px-3 text-sm font-semibold text-ink"
        >
          {options.map((option) => (
            <option key={option.formKey} value={option.formKey}>
              {`${option.label}: ${option.detail}${statusText(option.formKey)}`}
            </option>
          ))}
        </select>
      </label>
      <nav aria-label="Packet forms" className="-mx-1 hidden overflow-x-auto px-1 sm:block">
        <ul className="relative flex min-w-max gap-1 border-b border-line">
          {options.map((option) => {
            const isActive = option.formKey === activeKey;
            return (
              <li key={option.formKey}>
                <Link
                  href={packetFormHref(option.formKey, caseId)}
                  aria-current={isActive ? "page" : undefined}
                  className={cx(
                    "-mb-px flex flex-col border-b-2 px-3 pb-2.5 pt-1 text-sm transition-colors",
                    isActive ? "border-pine text-ink" : "border-transparent text-muted hover:border-line-strong hover:text-ink",
                  )}
                >
                  <span className="flex items-center gap-1.5 font-semibold">
                    {option.label}
                    <FormStatusMark status={formStatuses[option.formKey]} />
                  </span>
                  <span className="text-xs">{option.detail}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </>
  );
}

function FormStatusMark({ status }: { status?: { missing: number } }) {
  if (!status) {
    return null;
  }
  if (status.missing) {
    return (
      <span className="rounded-full bg-amber-100 px-1.5 text-[0.6875rem] font-bold tabular-nums text-amber-900">
        {status.missing}
        <span className="sr-only"> required answers left</span>
      </span>
    );
  }
  return (
    <span className="text-pine" title="Every required answer is filled in">
      <span aria-hidden="true">{"\u2713"}</span>
      <span className="sr-only"> complete</span>
    </span>
  );
}

export function HelpPopover({ label, title, children }: { label: string; title: string; children: ReactNode }) {
  return (
    <details className="group/help relative">
      <summary
        aria-label={label}
        className="flex h-7 cursor-pointer list-none items-center gap-1 rounded-full border border-line-strong bg-white px-2.5 text-xs font-semibold text-pine transition-colors hover:border-pine group-open/help:border-pine group-open/help:bg-pine-soft [&::-webkit-details-marker]:hidden"
      >
        <span aria-hidden="true" className="font-bold">
          ?
        </span>
        Help
      </summary>
      <div className="absolute right-0 top-9 z-20 w-80 max-w-[calc(100vw-3rem)] rounded-lg border border-line bg-white p-3 text-left text-sm font-normal leading-6 text-ink shadow-pop">
        <p className="font-semibold text-ink">{title}</p>
        <div className="mt-1 text-ink/80">{children}</div>
      </div>
    </details>
  );
}

export function ComeBackToggle({
  flagged,
  onToggle,
  disabled,
  compact = false,
}: {
  flagged: boolean;
  onToggle: () => void;
  disabled?: boolean;
  compact?: boolean;
}) {
  return (
    <button
      type="button"
      aria-pressed={flagged}
      onClick={onToggle}
      disabled={disabled}
      title={flagged ? "You marked this to come back to. Select to clear the mark." : "Mark this question so it shows in your list to come back to."}
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full border font-semibold transition-colors disabled:opacity-50",
        flagged ? (compact ? "min-h-7 px-2 py-0.5 text-xs" : "min-h-8 px-2.5 py-1 text-xs") : "h-8 w-8 justify-center text-sm",
        flagged ? "border-amber-300 bg-amber-50 text-amber-900" : "border-line bg-white text-muted hover:border-line-strong hover:text-ink",
      )}
    >
      <span aria-hidden="true">{flagged ? "\u2691" : "\u2690"}</span>
      {flagged ? "Marked for later" : <span className="sr-only">Mark for later</span>}
    </button>
  );
}

export function QuestionCard({
  label,
  required,
  missing,
  flagged,
  actions,
  plainLanguage,
  children,
  meta,
  source,
  className,
}: {
  label: ReactNode;
  required?: boolean;
  missing?: boolean;
  flagged?: boolean;
  actions?: ReactNode;
  plainLanguage?: ReactNode;
  children: ReactNode;
  meta?: ReactNode;
  source?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "grid gap-3 bg-white transition-colors",
        missing
          ? "my-3 rounded-lg border border-clay/40 p-4 shadow-[inset_3px_0_0_0_#a8522f]"
          : flagged
            ? "my-3 rounded-lg border border-amber-300 p-4 shadow-[inset_3px_0_0_0_#d97706]"
            : "py-5",
        className,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
        <div className="min-w-0 flex-1 basis-64">
          <p className="text-sm font-semibold leading-6 text-ink">
            {label}
            {required ? (
              <span className="text-clay" aria-label="required">
                {" "}
                *
              </span>
            ) : null}
          </p>
          {plainLanguage ? <p className="mt-0.5 text-sm leading-6 text-muted">{plainLanguage}</p> : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {missing ? <Badge tone="danger">Missing</Badge> : null}
          {actions}
        </div>
      </div>
      {children}
      {meta || source ? (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
          {meta ? <span>{meta}</span> : null}
          {source ? <span className="font-semibold text-pine">{source}</span> : null}
        </div>
      ) : null}
    </div>
  );
}

// Backend readiness codes such as "ready for standard i485 review" read as plain status text.
function readinessText(value: string) {
  if (/^ready for standard/i.test(value)) {
    return "Required answers complete";
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export type PageNavItem = {
  id: string;
  title: string;
  subtitle?: string;
  missingCount: number;
  complete: boolean;
  flagCount: number;
};

export function PageNav({
  items,
  selectedId,
  onSelect,
  completionPct,
  statusLabel,
  stats,
}: {
  items: PageNavItem[];
  selectedId: string;
  onSelect: (id: string) => void;
  completionPct: number;
  statusLabel: string;
  stats?: Array<{ label: string; value: ReactNode; tone?: "danger" | "warning" }>;
}) {
  return (
    <aside className={cx(cardClass, "h-fit p-3 lg:sticky lg:top-20")}>
      <div className="px-2 pb-3 pt-1">
        <div className="flex items-center justify-between text-xs font-semibold text-muted">
          <span>{readinessText(statusLabel)}</span>
          <span className="tabular-nums">{completionPct}%</span>
        </div>
        <ProgressBar value={completionPct} label="Required answers complete" className="mt-1.5" />
        {stats?.length ? (
          <dl className="mt-2 flex flex-wrap gap-x-3 gap-y-0.5 text-xs">
            {stats.map((stat) => (
              <div key={stat.label} className="flex items-baseline gap-1">
                <dd
                  className={cx(
                    "order-1 font-semibold tabular-nums",
                    stat.tone === "danger" ? "text-red-800" : stat.tone === "warning" ? "text-amber-800" : "text-ink",
                  )}
                >
                  {stat.value}
                </dd>
                <dt className="order-2 text-muted">{stat.label}</dt>
              </div>
            ))}
          </dl>
        ) : null}
      </div>
      <label className="grid gap-1.5 px-2 pb-1 lg:hidden">
        <span className="text-sm font-semibold text-ink">Page</span>
        <select
          value={selectedId}
          onChange={(event) => onSelect(event.target.value)}
          className="h-10 w-full rounded-lg border border-line-strong bg-white px-3 text-sm text-ink"
        >
          {items.map((item, index) => (
            <option key={item.id} value={item.id}>
              {`${index + 1}. ${item.title}${item.missingCount ? ` (${item.missingCount} left)` : item.complete ? " (done)" : ""}`}
            </option>
          ))}
        </select>
      </label>
      <nav aria-label="Form pages" className="hidden lg:block">
        <ol className="relative flex flex-col gap-1 lg:max-h-[calc(100vh-12rem)] lg:overflow-y-auto">
          {items.map((item, index) => {
            const isSelected = item.id === selectedId;
            return (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => onSelect(item.id)}
                  aria-current={isSelected ? "step" : undefined}
                  className={cx(
                    "grid w-full grid-cols-[1.5rem_1fr_auto] items-start gap-2 rounded-lg px-2 py-2 text-left text-sm transition-colors",
                    isSelected ? "bg-pine-soft" : "hover:bg-paper",
                  )}
                >
                  <span
                    aria-hidden="true"
                    className={cx(
                      "mt-0.5 flex h-5 w-5 items-center justify-center rounded-full text-[0.6875rem] font-bold tabular-nums",
                      item.missingCount
                        ? "border border-clay/50 text-clay"
                        : item.complete
                          ? "bg-pine text-white"
                          : isSelected
                            ? "border border-pine text-pine"
                            : "border border-line-strong text-muted",
                    )}
                  >
                    {item.complete && !item.missingCount ? "\u2713" : index + 1}
                  </span>
                  <span className="min-w-0">
                    <span className={cx("block font-semibold leading-5", isSelected ? "text-pine-strong" : "text-ink")}>{item.title}</span>
                    {item.subtitle ? <span className="mt-0.5 block text-xs leading-4 text-muted">{item.subtitle}</span> : null}
                    <span className="sr-only">
                      {item.missingCount ? `, ${item.missingCount} missing` : item.complete ? ", complete" : ""}
                    </span>
                  </span>
                  <span className="flex flex-col items-end gap-1">
                    {item.missingCount ? (
                      <span className="text-xs font-semibold tabular-nums text-clay" aria-hidden="true">
                        {item.missingCount} left
                      </span>
                    ) : null}
                    {item.flagCount ? (
                      <span className="text-xs font-semibold text-amber-800" title={`${item.flagCount} marked to come back to`}>
                        {"\u2691"} {item.flagCount}
                      </span>
                    ) : null}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      </nav>
    </aside>
  );
}

export function CaseBar({
  caseId,
  onSelect,
  disabled,
  stats,
}: {
  caseId: string;
  onSelect: (caseSummary: CaseSummary) => void;
  disabled?: boolean;
  stats?: Array<{ label: string; value: ReactNode; tone?: "danger" | "warning" }>;
}) {
  return (
    <div
      className={cx(
        cardClass,
        "grid gap-3 p-4 md:grid-cols-[minmax(0,22rem)_minmax(0,1fr)] md:items-end md:gap-6",
        !caseId ? "border-amber-200 bg-amber-50" : "",
      )}
    >
      <CaseSelector selectedCaseId={caseId} onSelect={onSelect} disabled={disabled} label={caseId ? "Case" : "Choose a case to start"} />
      {stats?.length ? (
        <dl className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm md:justify-end md:pb-2">
          {stats.map((stat) => (
            <div key={stat.label} className="flex items-baseline gap-1.5">
              <dd
                className={cx(
                  "order-1 font-semibold tabular-nums",
                  stat.tone === "danger" ? "text-red-800" : stat.tone === "warning" ? "text-amber-800" : "text-ink",
                )}
              >
                {stat.value}
              </dd>
              <dt className="order-2 text-muted">{stat.label}</dt>
            </div>
          ))}
        </dl>
      ) : !caseId ? (
        <p className="text-sm leading-6 text-amber-950">Choose a saved case before answering. Answers save to that case.</p>
      ) : null}
    </div>
  );
}

export function MissingAnswers({
  items,
  hiddenCount,
  onSelect,
}: {
  items: Array<{ question_id: string; page_id: string; label: string }>;
  hiddenCount: number;
  onSelect: (pageId: string) => void;
}) {
  if (!items.length) {
    return null;
  }
  return (
    <Notice tone="warning" title={`${items.length + hiddenCount} required ${items.length + hiddenCount === 1 ? "answer" : "answers"} left`}>
      <div className="mt-2 flex flex-wrap gap-2">
        {items.map((item) => (
          <button
            key={item.question_id}
            type="button"
            onClick={() => onSelect(item.page_id)}
            className="max-w-full rounded-full border border-amber-300 bg-white px-3 py-1 text-left text-xs font-semibold text-amber-950 transition-colors hover:border-amber-500 hover:bg-amber-100"
          >
            {item.label}
          </button>
        ))}
        {hiddenCount ? (
          <span className="rounded-full px-2 py-1 text-xs font-semibold text-amber-900">+{hiddenCount} more in the page list</span>
        ) : null}
      </div>
    </Notice>
  );
}

export function ComeBackList({
  items,
  onSelect,
}: {
  items: Array<{ questionId: string; pageId: string; pageTitle: string; label: string }>;
  onSelect: (pageId: string) => void;
}) {
  if (!items.length) {
    return null;
  }
  return (
    <Notice tone="warning" title={`${items.length} marked to come back to`} className="mb-5">
      <div className="mt-2 flex flex-wrap gap-2">
        {items.map((item) => (
          <button
            key={item.questionId}
            type="button"
            onClick={() => onSelect(item.pageId)}
            className="max-w-full rounded-full border border-amber-300 bg-white px-3 py-1 text-left text-xs font-semibold text-amber-950 transition-colors hover:border-amber-500 hover:bg-amber-100"
          >
            {item.pageTitle}: {item.label}
          </button>
        ))}
      </div>
    </Notice>
  );
}

export function GeneratedPdfNotice({
  path,
  href,
  fieldCount,
  mappedCount,
  ready,
}: {
  path: string;
  href: string;
  fieldCount: number;
  mappedCount: number;
  ready: boolean;
}) {
  return (
    <Notice
      tone="success"
      title="Draft PDF ready"
      actions={
        <a href={href} target="_blank" rel="noreferrer" className={buttonClass("primary", "sm")}>
          Open PDF
        </a>
      }
    >
      <p>
        Filled {fieldCount} form fields from {mappedCount} answers.
        {ready ? "" : " Some required answers are still missing, so review this draft carefully."}
      </p>
      <p className="mt-1 break-all text-xs text-muted">{path}</p>
    </Notice>
  );
}

export function FormCompleteNotice({
  formCode,
  nextHref,
  nextLabel,
}: {
  formCode: string;
  nextHref: string;
  nextLabel: string;
}) {
  return (
    <Notice
      tone="success"
      title={`${formCode} has every required answer`}
      actions={
        <Link href={nextHref} className={buttonClass("secondary", "sm")}>
          {nextLabel} <span aria-hidden="true">{"\u2192"}</span>
        </Link>
      }
    >
      Preview the draft PDF from the top of the page, or move on to the next form.
    </Notice>
  );
}

export function SourcesDisclosure({
  version,
  verifiedOn,
  officialUrl,
  sources,
}: {
  version: string;
  verifiedOn: string;
  officialUrl?: string;
  sources: Array<{ label: string; url: string; notes?: string | null }>;
}) {
  return (
    <details className={cx(cardClass, "group p-0")}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-xl px-5 py-4 text-sm hover:bg-paper [&::-webkit-details-marker]:hidden">
        <span>
          <span className="font-semibold text-ink">Sources and version</span>
          <span className="ml-2 text-muted">Verified {verifiedOn}</span>
        </span>
        <span aria-hidden="true" className="text-muted transition-transform group-open:rotate-180">
          {"\u25BE"}
        </span>
      </summary>
      <div className="border-t border-line px-5 py-4">
        <p className="text-xs text-muted">Questionnaire version {version}</p>
        <ul className="mt-3 grid gap-3 md:grid-cols-3">
          {sources.map((source) => (
            <li key={source.label} className="rounded-lg border border-line bg-paper p-3 text-sm">
              {source.url.startsWith("http") ? (
                <a href={source.url} target="_blank" rel="noreferrer" className="font-semibold text-pine underline-offset-4 hover:underline">
                  {source.label}
                </a>
              ) : (
                <span className="font-semibold text-ink">{source.label}</span>
              )}
              {source.notes ? <p className="mt-1 leading-6 text-muted">{source.notes}</p> : null}
            </li>
          ))}
        </ul>
        {officialUrl ? (
          <a href={officialUrl} target="_blank" rel="noreferrer" className={buttonClass("ghost", "sm", "mt-3 -ml-3")}>
            Open the official USCIS page {"\u2197"}
          </a>
        ) : null}
      </div>
    </details>
  );
}

export function PageFooterActions({
  onSave,
  onSaveAndNext,
  onPrevious,
  isPending,
  isDirty = false,
  hasNext,
  disabled,
}: {
  onSave: () => void;
  onSaveAndNext: () => void;
  onPrevious?: () => void;
  isPending: boolean;
  isDirty?: boolean;
  hasNext: boolean;
  disabled?: boolean;
}) {
  return (
    <div className="-mx-5 -mb-5 mt-6 flex items-center justify-end gap-2 shadow-[0_-6px_16px_-12px_rgba(31,48,45,0.35)] sm:sticky sm:bottom-0 sm:z-10 rounded-b-xl border-t border-line bg-white/95 px-5 py-3 backdrop-blur md:-mx-6 md:-mb-6 md:px-6">
      <span className="mr-auto flex min-w-0 items-center gap-2 text-xs text-muted" aria-live="polite">
        {isDirty && !isPending ? <span aria-hidden="true" className="h-2 w-2 rounded-full bg-amber-500" /> : null}
        {isPending
          ? "Saving..."
          : isDirty
            ? (
              <>
                Unsaved changes<span className="hidden sm:inline">. Lucy also saves them when you switch pages.</span>
              </>
            ) : (
              <>
                <span aria-hidden="true" className="text-pine">
                  {"\u2713"}
                </span>
                Saved
              </>
            )}
      </span>
      {onPrevious ? (
        <button type="button" onClick={onPrevious} disabled={isPending} className={buttonClass("ghost", "md", "shrink-0")}>
          <span aria-hidden="true">{"\u2190"}</span>
          <span className="sr-only sm:not-sr-only">Previous</span>
        </button>
      ) : null}
      {isDirty || isPending ? (
        <button type="button" onClick={onSave} disabled={isPending || disabled} className={buttonClass("secondary", "md", "shrink-0")}>
          <span>
            Save<span className="hidden sm:inline"> page</span>
          </span>
        </button>
      ) : null}
      {hasNext ? (
        <button type="button" onClick={onSaveAndNext} disabled={isPending || disabled} className={buttonClass("primary", "md", "shrink-0")}>
          {isDirty ? "Save and continue" : "Next page"}
        </button>
      ) : null}
    </div>
  );
}

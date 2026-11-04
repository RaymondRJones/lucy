import Link from "next/link";
import type { ReactNode } from "react";

export function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

const BUTTON_BASE =
  "inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-pine text-white shadow-card hover:bg-pine-strong active:bg-pine-strong disabled:bg-line disabled:text-muted disabled:shadow-none disabled:opacity-100",
  secondary: "border border-line-strong bg-white text-ink shadow-card hover:border-ink/40 hover:bg-paper active:bg-line/60",
  ghost: "text-pine hover:bg-pine-soft active:bg-mist",
  danger: "border border-red-300 bg-white text-red-800 hover:bg-red-50 active:bg-red-100",
};

const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: "min-h-8 px-3 py-1.5 text-xs",
  md: "min-h-10 px-4 py-2 text-sm",
  lg: "min-h-12 px-5 py-3 text-base",
};

export function buttonClass(variant: ButtonVariant = "secondary", size: ButtonSize = "md", extra?: string) {
  return cx(BUTTON_BASE, BUTTON_VARIANTS[variant], BUTTON_SIZES[size], extra);
}

export const inputClass =
  "h-10 w-full rounded-lg border border-line-strong bg-white px-3 text-sm text-ink transition-colors hover:border-ink/40 disabled:cursor-not-allowed disabled:bg-paper disabled:text-muted";
export const selectClass = inputClass;
export const textareaClass =
  "w-full rounded-lg border border-line-strong bg-white px-3 py-2 text-sm leading-6 text-ink transition-colors hover:border-ink/40";
export const labelClass = "text-sm font-semibold text-ink";
export const hintClass = "text-xs leading-5 text-muted";
export const eyebrowClass = "text-xs font-semibold uppercase tracking-[0.12em] text-pine";
export const cardClass = "rounded-xl border border-line bg-white shadow-card";

export function Card({
  children,
  className,
  as: Tag = "section",
  ...rest
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "aside" | "article";
  id?: string;
  "aria-labelledby"?: string;
}) {
  return (
    <Tag className={cx(cardClass, "p-5 md:p-6", className)} {...rest}>
      {children}
    </Tag>
  );
}

export function SectionHeader({
  title,
  description,
  eyebrow,
  actions,
  id,
  level = 2,
}: {
  title: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  actions?: ReactNode;
  id?: string;
  level?: 2 | 3;
}) {
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        {eyebrow ? <p className={eyebrowClass}>{eyebrow}</p> : null}
        <Heading id={id} className={cx("font-semibold text-ink", level === 2 ? "text-lg" : "text-base", eyebrow ? "mt-1" : "")}>
          {title}
        </Heading>
        {description ? <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0">
        {eyebrow ? <p className={eyebrowClass}>{eyebrow}</p> : null}
        <h1 className="mt-1 font-display text-3xl leading-tight text-ink md:text-4xl">{title}</h1>
        {description ? <p className="mt-2 max-w-3xl text-[15px] leading-7 text-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}

type Tone = "neutral" | "strong" | "success" | "warning" | "danger" | "info" | "accent";

const BADGE_TONES: Record<Tone, string> = {
  neutral: "border-line bg-paper text-muted",
  strong: "border-ink bg-ink text-white",
  success: "border-pine/20 bg-pine-soft text-pine-strong",
  warning: "border-amber-200 bg-amber-50 text-amber-900",
  danger: "border-red-200 bg-red-50 text-red-800",
  info: "border-sky-200 bg-sky-50 text-sky-900",
  accent: "border-pine bg-pine text-white",
};

export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span
      className={cx(
        "inline-flex items-center whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-semibold leading-5",
        BADGE_TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

const NOTICE_TONES: Record<Tone, string> = {
  neutral: "border-line bg-white text-ink",
  strong: "border-line-strong bg-white text-ink",
  success: "border-pine/25 bg-pine-soft text-ink",
  warning: "border-amber-200 bg-amber-50 text-amber-950",
  danger: "border-red-200 bg-red-50 text-red-950",
  info: "border-sky-200 bg-sky-50 text-sky-950",
  accent: "border-pine bg-pine text-white",
};

export function Notice({
  tone = "neutral",
  title,
  children,
  className,
  actions,
}: {
  tone?: Tone;
  title?: ReactNode;
  children?: ReactNode;
  className?: string;
  actions?: ReactNode;
}) {
  return (
    <div className={cx("rounded-lg border px-4 py-3 text-sm leading-6", NOTICE_TONES[tone], className)}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          {title ? <p className="font-semibold">{title}</p> : null}
          {children ? <div className={title ? "mt-0.5" : ""}>{children}</div> : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
      </div>
    </div>
  );
}

const ERROR_PATTERN = /(could not|failed|error|unable|not found|invalid|refused)/i;
const WARNING_PATTERN = /(skipped|no payment|not added|need attention)/i;
const UNREACHABLE_PATTERN = /could not reach the lucy api/i;

// Status line for the result of the last action. Errors are announced assertively; warnings stand out in amber.
export function StatusMessage({ message, className }: { message: string | null | undefined; className?: string }) {
  if (!message) {
    return null;
  }
  const isError = ERROR_PATTERN.test(message);
  const isWarning = !isError && WARNING_PATTERN.test(message);
  return (
    <div
      role={isError ? "alert" : "status"}
      aria-live={isError ? "assertive" : "polite"}
      className={cx(
        "flex flex-wrap items-start gap-x-2 gap-y-2 rounded-lg border px-3 py-2 text-sm leading-6",
        isError ? "border-red-200 bg-red-50 text-red-900" : isWarning ? "border-amber-200 bg-amber-50 text-amber-950" : "border-line bg-white text-muted",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cx("mt-2 h-1.5 w-1.5 shrink-0 rounded-full", isError ? "bg-red-600" : isWarning ? "bg-amber-500" : "bg-pine")}
      />
      <span className="min-w-0 flex-1">{message}</span>
      {UNREACHABLE_PATTERN.test(message) ? (
        <button type="button" onClick={() => window.location.reload()} className={buttonClass("secondary", "sm")}>
          Try again
        </button>
      ) : null}
    </div>
  );
}

export function ProgressBar({ value, label, className }: { value: number; label: string; className?: string }) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={clamped}
      className={cx("h-2 overflow-hidden rounded-full bg-line", className)}
    >
      <div className="h-full rounded-full bg-pine transition-[width] duration-300" style={{ width: `${clamped}%` }} />
    </div>
  );
}

export function Stat({ label, value, detail, tone = "neutral" }: { label: string; value: ReactNode; detail?: ReactNode; tone?: Tone }) {
  return (
    <div className={cx("rounded-lg border px-4 py-3", tone === "danger" ? "border-red-200 bg-red-50" : tone === "warning" ? "border-amber-200 bg-amber-50" : "border-line bg-paper")}>
      <p className="text-xs font-semibold text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-ink">{value}</p>
      {detail ? <p className="mt-0.5 text-xs leading-5 text-muted">{detail}</p> : null}
    </div>
  );
}

export function TextLink({ href, children, className }: { href: string; children: ReactNode; className?: string }) {
  return (
    <Link href={href} className={cx("font-semibold text-pine underline-offset-4 hover:underline", className)}>
      {children}
    </Link>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cx("inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent", className)}
    />
  );
}

export function LoadingState({ label }: { label: string }) {
  return (
    <div role="status" className="flex items-center gap-3 rounded-xl border border-line bg-white px-5 py-6 text-sm text-muted shadow-card">
      <Spinner className="text-pine" />
      {label}
    </div>
  );
}

// Yes/No choice that exposes its selected state to assistive technology.
export function YesNoControl({
  value,
  onChange,
  label,
  className,
}: {
  value: unknown;
  onChange: (value: boolean) => void;
  label: string;
  className?: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className={cx("grid w-full grid-cols-2 gap-2 justify-self-start sm:w-72", className)}>
      {[
        { value: true, text: "Yes" },
        { value: false, text: "No" },
      ].map((option) => {
        const selected = value === option.value;
        return (
          <button
            key={option.text}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(option.value)}
            className={cx(
              "flex h-10 items-center justify-center gap-2 rounded-lg border px-4 text-sm font-semibold transition-colors",
              selected
                ? "border-pine bg-pine-soft text-pine-strong ring-1 ring-pine"
                : "border-line-strong bg-white text-ink hover:border-ink/40 hover:bg-paper",
            )}
          >
            <span
              aria-hidden="true"
              className={cx(
                "flex h-4 w-4 items-center justify-center rounded-full border",
                selected ? "border-pine bg-white" : "border-line-strong",
              )}
            >
              {selected ? <span className="h-2 w-2 rounded-full bg-pine" /> : null}
            </span>
            {option.text}
          </button>
        );
      })}
    </div>
  );
}

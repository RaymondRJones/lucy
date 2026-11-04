import Link from "next/link";
import type { ReactNode } from "react";

import { buttonClass, cardClass, cx, eyebrowClass } from "@/components/ui";

type PublicPageProps = {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
};

const PUBLIC_LINKS = [
  { href: "/how-it-works", label: "How it works" },
  { href: "/legal-disclaimer", label: "Not legal advice" },
];

export function PublicPage({ eyebrow, title, description, children }: PublicPageProps) {
  return (
    <div className="min-h-screen bg-canvas text-ink">
      <header className="border-b border-line bg-white/80">
        <nav aria-label="Main" className="mx-auto flex max-w-shell items-center gap-4 px-4 py-3 md:px-8">
          <Link href="/" className="font-display text-2xl font-semibold leading-none">
            Lucy
          </Link>
          <ul className="ml-auto hidden items-center gap-1 sm:flex">
            {PUBLIC_LINKS.map((link) => (
              <li key={link.href}>
                <Link href={link.href} className="rounded-lg px-3 py-2 text-sm font-semibold text-muted transition-colors hover:bg-paper hover:text-ink">
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
          <Link href="/prescreen" className={buttonClass("primary", "sm", "ml-auto sm:ml-2")}>
            Start a packet
          </Link>
        </nav>
      </header>

      <main id="main" className="mx-auto flex max-w-shell flex-col gap-8 px-4 pb-16 pt-10 md:px-8 md:pt-14">
        <section className="max-w-3xl">
          <p className={eyebrowClass}>{eyebrow}</p>
          <h1 className="mt-3 font-display text-4xl leading-tight text-ink md:text-5xl">{title}</h1>
          <p className="mt-4 text-lg leading-8 text-muted">{description}</p>
        </section>
        {children}
      </main>
    </div>
  );
}

export function PublicCard({
  title,
  children,
  eyebrow,
}: {
  title: string;
  children: ReactNode;
  eyebrow?: string;
}) {
  return (
    <section className={cx(cardClass, "p-6")}>
      {eyebrow ? <p className={eyebrowClass}>{eyebrow}</p> : null}
      <h2 className="mt-1 text-lg font-semibold text-ink">{title}</h2>
      <div className="mt-3 text-sm leading-7 text-muted">{children}</div>
    </section>
  );
}

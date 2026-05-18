import Link from "next/link";
import type { ReactNode } from "react";

type PublicPageProps = {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
};

const PUBLIC_LINKS = [
  { href: "/", label: "Home" },
  { href: "/prescreen", label: "Prescreen" },
  { href: "/packet-assembly", label: "Packet assembly" },
  { href: "/manage-tasks", label: "Tasks" },
];

export function PublicPage({ eyebrow, title, description, children }: PublicPageProps) {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-8 px-4 py-6 md:px-8 md:py-8">
      <nav className="flex flex-col gap-4 rounded-full border border-white/60 bg-white/82 px-5 py-3 shadow-sm backdrop-blur md:flex-row md:items-center md:justify-between">
        <Link href="/" className="font-display text-xl text-ink">
          Lucy
        </Link>
        <div className="flex flex-wrap gap-2">
          {PUBLIC_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-full px-3 py-2 text-sm font-semibold text-ink/68 transition hover:bg-paper hover:text-ink"
            >
              {link.label}
            </Link>
          ))}
        </div>
      </nav>

      <section className="relative overflow-hidden rounded-[2.6rem] border border-white/60 bg-gradient-to-br from-paper via-[#fbf7ef] to-mist px-6 py-12 shadow-panel md:px-10 md:py-16">
        <div className="absolute inset-y-0 right-0 w-1/2 bg-[radial-gradient(circle_at_top,rgba(37,103,93,0.16),transparent_54%)]" />
        <div className="relative z-10 max-w-4xl">
          <p className="text-xs uppercase tracking-[0.3em] text-pine/75">{eyebrow}</p>
          <h1 className="mt-4 font-display text-4xl leading-tight text-ink md:text-6xl">{title}</h1>
          <p className="mt-5 max-w-3xl text-base leading-8 text-ink/72 md:text-lg">{description}</p>
        </div>
      </section>

      {children}
    </main>
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
    <section className="rounded-[2rem] border border-white/60 bg-white/78 p-6 shadow-panel backdrop-blur">
      {eyebrow ? <p className="text-xs uppercase tracking-[0.24em] text-pine/80">{eyebrow}</p> : null}
      <h2 className="mt-1 font-display text-2xl text-ink">{title}</h2>
      <div className="mt-4 text-sm leading-7 text-ink/72">{children}</div>
    </section>
  );
}

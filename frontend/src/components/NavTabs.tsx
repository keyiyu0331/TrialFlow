"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "Dashboard", match: (p: string) => p === "/" || p.startsWith("/sites") },
  { href: "/tasks", label: "My tasks", match: (p: string) => p.startsWith("/tasks") },
  { href: "/trials", label: "Trials", match: (p: string) => p.startsWith("/trials") },
];

export default function NavTabs() {
  const pathname = usePathname();
  return (
    <nav className="tabs" aria-label="Primary">
      {TABS.map((t) => (
        <Link key={t.href} href={t.href} className={`tab ${t.match(pathname) ? "tab--active" : ""}`}>
          {t.label}
        </Link>
      ))}
    </nav>
  );
}

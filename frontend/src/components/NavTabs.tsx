"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "Dashboard", match: (p: string) => p === "/" || p.startsWith("/sites") },
  { href: "/brief", label: "Daily brief", match: (p: string) => p.startsWith("/brief") },
  { href: "/tasks", label: "My tasks", match: (p: string) => p.startsWith("/tasks") },
  { href: "/trials", label: "Trials", match: (p: string) => p.startsWith("/trials") },
];

export default function NavTabs({ sponsor }: { sponsor: boolean }) {
  const pathname = usePathname();
  const tabs = sponsor ? TABS : TABS.filter((t) => t.href === "/tasks");
  return (
    <nav className="tabs" aria-label="Primary">
      {tabs.map((t) => (
        <Link key={t.href} href={t.href} className={`tab ${t.match(pathname) ? "tab--active" : ""}`}>
          {t.label}
        </Link>
      ))}
    </nav>
  );
}

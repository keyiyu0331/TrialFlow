"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMe } from "./SessionProvider";

interface Hit {
  label: string;
  sub?: string;
  run: () => void;
  group: string;
}
interface SiteRef {
  id: number;
  name: string;
  sub: string;
  health: string;
}

const PAGES = [
  { label: "Dashboard", href: "/", sponsor: true },
  { label: "Daily brief", href: "/brief", sponsor: true },
  { label: "Insights", href: "/insights", sponsor: true },
  { label: "Trials", href: "/trials", sponsor: true },
  { label: "My tasks", href: "/tasks", sponsor: false },
];

/** ⌘K / Ctrl+K: jump to any page or site, or ask TrialFlow a question. */
export default function CommandPalette() {
  const router = useRouter();
  const { me } = useMe();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [sites, setSites] = useState<SiteRef[] | null>(null);
  const [i, setI] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!open) return;
    setQ("");
    setI(0);
    setTimeout(() => input.current?.focus(), 0);
  }, [open]);

  useEffect(() => {
    if (open && sites === null) fetch("/api/palette").then((r) => r.json()).then((d) => setSites(d.sites ?? [])).catch(() => setSites([]));
  }, [open, sites]);

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  const hits = useMemo<Hit[]>(() => {
    const needle = q.trim().toLowerCase();
    const pages = PAGES.filter((p) => (me?.sponsor || !p.sponsor) && (!needle || p.label.toLowerCase().includes(needle))).map<Hit>((p) => ({
      group: "Go to",
      label: p.label,
      run: () => go(p.href),
    }));
    const found = (sites ?? [])
      .filter((s) => needle && `${s.name} ${s.sub}`.toLowerCase().includes(needle))
      .slice(0, 6)
      .map<Hit>((s) => ({ group: "Sites", label: s.name, sub: s.sub, run: () => go(`/sites/${s.id}`) }));
    const ask: Hit[] = needle
      ? [{ group: "Ask", label: `Ask TrialFlow: “${q.trim()}”`, run: () => { setOpen(false); window.dispatchEvent(new CustomEvent("tf:ask", { detail: q.trim() })); } }]
      : [];
    return [...found, ...pages, ...ask];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, sites, me]);

  if (!open) {
    return (
      <button className="kbtn" onClick={() => setOpen(true)} aria-label="Search and jump (Ctrl K)">
        <span>Search</span>
        <kbd>⌘K</kbd>
      </button>
    );
  }

  return (
    <div className="pal" onMouseDown={(e) => e.target === e.currentTarget && setOpen(false)}>
      <div className="pal__box" role="dialog" aria-label="Search and jump">
        <input
          ref={input}
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setI(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setI((x) => Math.min(x + 1, hits.length - 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setI((x) => Math.max(x - 1, 0)); }
            else if (e.key === "Enter") hits[i]?.run();
          }}
          placeholder="Jump to a site or page, or ask a question…"
          aria-label="Search"
        />
        <ul className="pal__list">
          {hits.map((h, idx) => (
            <li key={h.group + h.label} className={idx === i ? "on" : ""} onMouseEnter={() => setI(idx)} onClick={h.run}>
              <small>{h.group}</small>
              <span>{h.label}</span>
              {h.sub && <em>{h.sub}</em>}
            </li>
          ))}
          {hits.length === 0 && <li className="pal__empty">{sites === null ? "Loading sites…" : "No matches"}</li>}
        </ul>
        <div className="pal__foot">↑↓ to move · Enter to open · Esc to close</div>
      </div>
    </div>
  );
}

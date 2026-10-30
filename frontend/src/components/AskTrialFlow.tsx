"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { Answer } from "@/lib/ask";

interface Msg {
  from: "you" | "tf";
  text: string;
  links?: Answer["links"];
  follow?: string[];
}

const START = [
  "What should I chase today?",
  "Which sites are blocked?",
  "What's overdue?",
  "Which sites will miss their target?",
];

/** Floating chat. Read-only: it answers from live status and never changes a milestone. */
export default function AskTrialFlow() {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [q, setQ] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => end.current?.scrollIntoView({ block: "end" }), [msgs, busy]);

  const askRef = useRef<(t: string) => void>(() => {});
  useEffect(() => {
    const on = (e: Event) => {
      setOpen(true);
      setTimeout(() => askRef.current(String((e as CustomEvent).detail ?? "")), 0);
    };
    window.addEventListener("tf:ask", on);
    return () => window.removeEventListener("tf:ask", on);
  }, []);

  async function ask(text: string) {
    const question = text.trim();
    if (!question || busy) return;
    setQ("");
    setMsgs((m) => [...m, { from: "you", text: question }]);
    setBusy(true);
    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const a: Answer = await res.json();
      setMsgs((m) => [...m, { from: "tf", text: a.text, links: a.links, follow: a.follow }]);
    } catch {
      setMsgs((m) => [...m, { from: "tf", text: "I couldn't reach the server. Try again in a moment." }]);
    }
    setBusy(false);
  }

  askRef.current = ask;

  if (!open) {
    return (
      <button className="ask-fab" onClick={() => setOpen(true)} aria-label="Ask TrialFlow">
        <span className="ask-fab__dot" /> Ask TrialFlow
      </button>
    );
  }

  return (
    <section className="ask" aria-label="Ask TrialFlow">
      <header className="ask__head">
        <div>
          <strong>Ask TrialFlow</strong>
          <div className="ask__sub">Answers from live data · never changes anything</div>
        </div>
        <button className="ask__x" onClick={() => setOpen(false)} aria-label="Close">
          ×
        </button>
      </header>
      <div className="ask__body">
        {msgs.length === 0 && (
          <div className="ask__intro">
            <p>Ask about any site, person or step in plain English.</p>
            <div className="ask__chips">
              {START.map((s) => (
                <button key={s} onClick={() => ask(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`ask__msg ask__msg--${m.from}`}>
            <p>{m.text}</p>
            {m.links && m.links.length > 0 && (
              <ul className="ask__links">
                {m.links.map((l) => (
                  <li key={l.href + l.label}>
                    <Link href={l.href} onClick={() => setOpen(false)}>
                      <span>{l.label}</span>
                      {l.sub && <small>{l.sub}</small>}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            {m.follow && m.follow.length > 0 && (
              <div className="ask__chips">
                {m.follow.map((s) => (
                  <button key={s} onClick={() => ask(s)}>
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="ask__msg ask__msg--tf ask__typing">Checking the data…</div>}
        <div ref={end} />
      </div>
      <form
        className="ask__form"
        onSubmit={(e) => {
          e.preventDefault();
          ask(q);
        }}
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="e.g. what's holding up Oxford?"
          aria-label="Your question"
          maxLength={300}
        />
        <button className="btn btn--primary" disabled={busy || !q.trim()}>
          Ask
        </button>
      </form>
    </section>
  );
}

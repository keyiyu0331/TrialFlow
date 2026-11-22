"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { DocumentAnalysis } from "@/lib/api";
import type { Answer } from "@/lib/ask";

interface Msg {
  from: "you" | "tf";
  text: string;
  links?: Answer["links"];
  follow?: string[];
  doc?: DocumentAnalysis;
}

const START = [
  "What should I chase today?",
  "Which sites are blocked?",
  "What's overdue?",
  "Which sites will miss their target?",
];

/** Earlier messages sent with each question (the server keeps no chat history). */
const HISTORY = 10;

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
  // biome-ignore lint/correctness/useExhaustiveDependencies: msgs and busy are triggers; scroll whenever a message or the typing row appears.
  useEffect(() => {
    // Braces matter: an effect must not return scrollIntoView's result, or React treats it as a cleanup function.
    end.current?.scrollIntoView({ block: "end" });
  }, [msgs, busy]);

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
    // The conversation so far (before this question), so follow-ups like "who owns that?" have context.
    const history = msgs.slice(-HISTORY).map((m) => ({ role: m.from === "you" ? "user" : "assistant", text: m.text }));
    // The latest uploaded document goes in its own field, so both answer paths can use it for follow-ups.
    const doc = msgs.findLast((m) => m.doc)?.doc;
    const document = doc && {
      filename: doc.filename,
      category_label: doc.category_label,
      title: doc.title,
      summary: doc.summary,
      key_facts: doc.key_facts,
    };
    setQ("");
    setMsgs((m) => [...m, { from: "you", text: question }]);
    setBusy(true);
    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, history, document }),
      });
      const a: Answer = await res.json();
      setMsgs((m) => [...m, { from: "tf", text: a.text, links: a.links, follow: a.follow }]);
    } catch {
      setMsgs((m) => [...m, { from: "tf", text: "I couldn't reach the server. Try again in a moment." }]);
    }
    setBusy(false);
  }

  const fileRef = useRef<HTMLInputElement>(null);

  /** Summarize and categorize an uploaded document. Read-only: it suggests, and changes nothing. */
  async function upload(file: File) {
    if (busy) return;
    setMsgs((m) => [...m, { from: "you", text: `Attached: ${file.name}` }]);
    setBusy(true);
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await fetch("/api/ask/document", { method: "POST", body });
      const data = await res.json();
      if (res.ok) {
        setMsgs((m) => [...m, { from: "tf", text: "Here is what I found in that document.", doc: data }]);
      } else {
        setMsgs((m) => [...m, { from: "tf", text: data.detail ?? "I couldn't read that file." }]);
      }
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
            <p>Ask about any site, person or step in plain English, or attach a document to summarize.</p>
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
            {m.doc && <DocCard doc={m.doc} />}
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
        {busy && <div className="ask__msg ask__msg--tf ask__typing">Working on it…</div>}
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
          ref={fileRef}
          type="file"
          accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (f) upload(f);
          }}
        />
        <button
          type="button"
          className="ask__attach"
          onClick={() => fileRef.current?.click()}
          disabled={busy}
          aria-label="Attach a document (PDF, .txt or .md)"
          title="Attach an IRB letter, contract or other site document"
        >
          📎
        </button>
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

/** What the assistant found in an uploaded document. Suggestion only. */
function DocCard({ doc }: { doc: DocumentAnalysis }) {
  return (
    <div className="ask__doc">
      <div className="ask__doc-head">
        <span className="tag">{doc.category_label}</span>
        <small>{doc.filename}</small>
      </div>
      <strong>{doc.title}</strong>
      <p>{doc.summary}</p>
      {doc.key_facts.length > 0 && (
        <dl className="ask__facts">
          {doc.key_facts.map((f, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: facts can repeat, and the list never reorders
            <div key={`${i}-${f.label}-${f.value}`}>
              <dt>{f.label}</dt>
              <dd title={`"${f.quote}"`}>{f.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {doc.related_milestone && <p className="ask__doc-note">Usually evidence for: {doc.related_milestone}.</p>}
      <p className="ask__doc-note">
        {doc.source === "claude" ? "Summarized by Claude." : "Rule-based summary (no Claude connection)."} A suggestion
        only: nothing in TrialFlow was changed.
        {doc.truncated && " Only the start of a long document was read."}
      </p>
    </div>
  );
}

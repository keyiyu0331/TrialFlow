"use client";

import { useEffect, useState } from "react";
import { HealthChip } from "@/components/Chips";
import { type Milestone, simulateWhatIf, type WhatIfAssumption, type WhatIfResult } from "@/lib/api";
import { fmtDate, plural } from "@/lib/format";

/** Local calendar day as YYYY-MM-DD, `days` from today. */
function isoDay(days = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function endOfMonth(): string {
  const d = new Date();
  const last = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  return isoDay(Math.max(0, Math.round((last.getTime() - d.getTime()) / 86_400_000)));
}

function deltaText(days: number | null): { text: string; tone: "ok" | "late" | "same" } {
  if (days === null) return { text: "No green light step", tone: "same" };
  if (days < 0) return { text: `${plural(-days, "day")} earlier`, tone: "ok" };
  if (days > 0) return { text: `${plural(days, "day")} later`, tone: "late" };
  return { text: "No change", tone: "same" };
}

const slip = (d: number) => (d > 0 ? `+${d}d late` : "on time");

/**
 * Planning tool (rule D15): "what if this step finished on that date?". Shows how the projected green light
 * and the slipping steps would move. Practice only: it calls a read-only endpoint and changes nothing.
 */
export default function WhatIf({
  trialSiteId,
  milestones,
  topBlockerId,
}: {
  trialSiteId: number;
  milestones: Milestone[];
  topBlockerId: number | null;
}) {
  const open = milestones.filter((m) => m.status !== "complete" && m.status !== "not_applicable");
  const first = open.find((m) => m.id === topBlockerId) ?? open[0];
  const [pick, setPick] = useState<number | undefined>(first?.id);
  const [date, setDate] = useState(isoDay(7));
  const [assumptions, setAssumptions] = useState<WhatIfAssumption[]>([]);
  const [result, setResult] = useState<WhatIfResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (assumptions.length === 0) {
      setResult(null);
      setError(null);
      return;
    }
    let stale = false;
    setBusy(true);
    simulateWhatIf(trialSiteId, assumptions).then((r) => {
      if (stale) return;
      setBusy(false);
      if ("result" in r) {
        setResult(r.result);
        setError(null);
      } else {
        setError(r.error);
      }
    });
    return () => {
      stale = true;
    };
  }, [assumptions, trialSiteId]);

  if (open.length === 0) return null;
  const name = (id: number) => milestones.find((m) => m.id === id)?.name ?? `Milestone ${id}`;

  function add() {
    if (pick === undefined || !date) return;
    setAssumptions((list) => {
      const others = list.filter((a) => a.milestone_id !== pick);
      return [...others, { milestone_id: pick, finish_date: date }].slice(-5);
    });
  }

  const delta = result ? deltaText(result.delta_days) : null;
  // Late steps the user dated today: the page already assumes that, so it is the best case for them.
  const bestCase = result
    ? assumptions
        .filter((a) => a.finish_date === result.as_of)
        .map((a) => milestones.find((m) => m.id === a.milestone_id))
        .filter((m): m is Milestone => !!m && m.days_overdue > 0)
    : [];
  const recovered = result?.changed.filter((m) => !m.assumed && m.baseline_slip_days > 0 && m.slip_days === 0) ?? [];
  const slipping = result?.changed.filter((m) => !m.assumed && m.slip_days > 0) ?? [];
  const assumed = result?.changed.filter((m) => m.assumed) ?? [];

  return (
    <section className="card panel whatif">
      <div className="panel__head">
        <div>
          <div className="label">Planning</div>
          <h2 className="panel__title">What if a step finished on a different date?</h2>
        </div>
        <span className="tag">Simulation only · nothing is saved</span>
      </div>

      <div className="whatif__form">
        <label>
          <span className="label">Step</span>
          <select className="select" value={pick} onChange={(e) => setPick(Number(e.target.value))}>
            {open.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
                {m.days_overdue > 0 ? ` (${m.days_overdue}d late)` : ""}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="label">Finishes on</span>
          <input
            className="select"
            type="date"
            value={date}
            min={isoDay(0)}
            onChange={(e) => setDate(e.target.value)}
          />
        </label>
        <div className="whatif__quick">
          <button type="button" className="btn" onClick={() => setDate(isoDay(7))}>
            +1 week
          </button>
          <button type="button" className="btn" onClick={() => setDate(isoDay(14))}>
            +2 weeks
          </button>
          <button type="button" className="btn" onClick={() => setDate(endOfMonth())}>
            End of month
          </button>
        </div>
        <button type="button" className="btn btn--primary" onClick={add} disabled={pick === undefined || !date}>
          Try it
        </button>
      </div>

      {assumptions.length > 0 && (
        <div className="whatif__chips">
          {assumptions.map((a) => (
            <span key={a.milestone_id} className="whatif__chip">
              {name(a.milestone_id)} done {fmtDate(a.finish_date, true)}
              <button
                type="button"
                aria-label={`Remove ${name(a.milestone_id)}`}
                onClick={() => setAssumptions((list) => list.filter((x) => x.milestone_id !== a.milestone_id))}
              >
                ×
              </button>
            </span>
          ))}
          <button type="button" className="btn-ghost whatif__reset" onClick={() => setAssumptions([])}>
            Reset
          </button>
        </div>
      )}

      {error && <div className="notice">{error}</div>}
      {assumptions.length === 0 && (
        <p className="data-note">
          Pick a step and a date to see when this site would go live. Add up to five steps to combine them. Today's
          projection assumes every late step finishes today, so a realistic date for a late step shows how far go-live
          really slips.
        </p>
      )}

      {result && delta && (
        <div className={`whatif__result ${busy ? "whatif__result--busy" : ""}`}>
          <div className="whatif__headline">
            <div>
              <div className="label">Green light</div>
              <div className="whatif__dates mono">
                <span>{fmtDate(result.baseline_activation_date, true)}</span>
                <span aria-hidden>→</span>
                <strong>{fmtDate(result.projected_activation_date, true)}</strong>
              </div>
            </div>
            <span className={`whatif__delta whatif__delta--${delta.tone}`}>{delta.text}</span>
            <div className="whatif__health">
              <HealthChip health={result.baseline_health} />
              <span aria-hidden>→</span>
              <HealthChip health={result.health} />
            </div>
          </div>
          {result.delta_days === 0 && bestCase.length > 0 && (
            <p className="whatif__note whatif__note--best">
              This is already the best case. {bestCase.map((m) => m.name).join(" and ")}{" "}
              {bestCase.length === 1 ? "is" : "are"} late, so today's projection already assumes{" "}
              {bestCase.length === 1 ? "it finishes" : "they finish"} today, the earliest possible date. A later date
              shows how much a realistic finish would push go-live out.
            </p>
          )}
          <p className="whatif__note">
            {result.site_slip_days > 0
              ? `Still ${plural(result.site_slip_days, "day")} past the target go-live.`
              : result.baseline_site_slip_days > 0
                ? "Back on target: the site would go live by its target date."
                : "On target."}
            {(result.delta_days ?? 0) > 0 &&
              " Today's projection assumes late steps finish today, so a later date for them pushes go-live out."}
            {result.still_blocked &&
              " The site stays blocked today: this only shows the dates if the late work gets done as assumed."}
          </p>

          {result.warnings.length > 0 && (
            <ul className="whatif__warnings">
              {result.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}

          {result.changed.length > 0 && (
            <div className="whatif__cols">
              <StepList title="Your dates" items={assumed} />
              <StepList title="Back on schedule" items={recovered} empty="None" />
              <StepList title="Still slipping" items={slipping} empty="None" />
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function StepList({ title, items, empty }: { title: string; items: WhatIfResult["changed"]; empty?: string }) {
  if (items.length === 0 && !empty) return null;
  return (
    <div>
      <div className="label">{title}</div>
      {items.length === 0 ? (
        <p className="data-note">{empty}</p>
      ) : (
        <ul className="whatif__steps">
          {items.map((m) => (
            <li key={m.milestone_id}>
              <span>{m.name}</span>
              <span className="mono">
                {fmtDate(m.baseline_finish)} → {fmtDate(m.projected_finish)}
                <span className={m.slip_days > 0 ? "late" : ""}> · {slip(m.slip_days)}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

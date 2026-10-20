"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { updateMilestone, type Milestone, type MilestoneStatus } from "@/lib/api";
import { DELAY_SHORT, STATUS_LABEL, fmtDate, plural, roleLabel } from "@/lib/format";

const STATUSES = Object.keys(STATUS_LABEL) as MilestoneStatus[];

function Editor({ m, onDone }: { m: Milestone; onDone: () => void }) {
  const router = useRouter();
  const [status, setStatus] = useState<MilestoneStatus>(m.status);
  const [reason, setReason] = useState(m.blocked_reason ?? "");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    const body: Parameters<typeof updateMilestone>[1] = { changed_by_user_id: m.owner?.id };
    if (status !== m.status) body.status = status;
    if (status === "blocked" && reason.trim() !== (m.blocked_reason ?? "")) body.blocked_reason = reason.trim();
    if (note.trim()) body.note = note.trim();
    if (!body.status && !body.blocked_reason && !body.note) {
      setBusy(false);
      onDone();
      return;
    }
    const err = await updateMilestone(m.id, body);
    setBusy(false);
    if (err) return setError(err);
    onDone();
    router.refresh();
  }

  return (
    <div className="editor">
      <label>
        <span className="label">Status</span>
        <select value={status} onChange={(e) => setStatus(e.target.value as MilestoneStatus)}>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s]}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span className="label">{status === "blocked" ? "Why is it blocked?" : "Note (optional)"}</span>
        {status === "blocked" ? (
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Legal redlines outstanding" />
        ) : (
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add context for the history" />
        )}
      </label>
      <div className="editor__actions">
        <button className="btn btn--primary" onClick={save} disabled={busy}>
          {busy ? "Saving…" : "Save"}
        </button>
        <button className="btn" onClick={onDone} disabled={busy}>
          Cancel
        </button>
      </div>
      {error && <div className="editor__error">{error}</div>}
      <div className="editor__hint">
        {m.owner ? `Recorded as ${m.owner.name} (synthetic user). ` : ""}Readiness, blockers and projected dates recompute on save.
      </div>
    </div>
  );
}

export default function MilestoneList({ milestones }: { milestones: Milestone[] }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div>
      {milestones.map((m) => (
        <div className="mrow" key={m.id}>
          <div>
            <div className="mrow__name">{m.name}</div>
            {m.status === "blocked" && m.blocked_reason && <div className="mrow__reason">{m.blocked_reason}</div>}
          </div>
          <div>
            <span className="status" data-s={m.status}>
              {STATUS_LABEL[m.status]}
            </span>
            {m.is_impacted && m.status !== "complete" && <div className="cell-sub late">Pushed out by upstream delay</div>}
          </div>
          <div>
            <div className="cell-main mono">{fmtDate(m.due_date, true)}</div>
            <div className="cell-sub">
              {m.is_overdue && m.status !== "complete" && m.status !== "not_applicable" ? (
                <span className="late">
                  {plural(m.days_overdue, "day")} late · {DELAY_SHORT[m.delay_level]}
                </span>
              ) : m.status === "complete" ? (
                `Done ${fmtDate(m.completed_at)}`
              ) : (
                "On schedule"
              )}
            </div>
          </div>
          <div>
            {m.owner ? (
              <>
                <div className="cell-main">{m.owner.name}</div>
                <div className="cell-sub">{roleLabel(m.owner.role)}</div>
              </>
            ) : (
              <span className="faint">Unassigned</span>
            )}
          </div>
          <button className="btn" onClick={() => setOpen(open === m.id ? null : m.id)} aria-expanded={open === m.id}>
            {open === m.id ? "Close" : "Update"}
          </button>
          {open === m.id && <Editor m={m} onDone={() => setOpen(null)} />}
        </div>
      ))}
    </div>
  );
}

"use client";

import Link from "next/link";
import { useState } from "react";
import type { Task } from "@/lib/insights";
import { DELAY_SHORT, STATUS_LABEL, fmtDate, plural, roleLabel } from "@/lib/format";
import { TaskChip } from "./Chips";
import { Editor } from "./MilestoneList";

/** Tasks across sites with in-place status updates (same editor as the site page). */
export default function TaskList({ tasks, showOwner }: { tasks: Task[]; showOwner: boolean }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div>
      {tasks.map((t) => {
        const m = t.milestone;
        return (
          <div className="mrow" key={m.id}>
            <div>
              <div className="mrow__name">{m.name}</div>
              <div className="cell-sub">
                <Link href={`/sites/${t.siteId}`} className="link">{t.siteName}</Link>
              </div>
              {m.status === "blocked" && m.blocked_reason && <div className="mrow__reason">{m.blocked_reason}</div>}
            </div>
            <div>
              <TaskChip kind={t.kind} />
              <div className="cell-sub">{STATUS_LABEL[m.status]}</div>
            </div>
            <div>
              <div className="cell-main mono">{fmtDate(m.due_date, true)}</div>
              <div className="cell-sub">
                {m.is_overdue ? (
                  <span className="late">{plural(m.days_overdue, "day")} late · {DELAY_SHORT[m.delay_level]}</span>
                ) : t.until !== null ? (
                  t.until === 0 ? "Due today" : `Due in ${plural(t.until, "day")}`
                ) : (
                  "No due date"
                )}
              </div>
            </div>
            <div>
              {showOwner && m.owner ? (
                <>
                  <div className="cell-main">{m.owner.name}</div>
                  <div className="cell-sub">{roleLabel(m.owner.role)}</div>
                </>
              ) : (
                <div className="cell-sub">{t.trialLabel}</div>
              )}
            </div>
            <button className="btn" onClick={() => setOpen(open === m.id ? null : m.id)} aria-expanded={open === m.id}>
              {open === m.id ? "Close" : "Update"}
            </button>
            {open === m.id && <Editor m={m} onDone={() => setOpen(null)} />}
          </div>
        );
      })}
    </div>
  );
}

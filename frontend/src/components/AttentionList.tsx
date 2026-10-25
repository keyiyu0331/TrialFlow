import Link from "next/link";
import type { Task } from "@/lib/insights";
import { plural, roleLabel } from "@/lib/format";
import { TaskChip } from "./Chips";

function when(t: Task) {
  if (t.milestone.days_overdue > 0) return <span className="late">{plural(t.milestone.days_overdue, "day")} late</span>;
  if (t.until === null) return "No due date";
  return t.until === 0 ? "Due today" : `Due in ${plural(t.until, "day")}`;
}

/** Alerts: blocked, overdue, or about-to-be-due milestones across the trial. */
export default function AttentionList({ tasks, total }: { tasks: Task[]; total: number }) {
  if (tasks.length === 0) return <p className="muted">Nothing needs attention right now.</p>;
  return (
    <>
      <ul className="attn">
        {tasks.map((t) => (
          <li key={t.milestone.id}>
            <Link href={`/sites/${t.siteId}`} className="attn__row">
              <TaskChip kind={t.kind} />
              <span className="attn__main">
                <span className="cell-main">{t.milestone.name}</span>
                <span className="cell-sub">
                  {t.siteName} · {when(t)}
                  {t.milestone.owner && ` · ${t.milestone.owner.name}, ${roleLabel(t.milestone.owner.role)}`}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
      {total > tasks.length && (
        <Link href="/tasks" className="attn__more">
          See all {total} items in My tasks →
        </Link>
      )}
    </>
  );
}

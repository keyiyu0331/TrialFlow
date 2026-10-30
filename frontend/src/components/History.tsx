import type { ApiEvent, MilestoneStatus } from "@/lib/api";
import { fmtAgo, fmtDate, STATUS_LABEL } from "@/lib/format";

function describe(e: ApiEvent) {
  switch (e.event_type) {
    case "status_change":
      return (
        <>
          Status <span className="arrow">{STATUS_LABEL[e.old_value as MilestoneStatus] ?? e.old_value}</span>→
          <span className="arrow">{STATUS_LABEL[e.new_value as MilestoneStatus] ?? e.new_value}</span>
        </>
      );
    case "due_date_change":
      return (
        <>
          Due date <span className="arrow">{fmtDate(e.old_value, true)}</span>→
          <span className="arrow">{fmtDate(e.new_value, true)}</span>
        </>
      );
    case "owner_change":
      return <>Owner reassigned</>;
    default:
      return <>Note{e.new_value ? `: ${e.new_value}` : ""}</>;
  }
}

export default function History({ events }: { events: ApiEvent[] }) {
  if (events.length === 0) return <p className="muted">No changes recorded.</p>;
  return (
    <ul className="history">
      {events.map((e) => (
        <li key={e.id}>
          <span className="label">{fmtAgo(e.occurred_at)}</span>
          <div>
            <div className="history__what">
              <b>{e.milestone_name}</b> · {describe(e)}
              {e.changed_by && <span className="faint"> · {e.changed_by.name}</span>}
            </div>
            {e.note && <div className="history__note">{e.note}</div>}
          </div>
        </li>
      ))}
    </ul>
  );
}

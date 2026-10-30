import type { Milestone } from "@/lib/api";
import { dayNumber, fmtDate, todayIso } from "@/lib/format";

const LABEL_W = 190;
const ROW = 34;
const TOP = 28;
const CHART_W = 860;

/** Planned bar from start to due date; hatched extension to the projected finish when it slips. */
export default function Timeline({ milestones }: { milestones: Milestone[] }) {
  const rows = milestones.filter((m) => m.planned_start_date && m.due_date);
  if (rows.length === 0) return <p className="muted">No dated milestones.</p>;

  const today = dayNumber(todayIso());
  const starts = rows.map((m) => dayNumber(m.planned_start_date!));
  const ends = rows.map((m) =>
    Math.max(dayNumber(m.due_date!), m.projected_finish ? dayNumber(m.projected_finish) : 0),
  );
  const min = Math.min(...starts, today) - 3;
  const max = Math.max(...ends, today) + 5;
  const span = max - min;
  const x = (d: number) => LABEL_W + ((d - min) / span) * CHART_W;
  const W = LABEL_W + CHART_W + 16;
  const H = TOP + rows.length * ROW + 10;

  // month ticks
  const ticks: { d: number; label: string }[] = [];
  const first = new Date(min * 86_400_000);
  const cursor = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 1));
  while (cursor.getTime() / 86_400_000 < max) {
    ticks.push({
      d: Math.round(cursor.getTime() / 86_400_000),
      label: cursor.toLocaleDateString("en-US", { month: "short", year: "2-digit", timeZone: "UTC" }),
    });
    cursor.setUTCMonth(cursor.getUTCMonth() + 1);
  }

  return (
    <div className="scroll-x">
      <svg className="gantt" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Milestone timeline">
        <defs>
          <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" fill="rgba(124,91,209,0.18)" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="#7c5bd1" strokeWidth="3" />
          </pattern>
          <pattern id="hatch-slip" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" fill="rgba(193,69,106,0.06)" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="rgba(193,69,106,0.55)" strokeWidth="2" />
          </pattern>
        </defs>
        {ticks.map((t) => (
          <g key={t.d}>
            <line className="grid" x1={x(t.d)} x2={x(t.d)} y1={TOP - 6} y2={H - 6} />
            <text className="axis" x={x(t.d) + 4} y={14}>
              {t.label}
            </text>
          </g>
        ))}
        {rows.map((m, i) => {
          const y = TOP + i * ROW;
          const s = dayNumber(m.planned_start_date!);
          const due = dayNumber(m.due_date!);
          const proj = m.projected_finish ? dayNumber(m.projected_finish) : due;
          const late =
            m.is_blocking ||
            m.status === "blocked" ||
            (m.is_overdue && m.status !== "complete" && m.status !== "not_applicable");
          const showSlip = m.slip_days > 0 && m.status !== "complete" && m.status !== "not_applicable" && proj > due;
          return (
            <g key={m.id}>
              <text className="row-label" x={0} y={y + 14}>
                {m.name}
              </text>
              <text className="row-sub" x={0} y={y + 26}>
                {fmtDate(m.planned_start_date)} → {fmtDate(m.due_date)}
              </text>
              <rect
                className={`bar bar--${late ? "blocked" : m.status}`}
                x={x(s)}
                y={y + 4}
                width={Math.max(4, x(due) - x(s))}
                height={18}
                rx={2}
              >
                <title>{`${m.name}: ${fmtDate(m.planned_start_date)} to ${fmtDate(m.due_date)}`}</title>
              </rect>
              {showSlip && (
                <rect className="slip" x={x(due)} y={y + 4} width={Math.max(4, x(proj) - x(due))} height={18} rx={2}>
                  <title>{`Projected to finish ${fmtDate(m.projected_finish)} (+${m.slip_days}d)`}</title>
                </rect>
              )}
            </g>
          );
        })}
        <line className="today" x1={x(today)} x2={x(today)} y1={TOP - 6} y2={H - 6} />
        <text className="today-label" x={x(today) + 5} y={H - 12}>
          TODAY
        </text>
      </svg>
    </div>
  );
}

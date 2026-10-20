import Link from "next/link";
import { notFound } from "next/navigation";
import { DelayChip, HealthChip } from "@/components/Chips";
import DependencyGraph from "@/components/DependencyGraph";
import History from "@/components/History";
import MilestoneList from "@/components/MilestoneList";
import Timeline from "@/components/Timeline";
import { ApiError, ApiUnreachable, getEvents, getGraph, getSite } from "@/lib/api";
import { fmtDate, location, plural, roleLabel } from "@/lib/format";

export default async function SitePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const num = Number(id);
  if (!Number.isInteger(num) || num < 1) notFound();

  let data;
  try {
    data = await Promise.all([getSite(num), getGraph(num), getEvents(num)]);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    if (e instanceof ApiUnreachable) {
      return (
        <section className="section" style={{ paddingTop: 64 }}>
          <div className="notice">The API is not reachable. Start the backend, then reload.</div>
        </section>
      );
    }
    throw e;
  }
  const [site, graph, events] = data;
  const b = site.top_blocker;
  const owner = site.next_action_owner;

  return (
    <>
      <div className="crumbs">
        <Link href="/">Dashboard</Link>
        <span>/</span>
        <Link href={`/?trial=${site.trial.id}`}>{site.trial.nct_id ?? "Trial"}</Link>
        <span>/</span>
        <span>{site.site.name}</span>
      </div>

      <div className="detail-head">
        <div>
          <h1>{site.site.name}</h1>
          <p className="detail-head__sub">
            {location(site.site) || "Location not listed"} · {site.trial.title}
          </p>
          <div className="detail-head__chips">
            <HealthChip health={site.health} />
            {site.delay_level !== "on_time" && <DelayChip level={site.delay_level} />}
          </div>
          <p className="data-note" style={{ marginTop: 14, marginBottom: 0 }}>
            Real registry site. Milestones, owners and dates are synthetic demo data.
          </p>
        </div>
      </div>

      <div className="kpis">
        <div className="card kpi">
          <div className="label">Readiness</div>
          <div className="kpi__value">{Math.round(site.readiness_pct)}%</div>
          <div className="kpi__sub">
            {site.milestones_satisfied} of {site.milestones_total} milestones satisfied
          </div>
        </div>
        <div className={`card kpi ${b ? "kpi--alert" : ""}`}>
          <div className="label">Top blocker</div>
          <div className="kpi__value">{b ? b.milestone_name : "None"}</div>
          <div className="kpi__sub">
            {b
              ? `${b.days_overdue > 0 ? `${plural(b.days_overdue, "day")} late` : "Blocked"} · holds up ${b.downstream_unsatisfied} later ${b.downstream_unsatisfied === 1 ? "milestone" : "milestones"}${b.blocked_reason ? ` · ${b.blocked_reason}` : ""}`
              : site.health === "activated"
                ? "Activated"
                : "Nothing is overdue or flagged"}
          </div>
        </div>
        <div className="card kpi">
          <div className="label">Next action</div>
          <div className="kpi__value">{owner ? owner.name : "—"}</div>
          <div className="kpi__sub">{owner ? `${roleLabel(owner.role)}${owner.team_name ? ` · ${owner.team_name}` : ""}` : "No open action"}</div>
        </div>
        <div className="card kpi">
          <div className="label">{site.health === "activated" ? "Activated" : "Projected activation"}</div>
          <div className="kpi__value mono" style={{ fontSize: 22 }}>
            {fmtDate(site.health === "activated" ? site.actual_activation_date : site.projected_activation_date, true)}
          </div>
          <div className="kpi__sub">
            {site.site_slip_days > 0 ? <span className="late">+{site.site_slip_days}d vs target {fmtDate(site.target_activation_date, true)}</span> : `Target ${fmtDate(site.target_activation_date, true)}`}
          </div>
        </div>
      </div>

      <section className="card panel">
        <div className="panel__head">
          <div>
            <div className="label">Milestones</div>
            <h2 className="panel__title">Update status</h2>
          </div>
        </div>
        <MilestoneList milestones={site.milestones} />
      </section>

      <details className="card panel" open>
        <summary>
          <div className="panel__head">
            <div>
              <div className="label">Dependencies</div>
              <h2 className="panel__title">What is waiting on what</h2>
            </div>
          </div>
        </summary>
        <div className="legend" style={{ marginBottom: 14 }}>
          <span><i style={{ background: "rgba(91,63,184,0.35)" }} />Complete</span>
          <span><i style={{ background: "#fff", border: "1.5px solid var(--purple-2)" }} />In progress</span>
          <span><i style={{ background: "rgba(193,69,106,0.25)", border: "1.5px solid var(--blocked)" }} />Blocking</span>
        </div>
        <DependencyGraph graph={graph} />
      </details>

      <details className="card panel">
        <summary>
          <div className="panel__head">
            <div>
              <div className="label">Schedule</div>
              <h2 className="panel__title">Plan vs. projected finish</h2>
            </div>
          </div>
        </summary>
        <div className="legend" style={{ marginBottom: 14 }}>
          <span><i style={{ background: "rgba(124,91,209,0.4)" }} />Planned</span>
          <span><i style={{ background: "rgba(193,69,106,0.5)" }} />Late or blocked</span>
          <span><i style={{ background: "repeating-linear-gradient(45deg, rgba(193,69,106,0.6) 0 2px, transparent 2px 5px)" }} />Projected slip</span>
        </div>
        <Timeline milestones={site.milestones} />
      </details>

      <details className="card panel" style={{ marginBottom: 56 }}>
        <summary>
          <div className="panel__head">
            <div>
              <div className="label">History</div>
              <h2 className="panel__title">Recent changes ({events.total})</h2>
            </div>
          </div>
        </summary>
        <History events={events.items.slice(0, 12)} />
      </details>
    </>
  );
}

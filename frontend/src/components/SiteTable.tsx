import Link from "next/link";
import type { TrialSiteSummary } from "@/lib/api";
import { fmtDate, location, plural, roleLabel } from "@/lib/format";
import { HealthChip } from "./Chips";

/** One segment per milestone: satisfied first, then the blocker (if any), then the rest. */
function Strip({ site }: { site: TrialSiteSummary }) {
  const segs = Array.from({ length: site.milestones_total }, (_, i) => {
    if (i < site.milestones_satisfied) return "complete";
    if (i === site.milestones_satisfied && site.top_blocker) return "blocked";
    return "open";
  });
  return (
    <div className="strip" aria-hidden="true">
      {segs.map((s, i) => (
        <span key={i} className="strip__seg" data-s={s} />
      ))}
    </div>
  );
}

function Row({ site }: { site: TrialSiteSummary }) {
  const b = site.top_blocker;
  const owner = site.next_action_owner;
  return (
    <Link href={`/sites/${site.id}`} className="card site-row">
      <div>
        <div className="site-row__name">{site.site.name}</div>
        <div className="site-row__loc">{location(site.site) || "Location not listed"}</div>
      </div>
      <div>
        <HealthChip health={site.health} />
        {site.activation_status === "on_hold" && <div className="cell-sub">On hold</div>}
      </div>
      <div className="readiness">
        <div className="readiness__pct">
          <strong>{Math.round(site.readiness_pct)}%</strong>
          <span className="label">
            {site.milestones_satisfied}/{site.milestones_total}
          </span>
        </div>
        <Strip site={site} />
      </div>
      <div>
        {b ? (
          <>
            <div className="cell-main">{b.milestone_name}</div>
            <div className="cell-sub">
              {b.days_overdue > 0 && <span className="late">{plural(b.days_overdue, "day")} late</span>}
              {b.days_overdue > 0 && owner && " · "}
              {owner && `${owner.name}, ${roleLabel(owner.role)}`}
            </div>
          </>
        ) : (
          <span className="faint">{site.health === "activated" ? "Activated" : "Nothing blocking"}</span>
        )}
      </div>
      <div>
        <div className="cell-main mono">{fmtDate(site.projected_activation_date, true)}</div>
        <div className="cell-sub">
          {site.site_slip_days > 0 ? <span className="late">+{site.site_slip_days}d vs target</span> : "On target"}
        </div>
      </div>
    </Link>
  );
}

export default function SiteTable({ sites }: { sites: TrialSiteSummary[] }) {
  return (
    <div>
      <div className="sites__head label">
        <span>Trial site</span>
        <span>Health</span>
        <span>Readiness</span>
        <span>Blocker and owner</span>
        <span>Projected activation</span>
      </div>
      {sites.map((s) => (
        <Row key={s.id} site={s} />
      ))}
    </div>
  );
}

import Link from "next/link";
import type { TrialSiteSummary } from "@/lib/api";
import { fmtDate, location, plural, roleLabel } from "@/lib/format";
import { DelayChip, HealthChip, SourceTag } from "./Chips";

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
        <div className="site-row__tags">
          <SourceTag source={site.site.source_type} what="Site" />
          <SourceTag source={site.source_type} what="Activation" />
        </div>
      </div>
      <div>
        <HealthChip health={site.health} />
        {site.health === "activated" && <div className="cell-sub">Activated {fmtDate(site.actual_activation_date)}</div>}
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
              {b.days_overdue > 0 ? <span className="late">{plural(b.days_overdue, "day")} late</span> : "Blocked"}{" "}
              {b.delay_level !== "on_time" && <DelayChip level={b.delay_level} />}
            </div>
            {b.downstream_unsatisfied > 0 && <div className="cell-sub">Holds up {b.downstream_unsatisfied} later milestones</div>}
          </>
        ) : (
          <span className="faint">{site.health === "activated" ? "None" : "Nothing blocking"}</span>
        )}
      </div>
      <div>
        {owner ? (
          <>
            <div className="cell-main">{owner.name}</div>
            <div className="cell-sub">{roleLabel(owner.role)}</div>
          </>
        ) : (
          <span className="faint">—</span>
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
        <span>Top blocker</span>
        <span>Next action</span>
        <span>Projected activation</span>
      </div>
      {sites.map((s) => (
        <Row key={s.id} site={s} />
      ))}
    </div>
  );
}

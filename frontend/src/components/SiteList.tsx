import Link from "next/link";
import type { TrialSiteSummary } from "@/lib/api";
import { HEALTH_LABEL, fmtDate, location, plural, roleLabel } from "@/lib/format";

/** Flat, scannable list: one line per trial site, the blocker and its owner right where you look. */
export default function SiteList({ sites }: { sites: TrialSiteSummary[] }) {
  return (
    <div className="sl" role="list">
      <div className="sl__head" aria-hidden="true">
        <span>Trial site</span>
        <span>Progress</span>
        <span>Blocked by</span>
        <span>Go-live</span>
      </div>
      {sites.map((s) => {
        const b = s.top_blocker;
        const o = s.next_action_owner;
        return (
          <Link key={s.id} href={`/sites/${s.id}`} className="sl__row" role="listitem">
            <div className="sl__site">
              <span className="dot" data-h={s.health} title={HEALTH_LABEL[s.health]} />
              <div>
                <div className="sl__name">{s.site.name}</div>
                <div className="sl__sub">
                  {location(s.site) || "Location not listed"}
                  {s.activation_status === "on_hold" && " · On hold"}
                </div>
              </div>
            </div>
            <div className="sl__prog">
              <span className="bar" aria-hidden="true">
                <i style={{ width: `${Math.round(s.readiness_pct)}%` }} data-h={s.health} />
              </span>
              <span className="sl__pct">{Math.round(s.readiness_pct)}%</span>
            </div>
            <div>
              {b ? (
                <>
                  <div className="sl__name sl__name--sm">{b.milestone_name}</div>
                  <div className="sl__sub">
                    {b.days_overdue > 0 && <span className="late">{plural(b.days_overdue, "day")} late</span>}
                    {b.days_overdue > 0 && o && " · "}
                    {o && `${o.name}, ${roleLabel(o.role)}`}
                  </div>
                </>
              ) : (
                <span className="faint">{s.health === "activated" ? "Live" : "Nothing"}</span>
              )}
            </div>
            <div>
              <div className="sl__name sl__name--sm mono">{fmtDate(s.health === "activated" ? s.actual_activation_date : s.projected_activation_date)}</div>
              <div className="sl__sub">{s.site_slip_days > 0 ? <span className="late">+{s.site_slip_days}d vs target</span> : "On target"}</div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}

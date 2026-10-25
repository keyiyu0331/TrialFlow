/** The daily brief: what changed, what to do today, what is heading for trouble. Rule-based and deterministic. */
import type { ApiEvent, TrialSiteDetail, TrialSiteSummary } from "./api";
import { dayNumber, todayIso } from "./format";
import { nudgeText } from "./nudge";

export interface Action {
  siteId: number;
  siteName: string;
  milestone: string;
  owner: string | null;
  team: string | null;
  ownerRole: string | null;
  daysLate: number;
  holdsUp: number;
  why: string;
  nudge: string;
}

export interface Change {
  siteId: number;
  siteName: string;
  text: string;
  at: string;
}

export interface SiteRef {
  siteId: number;
  siteName: string;
  note: string;
}

export interface Brief {
  today: string;
  actions: Action[];
  changes: Change[];
  atRisk: SiteRef[];
  readyForGreenLight: SiteRef[];
  counts: { inStartup: number; blocked: number; atRisk: number; activated: number };
}

const live = (s: TrialSiteSummary) => s.activation_status === "in_startup";

function describe(e: ApiEvent): string {
  const who = e.changed_by?.name ?? "Someone";
  if (e.event_type === "status_change") {
    const to = (e.new_value ?? "").replace(/_/g, " ");
    return `${who} set ${e.milestone_name} to ${to}`;
  }
  if (e.event_type === "owner_change") return `${e.milestone_name} was reassigned`;
  if (e.event_type === "due_date_change") return `${e.milestone_name} due date moved to ${e.new_value ?? "a new date"}`;
  return `${who} noted on ${e.milestone_name}`;
}

export function buildBrief(
  details: TrialSiteDetail[],
  events: Map<number, ApiEvent[]>,
  sinceDays = 3,
  limit = 5,
): Brief {
  const today = todayIso();
  const sites = details.filter(live);

  const actions: Action[] = sites
    .filter((s) => s.top_blocker)
    .map((s) => {
      const b = s.top_blocker!;
      const m = s.milestones.find((x) => x.id === b.milestone_id);
      const why = b.blocked_reason
        ? `Blocked: ${b.blocked_reason}`
        : b.days_overdue > 0
          ? "Overdue and nothing upstream is in the way"
          : "Flagged as blocking";
      return {
        siteId: s.id,
        siteName: s.site.name,
        milestone: b.milestone_name,
        owner: b.owner?.name ?? null,
        team: b.owner?.team_name ?? null,
        ownerRole: b.owner?.role ?? null,
        daysLate: b.days_overdue,
        holdsUp: b.downstream_unsatisfied,
        why,
        nudge: nudgeText(s.site.name, m ?? b, b.downstream_unsatisfied),
      };
    })
    .sort((a, b) => b.holdsUp - a.holdsUp || b.daysLate - a.daysLate)
    .slice(0, limit);

  const cutoff = dayNumber(today) - sinceDays;
  const changes: Change[] = [];
  for (const s of sites) {
    for (const e of events.get(s.id) ?? []) {
      if (dayNumber(e.occurred_at) >= cutoff) changes.push({ siteId: s.id, siteName: s.site.name, text: describe(e), at: e.occurred_at });
    }
  }
  changes.sort((a, b) => b.at.localeCompare(a.at));

  const atRisk: SiteRef[] = sites
    .filter((s) => s.health === "at_risk" || (s.health !== "blocked" && s.site_slip_days > 0))
    .map((s) => ({
      siteId: s.id,
      siteName: s.site.name,
      note: s.site_slip_days > 0 ? `Projected ${s.site_slip_days} days past target` : "Close to slipping",
    }));

  const readyForGreenLight: SiteRef[] = sites
    .filter((s) => s.milestones.some((m) => m.template_code === "GREEN_LIGHT" && m.is_ready && m.status !== "complete"))
    .map((s) => ({ siteId: s.id, siteName: s.site.name, note: "Everything else is done. Only the sponsor green light is left." }));

  return {
    today,
    actions,
    changes,
    atRisk,
    readyForGreenLight,
    counts: {
      inStartup: sites.length,
      blocked: sites.filter((s) => s.health === "blocked").length,
      atRisk: atRisk.length,
      activated: details.filter((s) => s.health === "activated").length,
    },
  };
}

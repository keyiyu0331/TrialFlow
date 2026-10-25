/** Drafts a polite follow-up to a milestone owner. A person reads and sends it; TrialFlow never sends anything. */
import type { Blocker, Milestone } from "./api";
import { fmtDate, plural } from "./format";

export function nudgeText(siteName: string, m: Milestone | Blocker, downstream = 0): string {
  const name = "milestone_name" in m ? m.milestone_name : m.name;
  const o = m.owner;
  const isTeam = !!o && (o.team_name === o.name || /office|supply|pharmacy|team/i.test(o.name));
  const owner = !o ? "there" : isTeam ? `${o.name} team` : o.name.split(" ")[0];
  const reason = m.blocked_reason ? ` It's marked blocked: "${m.blocked_reason}".` : "";
  const late = m.days_overdue > 0 ? ` It is ${plural(m.days_overdue, "day")} past its ${fmtDate(m.due_date, true)} due date.` : m.due_date ? ` It is due ${fmtDate(m.due_date, true)}.` : "";
  const hold = downstream > 0 ? ` It is holding up ${plural(downstream, "later step")} for the site.` : "";
  return `Hi ${owner}, quick check on "${name}" for ${siteName}.${late}${reason}${hold} Could you share the current status and a date you expect it to be done? Thanks.`;
}

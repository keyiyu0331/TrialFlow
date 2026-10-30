/** Rule-based views over milestones: alerts, task lists, and the trial summary. No model involved. */
import type { Milestone, OwnerRef, TrialSiteDetail, TrialSiteSummary } from "./api";
import { dayNumber, todayIso } from "./format";

export type TaskKind = "blocked" | "overdue" | "due_soon" | "in_progress" | "ready" | "waiting";

export const TASK_LABEL: Record<TaskKind, string> = {
  blocked: "Blocked",
  overdue: "Overdue",
  due_soon: "Due soon",
  in_progress: "In progress",
  ready: "Ready to start",
  waiting: "Waiting",
};
const RANK: Record<TaskKind, number> = { blocked: 0, overdue: 1, due_soon: 2, in_progress: 3, ready: 4, waiting: 5 };
export const URGENT: TaskKind[] = ["blocked", "overdue", "due_soon"];
const OPEN = new Set(["not_started", "in_progress", "blocked"]);

export interface Task {
  kind: TaskKind;
  milestone: Milestone;
  siteId: number;
  siteName: string;
  trialLabel: string;
  /** Days until due (negative when late); null without a due date. */
  until: number | null;
}

function classify(m: Milestone, until: number | null, soonDays: number): TaskKind {
  if (m.status === "blocked" || m.is_blocking) return "blocked";
  if (m.is_overdue) return "overdue";
  const active = m.status === "in_progress" || m.is_ready;
  if (active && until !== null && until <= soonDays) return "due_soon";
  if (m.status === "in_progress") return "in_progress";
  if (m.is_ready) return "ready";
  return "waiting";
}

/** Open milestones on sites still in start-up, most urgent first. */
export function openTasks(details: TrialSiteDetail[], soonDays = 7): Task[] {
  const today = dayNumber(todayIso());
  const out: Task[] = [];
  for (const site of details) {
    if (site.activation_status !== "in_startup") continue;
    for (const m of site.milestones) {
      if (!OPEN.has(m.status)) continue;
      const until = m.due_date ? dayNumber(m.due_date) - today : null;
      out.push({
        kind: classify(m, until, soonDays),
        milestone: m,
        siteId: site.id,
        siteName: site.site.name,
        trialLabel: site.trial.nct_id ?? site.trial.title,
        until,
      });
    }
  }
  return out.sort(
    (a, b) =>
      RANK[a.kind] - RANK[b.kind] ||
      b.milestone.days_overdue - a.milestone.days_overdue ||
      (a.until ?? 9999) - (b.until ?? 9999),
  );
}

export interface TrialInsight {
  total: number;
  inStartup: number;
  blocked: number;
  slipping: number;
  avgReadiness: number | null;
  areas: { area: string; sites: number }[];
  worst: { siteId: number; siteName: string; milestone: string; days: number } | null;
  latestGoLive: string | null;
}

export function trialInsight(rows: TrialSiteSummary[], details: TrialSiteDetail[]): TrialInsight {
  const live = rows.filter((r) => r.activation_status === "in_startup");
  const byId = new Map(details.map((d) => [d.id, d]));
  const area = new Map<string, number>();
  let worst: TrialInsight["worst"] = null;
  for (const r of live) {
    const b = r.top_blocker;
    if (!b) continue;
    const ms = byId.get(r.id)?.milestones.find((m) => m.id === b.milestone_id);
    if (ms) area.set(ms.workstream, (area.get(ms.workstream) ?? 0) + 1);
    if (b.days_overdue > (worst?.days ?? 0)) worst = { siteId: r.id, siteName: r.site.name, milestone: b.milestone_name, days: b.days_overdue };
  }
  const dates = live.map((r) => r.projected_activation_date).filter((d): d is string => !!d).sort();
  return {
    total: rows.length,
    inStartup: live.length,
    blocked: live.filter((r) => r.health === "blocked").length,
    slipping: live.filter((r) => r.site_slip_days > 0).length,
    avgReadiness: live.length ? live.reduce((s, r) => s + r.readiness_pct, 0) / live.length : null,
    areas: [...area.entries()].map(([a, sites]) => ({ area: a, sites })).sort((x, y) => y.sites - x.sites),
    worst,
    latestGoLive: dates.length ? dates[dates.length - 1] : null,
  };
}

export interface Person extends OwnerRef {
  tasks: number;
}

export function peopleFrom(tasks: Task[]): Person[] {
  const map = new Map<number, Person>();
  for (const t of tasks) {
    const o = t.milestone.owner;
    if (!o) continue;
    const p = map.get(o.id) ?? { ...o, tasks: 0 };
    p.tasks += 1;
    map.set(o.id, p);
  }
  return [...map.values()].sort((a, b) => a.name.localeCompare(b.name));
}

/** Published start-up durations to compare against (see docs/site-activation-research.md). */
const BENCH: Record<string, { lo: number; hi: number; note: string }> = {
  IRB_APPROVAL: { lo: 28, hi: 42, note: "4–6 weeks for full-board review (WCG, 2024)" },
  CONTRACT_EXECUTED: { lo: 39, hi: 73, note: "39 days on standard templates, 73 on custom (CTSA study)" },
};

export interface CycleStat {
  code: string;
  name: string;
  n: number;
  median: number;
  bench: { lo: number; hi: number; note: string } | null;
}

/** Days from planned start to completion, per step, across the sites that finished it. */
export function cycleTimes(details: TrialSiteDetail[]): CycleStat[] {
  const byCode = new Map<string, { name: string; days: number[] }>();
  for (const d of details) {
    for (const m of d.milestones) {
      if (!m.template_code) continue;
      const entry = byCode.get(m.template_code) ?? { name: m.name, days: [] };
      if (m.status === "complete" && m.completed_at && m.planned_start_date) {
        entry.days.push(Math.max(0, dayNumber(m.completed_at) - dayNumber(m.planned_start_date)));
      }
      byCode.set(m.template_code, entry);
    }
  }
  return [...byCode.entries()]
    .filter(([, v]) => v.days.length > 0)
    .map(([code, v]) => {
      const s = [...v.days].sort((a, b) => a - b);
      const mid = s.length >> 1;
      return { code, name: v.name, n: s.length, median: s.length % 2 ? s[mid] : Math.round((s[mid - 1] + s[mid]) / 2), bench: BENCH[code] ?? null };
    });
}

export const SLIP_BUCKETS = [
  { key: "on", label: "On target", test: (d: number) => d <= 0 },
  { key: "1_14", label: "1–14 days late", test: (d: number) => d >= 1 && d <= 14 },
  { key: "15_30", label: "15–30 days late", test: (d: number) => d >= 15 && d <= 30 },
  { key: "30", label: "30+ days late", test: (d: number) => d > 30 },
];

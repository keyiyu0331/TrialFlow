/** Typed client for the TrialFlow API (see docs/api-design.md). */

export type SiteHealth = "activated" | "blocked" | "at_risk" | "on_track";
export type DelayLevel = "on_time" | "1_7" | "8_30" | "over_30";
export type MilestoneStatus = "not_started" | "in_progress" | "blocked" | "complete" | "not_applicable";
export type ActivationStatus = "selected" | "in_startup" | "activated" | "on_hold" | "dropped";
export type SourceType = "public_registry" | "synthetic";
export type EventType = "status_change" | "owner_change" | "due_date_change" | "note";

export interface OwnerRef {
  id: number;
  name: string;
  role: string;
  team_name: string | null;
}

export interface Site {
  id: number;
  name: string;
  is_placeholder_name: boolean;
  city: string | null;
  state: string | null;
  country: string | null;
  source_type: SourceType;
}

export interface Blocker {
  milestone_id: number;
  milestone_name: string;
  status: MilestoneStatus;
  due_date: string | null;
  days_overdue: number;
  delay_level: DelayLevel;
  owner: OwnerRef | null;
  blocked_reason: string | null;
  downstream_unsatisfied: number;
}

export interface TrialSiteSummary {
  id: number;
  site: Site;
  reported_recruitment_status: string | null;
  activation_status: ActivationStatus;
  target_activation_date: string | null;
  actual_activation_date: string | null;
  scenario_label: string | null;
  source_type: SourceType;
  readiness_pct: number;
  milestones_satisfied: number;
  milestones_total: number;
  is_ready: boolean;
  delay_level: DelayLevel;
  top_blocker: Blocker | null;
  next_action_owner: OwnerRef | null;
  health: SiteHealth;
  site_slip_days: number;
  projected_activation_date: string | null;
}

export interface Milestone {
  id: number;
  template_code: string | null;
  name: string;
  workstream: string;
  status: MilestoneStatus;
  owner: OwnerRef | null;
  planned_start_date: string | null;
  due_date: string | null;
  completed_at: string | null;
  status_changed_at: string;
  blocked_reason: string | null;
  predecessor_ids: number[];
  is_overdue: boolean;
  days_overdue: number;
  delay_level: DelayLevel;
  days_in_status: number;
  is_blocking: boolean;
  is_ready: boolean;
  projected_finish: string | null;
  slip_days: number;
  is_impacted: boolean;
  source_type: SourceType;
}

export interface TrialSiteDetail extends TrialSiteSummary {
  trial: { id: number; nct_id: string | null; title: string };
  selected_date: string | null;
  milestones: Milestone[];
}

export interface GraphNode {
  milestone_id: number;
  template_code: string | null;
  name: string;
  workstream: string;
  status: MilestoneStatus;
  is_gate: boolean;
  owner: OwnerRef | null;
  due_date: string | null;
  is_satisfied: boolean;
  is_overdue: boolean;
  is_blocking: boolean;
  is_ready: boolean;
  is_impacted: boolean;
}

export interface GraphEdge {
  id: number;
  predecessor_id: number;
  successor_id: number;
  is_satisfied: boolean;
}

export interface TrialSiteGraph {
  trial_site_id: number;
  green_light_milestone_id: number | null;
  nodes: GraphNode[];
  edges: GraphEdge[];
  blocking_milestone_ids: number[];
}

export interface ApiEvent {
  id: number;
  milestone_id: number;
  milestone_name: string;
  event_type: EventType;
  old_value: string | null;
  new_value: string | null;
  note: string | null;
  changed_by: OwnerRef | null;
  occurred_at: string;
}

export interface ActivationCounts {
  selected: number;
  in_startup: number;
  activated: number;
  on_hold: number;
  dropped: number;
}

export interface TrialSummary {
  id: number;
  nct_id: string | null;
  title: string;
  acronym: string | null;
  phases: string[];
  sponsor_name: string | null;
  overall_status: string | null;
  site_count: number;
  activation_counts: ActivationCounts;
  source_type: SourceType;
}

export interface TrialDetail extends TrialSummary {
  registry_url: string | null;
  avg_readiness_pct: number;
  target_fpi_date: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

/** Base URL for server-side rendering (pages) and for the browser (milestone updates). */
export const SERVER_API = process.env.API_URL ?? "http://localhost:8000";
export const BROWSER_API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
  ) {
    super(message);
  }
}

/** Thrown when the API cannot be reached at all, so pages can show a helpful message. */
export class ApiUnreachable extends Error {}

async function get<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${SERVER_API}${path}`, { cache: "no-store" });
  } catch {
    throw new ApiUnreachable(`Could not reach the API at ${SERVER_API}`);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? res.statusText, body.code);
  }
  return res.json() as Promise<T>;
}

export const getTrials = () => get<Page<TrialSummary>>("/trials?limit=500");
export const getTrial = (id: number) => get<TrialDetail>(`/trials/${id}`);
export const getSite = (id: number) => get<TrialSiteDetail>(`/trial-sites/${id}`);
export const getGraph = (id: number) => get<TrialSiteGraph>(`/trial-sites/${id}/graph`);
export const getEvents = (id: number) => get<Page<ApiEvent>>(`/trial-sites/${id}/events?limit=100`);

export function getDashboard(trialId: number, opts: { delay?: DelayLevel | null; sort?: string } = {}) {
  const params = new URLSearchParams({ limit: "500", sort: opts.sort ?? "-delay" });
  for (const status of ["in_startup", "on_hold", "activated"]) params.append("activation_status", status);
  if (opts.delay) params.append("delay_level", opts.delay);
  return get<Page<TrialSiteSummary>>(`/trials/${trialId}/sites?${params}`);
}

/** Trials that have sites TrialFlow is tracking, most active first. */
export function trackedTrials(trials: TrialSummary[]): TrialSummary[] {
  const tracked = (t: TrialSummary) => t.activation_counts.in_startup + t.activation_counts.activated + t.activation_counts.on_hold;
  return trials.filter((t) => tracked(t) > 0).sort((a, b) => tracked(b) - tracked(a));
}

export interface MilestoneUpdate {
  status?: MilestoneStatus;
  blocked_reason?: string;
  note?: string;
  changed_by_user_id?: number;
}

/** Called from the browser. Returns an error message, or null on success. */
export async function updateMilestone(id: number, body: MilestoneUpdate): Promise<string | null> {
  try {
    const res = await fetch(`${BROWSER_API}/milestones/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (res.ok) return null;
    const data = await res.json().catch(() => ({}));
    return data.detail ?? `Update failed (${res.status})`;
  } catch {
    return `Could not reach the API at ${BROWSER_API}`;
  }
}

export const getSiteDetails = (ids: number[]) => Promise.all(ids.map(getSite));

/** Every tracked trial with its dashboard rows and per-site detail (milestones). */
export async function getTrackedWorld() {
  const trials = trackedTrials((await getTrials()).items);
  return Promise.all(
    trials.map(async (trial) => {
      const rows = (await getDashboard(trial.id)).items;
      const details = await getSiteDetails(rows.map((r) => r.id));
      return { trial, rows, details };
    }),
  );
}

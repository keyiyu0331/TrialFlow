import type { DelayLevel, MilestoneStatus, SiteHealth } from "./api";

const MS_PER_DAY = 86_400_000;

/** Parse a YYYY-MM-DD string as a UTC date so it never shifts with the time zone. */
export function parseDay(iso: string): Date {
  return new Date(`${iso.slice(0, 10)}T00:00:00Z`);
}

export function dayNumber(iso: string): number {
  return Math.round(parseDay(iso).getTime() / MS_PER_DAY);
}

/** Today as YYYY-MM-DD (server date; the API measures "today" on the same machine). */
export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function fmtDate(iso: string | null | undefined, withYear = false): string {
  if (!iso) return "—";
  return parseDay(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: withYear ? "numeric" : undefined,
    timeZone: "UTC",
  });
}

export function fmtAgo(iso: string, today = todayIso()): string {
  const days = dayNumber(today) - dayNumber(iso);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  return `${days}d ago`;
}

export const HEALTH_LABEL: Record<SiteHealth, string> = {
  blocked: "Blocked",
  at_risk: "At risk",
  on_track: "On track",
  activated: "Activated",
};

export const DELAY_LABEL: Record<DelayLevel, string> = {
  on_time: "On time",
  "1_7": "1–7 days late",
  "8_30": "8–30 days late",
  over_30: "30+ days late",
};

export const DELAY_SHORT: Record<DelayLevel, string> = {
  on_time: "On time",
  "1_7": "1–7d",
  "8_30": "8–30d",
  over_30: "30d+",
};

export const STATUS_LABEL: Record<MilestoneStatus, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  blocked: "Blocked",
  complete: "Complete",
  not_applicable: "Not applicable",
};

const ROLE_LABEL: Record<string, string> = {
  startup_manager: "Start-up manager",
  cra: "CRA",
  site_coordinator: "Site coordinator",
  regulatory: "Regulatory",
  contracts: "Contracts",
  pharmacist: "Pharmacy",
  lab_manager: "Lab manager",
  pi: "PI",
  sponsor_supply: "Sponsor supply",
};

export const roleLabel = (role: string) => ROLE_LABEL[role] ?? role;

export function location(site: { city: string | null; state: string | null; country: string | null }): string {
  return [site.city, site.state, site.country].filter(Boolean).join(", ");
}

/** "6 weeks, 2 days" style helper is overkill; keep plain days. */
export const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

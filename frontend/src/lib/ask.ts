/**
 * Ask TrialFlow: answers a plain-English question from the structured status the API already returns.
 * Rule-based and read-only. It never changes a milestone, and every answer links to the record it came from.
 */
import type { TrialSiteDetail } from "./api";
import { HEALTH_LABEL, fmtDate, plural, roleLabel } from "./format";
import { URGENT, openTasks, trialInsight, type Task } from "./insights";

export interface AskLink {
  label: string;
  sub?: string;
  href: string;
}

export interface Answer {
  text: string;
  links: AskLink[];
  /** Follow-up questions worth offering next. */
  follow?: string[];
}

const STOP = new Set([
  "what", "which", "who", "whom", "when", "where", "why", "how", "does", "doing", "have", "has", "with", "from", "that", "this",
  "about", "show", "tell", "give", "need", "should", "would", "could", "site", "sites", "trial", "trials", "hospital", "cancer",
  "center", "centre", "care", "medical", "health", "research", "institute", "university", "holding", "status", "there", "their",
  "today", "late", "blocked", "overdue", "next", "most", "right", "now", "please", "list", "many", "much", "are", "the", "and",
]);

const tokens = (q: string) => q.toLowerCase().match(/[a-z]{3,}/g) ?? [];
const has = (q: string, ...words: string[]) => words.some((w) => q.includes(w));
const siteLink = (s: TrialSiteDetail, sub?: string): AskLink => ({ label: s.site.name, sub, href: `/sites/${s.id}` });
const taskLink = (t: Task): AskLink => ({
  label: `${t.milestone.name} · ${t.siteName}`,
  sub: [
    t.milestone.days_overdue > 0 ? `${plural(t.milestone.days_overdue, "day")} late` : t.until !== null ? `due in ${plural(t.until, "day")}` : "no due date",
    t.milestone.owner ? `${t.milestone.owner.name}, ${roleLabel(t.milestone.owner.role)}` : "no owner",
  ].join(" · "),
  href: `/sites/${t.siteId}`,
});

const MILESTONE_WORDS: Record<string, string[]> = {
  contract: ["contract"], budget: ["budget"], irb: ["irb"], ethics: ["irb"], pharmacy: ["pharmacy"], training: ["training"],
  drug: ["drug"], shipment: ["drug"], shipping: ["drug"], lab: ["lab"], initiation: ["initiation"], siv: ["initiation"],
  regulatory: ["regulatory"], feasibility: ["feasibility"], green: ["green"],
};

function siteStory(s: TrialSiteDetail, tasks: Task[]): Answer {
  const b = s.top_blocker;
  const parts = [
    `${s.site.name} is ${HEALTH_LABEL[s.health].toLowerCase()}, ${Math.round(s.readiness_pct)}% ready (${s.milestones_satisfied} of ${s.milestones_total} milestones done).`,
  ];
  if (s.health === "activated") parts.push(`It was activated ${fmtDate(s.actual_activation_date, true)}.`);
  else if (b) {
    const late = b.days_overdue > 0 ? `, ${plural(b.days_overdue, "day")} late` : "";
    const who = b.owner ? ` ${b.owner.name} (${roleLabel(b.owner.role)}) owns it.` : "";
    const down = b.downstream_unsatisfied ? ` It holds up ${plural(b.downstream_unsatisfied, "later step")}.` : "";
    parts.push(`What's holding it up: ${b.milestone_name}${late}.${who}${down}`);
  } else parts.push("Nothing is blocking it right now.");
  if (s.health !== "activated" && s.projected_activation_date) {
    parts.push(
      `Projected go-live ${fmtDate(s.projected_activation_date, true)}${s.site_slip_days > 0 ? `, ${plural(s.site_slip_days, "day")} past target` : ", on target"}.`,
    );
  }
  const next = tasks.filter((t) => t.siteId === s.id).slice(0, 3);
  return { text: parts.join(" "), links: [siteLink(s, "Open site"), ...next.map(taskLink)], follow: ["What should I chase today?"] };
}

export function answer(question: string, details: TrialSiteDetail[]): Answer {
  const q = question.toLowerCase().trim();
  const sites = [...new Map(details.map((d) => [d.id, d])).values()];
  const live = sites.filter((s) => s.activation_status === "in_startup");
  const tasks = openTasks(sites);
  const urgent = tasks.filter((t) => URGENT.includes(t.kind));

  if (!q) return help();
  if (/^(hi|hello|hey|help|what can you do)\b/.test(q)) return help();

  const words = tokens(q).filter((w) => !STOP.has(w));

  // A specific site: "what's holding up Oxford?"
  const scored = sites
    .map((s) => {
      const hay = new Set(tokens(`${s.site.name} ${s.site.city ?? ""} ${s.site.state ?? ""}`));
      return { s, score: words.filter((w) => hay.has(w)).length };
    })
    .filter((x) => x.score > 0);
  const best = Math.max(0, ...scored.map((x) => x.score));
  const matched = scored.filter((x) => x.score === best).map((x) => x.s);
  if (matched.length === 1) return siteStory(matched[0], tasks);
  if (matched.length > 1 && matched.length <= 8) {
    return {
      text: `${matched.length} sites match. Pick one to see what's holding it up:`,
      links: matched.map((s) => siteLink(s, `${HEALTH_LABEL[s.health]} · ${Math.round(s.readiness_pct)}% ready`)),
    };
  }

  // A person: "what does Nadia have open?"
  const people = new Map<number, { name: string; first: string; last: string }>();
  for (const t of tasks) {
    const o = t.milestone.owner;
    if (o) people.set(o.id, { name: o.name, first: o.name.split(" ")[0].toLowerCase(), last: (o.name.split(" ").slice(-1)[0] ?? "").toLowerCase() });
  }
  const person = [...people.entries()].find(([, p]) => words.includes(p.first) || (p.last.length > 3 && words.includes(p.last)));
  if (person) {
    const mine = tasks.filter((t) => t.milestone.owner?.id === person[0]);
    if (mine.length === 0) return { text: `${person[1].name} has nothing open right now.`, links: [] };
    const hot = mine.filter((t) => URGENT.includes(t.kind));
    return {
      text: `${person[1].name} has ${plural(mine.length, "open item")}, ${hot.length} of them urgent.${hot.length ? " Most urgent first:" : ""}`,
      links: (hot.length ? hot : mine).slice(0, 6).map(taskLink),
      follow: ["What should I chase today?"],
    };
  }

  // A kind of milestone: "which contracts are stuck?"
  const key = Object.keys(MILESTONE_WORDS).find((k) => q.includes(k));
  if (key) {
    const needle = MILESTONE_WORDS[key][0];
    const hits = tasks.filter((t) => t.milestone.name.toLowerCase().includes(needle) && URGENT.includes(t.kind));
    if (hits.length === 0) return { text: `No ${key} items are blocked, overdue or due soon right now.`, links: [] };
    return {
      text: `${plural(hits.length, "site")} ${hits.length === 1 ? "has" : "have"} a ${key} item that needs attention. Worst first:`,
      links: hits.slice(0, 8).map(taskLink),
      follow: ["What should I chase today?"],
    };
  }

  if (has(q, "chase", "nudge", "today", "priorit", "first", "focus", "do now", "should i", "follow up")) {
    const roots = live
      .filter((s) => s.top_blocker)
      .sort((a, b) => b.top_blocker!.downstream_unsatisfied - a.top_blocker!.downstream_unsatisfied || b.top_blocker!.days_overdue - a.top_blocker!.days_overdue)
      .slice(0, 5);
    if (roots.length === 0) return { text: "Nothing is blocked today. Nice.", links: [] };
    return {
      text: `Start with these ${roots.length}. Each is the main blocker at its site, ranked by how many later steps it holds up:`,
      links: [
        ...roots.map((s) => {
          const b = s.top_blocker!;
          return {
            label: `${b.milestone_name} · ${s.site.name}`,
            sub: `${b.owner ? `${b.owner.name}, ${roleLabel(b.owner.role)}` : "no owner"} · ${b.days_overdue > 0 ? `${plural(b.days_overdue, "day")} late` : "blocked"} · holds up ${b.downstream_unsatisfied}`,
            href: `/sites/${s.id}`,
          };
        }),
        { label: "Open the daily brief", sub: "Ready-to-send follow-up messages for each", href: "/brief" },
      ],
      follow: ["Which sites will miss their target?"],
    };
  }

  if (has(q, "overdue", "late", "behind", "delay")) {
    const late = tasks.filter((t) => t.milestone.days_overdue > 0);
    if (late.length === 0) return { text: "Nothing is overdue.", links: [] };
    return { text: `${plural(late.length, "item")} overdue across ${plural(new Set(late.map((t) => t.siteId)).size, "site")}. Longest first:`, links: late.slice(0, 8).map(taskLink) };
  }

  if (has(q, "blocked", "stuck", "block")) {
    const b = live.filter((s) => s.health === "blocked").sort((x, y) => (y.top_blocker?.days_overdue ?? 0) - (x.top_blocker?.days_overdue ?? 0));
    if (b.length === 0) return { text: "No sites are blocked.", links: [] };
    return {
      text: `${plural(b.length, "site")} ${b.length === 1 ? "is" : "are"} blocked, out of ${live.length} in start-up.`,
      links: b.slice(0, 8).map((s) => siteLink(s, `${s.top_blocker?.milestone_name ?? "blocked"}${s.top_blocker && s.top_blocker.days_overdue > 0 ? ` · ${s.top_blocker.days_overdue}d late` : ""}`)),
      follow: ["What should I chase today?"],
    };
  }

  if (has(q, "miss", "target", "risk", "slip", "go live", "go-live", "activate", "when", "projected")) {
    const slip = live.filter((s) => s.site_slip_days > 0).sort((a, b) => b.site_slip_days - a.site_slip_days);
    const dates = live.map((s) => s.projected_activation_date).filter((d): d is string => !!d).sort();
    if (slip.length === 0) return { text: "Every site in start-up is projected to hit its target date.", links: [] };
    return {
      text: `${plural(slip.length, "site")} ${slip.length === 1 ? "is" : "are"} projected to miss target. The last one goes live ${fmtDate(dates[dates.length - 1], true)}.`,
      links: slip.slice(0, 8).map((s) => siteLink(s, `${plural(s.site_slip_days, "day")} past target · live ${fmtDate(s.projected_activation_date, true)}`)),
    };
  }

  if (has(q, "summary", "overview", "how are", "status", "report", "update", "everything")) {
    const rows = live;
    const i = trialInsight(rows, sites);
    const area = i.areas[0] ? ` Most blockers are in ${i.areas[0].area} (${plural(i.areas[0].sites, "site")}).` : "";
    const worst = i.worst ? ` Longest delay: ${i.worst.milestone} at ${i.worst.siteName}, ${plural(i.worst.days, "day")} late.` : "";
    return {
      text: `${i.inStartup} sites are in start-up and ${i.blocked} are blocked. Average readiness is ${Math.round(i.avgReadiness ?? 0)}%.${area}${worst} ${urgent.length} items need attention.`,
      links: [],
      follow: ["What should I chase today?"],
    };
  }

  return {
    text: "I couldn't match that to a site, person or step. I answer from the live activation data. Try one of these:",
    links: [],
    follow: ["What should I chase today?", "Which sites are blocked?", "What's overdue?", "Which sites will miss their target?", "Give me a summary"],
  };
}

function help(): Answer {
  return {
    text: "Ask me about your sites in plain English. I only read the live data, and I never change anything.",
    links: [],
    follow: ["What should I chase today?", "Which sites are blocked?", "What's overdue?", "Which sites will miss their target?", "Give me a summary"],
  };
}

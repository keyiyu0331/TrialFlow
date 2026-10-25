import Link from "next/link";
import type { TrialInsight } from "@/lib/insights";
import { fmtDate, plural } from "@/lib/format";

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** Rule-based summary of the trial; every figure is computed from milestone data. */
export default function TrialSummary({ insight: i }: { insight: TrialInsight }) {
  const rows: [string, React.ReactNode][] = [
    ["Sites in start-up", `${i.inStartup} of ${i.total}`],
    ["Blocked", `${i.blocked} ${i.blocked === 1 ? "site" : "sites"}${i.slipping ? `, ${i.slipping} projected past target` : ""}`],
    [
      "Most common blocker area",
      i.areas.length ? i.areas.slice(0, 2).map((a) => `${cap(a.area)} (${plural(a.sites, "site")})`).join(", ") : "None",
    ],
    [
      "Longest delay",
      i.worst ? (
        <>
          <Link href={`/sites/${i.worst.siteId}`} className="link">{i.worst.milestone}</Link> at {i.worst.siteName}, {plural(i.worst.days, "day")} late
        </>
      ) : (
        "None"
      ),
    ],
    ["Last site projected live", fmtDate(i.latestGoLive, true)],
    ["Average readiness", i.avgReadiness === null ? "—" : `${Math.round(i.avgReadiness)}%`],
  ];
  return (
    <dl className="summary">
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt className="label">{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

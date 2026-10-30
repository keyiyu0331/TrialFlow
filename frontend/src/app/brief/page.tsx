import Link from "next/link";
import CopyButton from "@/components/CopyButton";
import { ApiUnreachable, getEvents, getTrackedWorld, type ApiEvent } from "@/lib/api";
import { buildBrief } from "@/lib/brief";
import { fmtAgo, parseDay, plural, roleLabel } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function BriefPage() {
  let world;
  try {
    world = await getTrackedWorld();
  } catch (e) {
    if (e instanceof ApiUnreachable) {
      return (
        <section className="section" style={{ paddingTop: 64 }}>
          <div className="notice">The API is not reachable. Start the backend, then reload.</div>
        </section>
      );
    }
    throw e;
  }
  const details = world.flatMap((w) => w.details);
  const live = details.filter((d) => d.activation_status === "in_startup");
  const events = new Map<number, ApiEvent[]>(await Promise.all(live.map(async (d) => [d.id, (await getEvents(d.id)).items] as const)));
  const b = buildBrief(details, events);
  const date = parseDay(b.today).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", timeZone: "UTC" });
  const headline =
    b.actions.length === 0
      ? "Nothing is blocked. Enjoy the quiet."
      : `${plural(b.actions.length, "thing")} need${b.actions.length === 1 ? "s" : ""} you today.`;

  return (
    <>
      <section className="brief-head">
        <div className="label">Daily brief · {date}</div>
        <h1 className="brief-head__title">{headline}</h1>
        <p className="brief-head__sub">
          {b.counts.inStartup} sites in start-up · {b.counts.blocked} blocked · {b.counts.atRisk} at risk · {b.counts.activated} activated. Rule-based, from live status. Nothing here changes any data.
        </p>
      </section>

      <section className="card panel">
        <div className="panel__head">
          <div>
            <div className="label">Do these today</div>
            <h2 className="panel__title">Biggest blockers first</h2>
          </div>
        </div>
        {b.actions.length === 0 && <p className="muted">No blockers across your sites.</p>}
        <ol className="todo">
          {b.actions.map((a, i) => (
            <li key={a.siteId} className="todo__item">
              <div className="todo__n">{i + 1}</div>
              <div className="todo__main">
                <div className="todo__title">
                  {a.milestone} <span className="faint">at</span>{" "}
                  <Link href={`/sites/${a.siteId}`} className="link">
                    {a.siteName}
                  </Link>
                </div>
                <div className="cell-sub">
                  {a.daysLate > 0 && <span className="late">{plural(a.daysLate, "day")} late · </span>}
                  holds up {plural(a.holdsUp, "later step")} · {a.why}
                </div>
                <div className="cell-sub">
                  Owner: {a.owner ? `${a.owner}${a.ownerRole ? `, ${roleLabel(a.ownerRole)}` : ""}` : "unassigned"}
                  {a.team && a.team !== a.owner ? ` · ${a.team}` : ""}
                </div>
                <blockquote className="todo__msg">{a.nudge}</blockquote>
                <div className="todo__actions">
                  <CopyButton text={a.nudge} label="Copy follow-up message" />
                  <Link href={`/sites/${a.siteId}`} className="btn">
                    Open site
                  </Link>
                </div>
              </div>
            </li>
          ))}
        </ol>
        <p className="data-note" style={{ marginBottom: 0 }}>
          Messages are drafts for you to review and send yourself. TrialFlow never contacts anyone.
        </p>
      </section>

      <div className="brief-cols">
        <section className="card panel">
          <div className="label">Heading for trouble</div>
          <h2 className="panel__title">Projected to miss target</h2>
          {b.atRisk.length === 0 ? (
            <p className="muted">Every site is on pace.</p>
          ) : (
            <ul className="plain">
              {b.atRisk.map((s) => (
                <li key={s.siteId}>
                  <Link href={`/sites/${s.siteId}`} className="link">
                    {s.siteName}
                  </Link>
                  <span className="cell-sub">{s.note}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card panel">
          <div className="label">Ready to go</div>
          <h2 className="panel__title">Waiting only on green light</h2>
          {b.readyForGreenLight.length === 0 ? (
            <p className="muted">No site is one step from activation yet.</p>
          ) : (
            <ul className="plain">
              {b.readyForGreenLight.map((s) => (
                <li key={s.siteId}>
                  <Link href={`/sites/${s.siteId}`} className="link">
                    {s.siteName}
                  </Link>
                  <span className="cell-sub">{s.note}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="card panel" style={{ marginBottom: 56 }}>
        <div className="label">What changed</div>
        <h2 className="panel__title">Last 3 days</h2>
        {b.changes.length === 0 ? (
          <p className="muted">No updates in the last 3 days.</p>
        ) : (
          <ul className="plain">
            {b.changes.slice(0, 12).map((c, i) => (
              <li key={i}>
                <span>
                  {c.text} · <Link href={`/sites/${c.siteId}`} className="link">{c.siteName}</Link>
                </span>
                <span className="cell-sub">{fmtAgo(c.at, b.today)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

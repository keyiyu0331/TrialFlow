import Link from "next/link";
import { ApiUnreachable, getTrials } from "@/lib/api";

export const metadata = { title: "Trials · TrialFlow" };

export default async function Trials() {
  let items;
  try {
    items = (await getTrials()).items;
  } catch (e) {
    if (e instanceof ApiUnreachable) {
      return (
        <div className="section">
          <div className="notice">The API is not reachable. Start the backend, then reload.</div>
        </div>
      );
    }
    throw e;
  }
  const tracked = (t: (typeof items)[number]) =>
    t.activation_counts.in_startup + t.activation_counts.activated + t.activation_counts.on_hold;
  const bySites = (a: (typeof items)[number], b: (typeof items)[number]) => b.site_count - a.site_count;
  const active = items.filter((t) => tracked(t) > 0).sort((a, b) => tracked(b) - tracked(a) || bySites(a, b));
  const other = items.filter((t) => tracked(t) === 0).sort(bySites);

  return (
    <>
      <header className="dh">
        <div>
          <div className="dh__eyebrow">Trials</div>
          <h1 className="dh__title">{active.length} trials we are tracking</h1>
          <p className="dh__sub">
            All {items.length} are real recruiting trials from ClinicalTrials.gov. The ones below have demo start-up
            data, so you can see how site activation is going.
          </p>
        </div>
      </header>

      <div className="trials">
        {active.map((t) => (
          <Link key={t.id} href={`/?trial=${t.id}`} className="card trial-card">
            <span className="label">{t.nct_id}</span>
            <div className="trial-card__title">{t.title}</div>
            <div className="trial-card__foot">
              <span>{t.sponsor_name ?? "Sponsor not listed"}</span>
              <span>{tracked(t)} sites in TrialFlow</span>
            </div>
          </Link>
        ))}
      </div>

      <details className="menu--plain">
        <summary className="btn">Other registry trials ({other.length}), not tracked</summary>
        <div className="sl" style={{ marginTop: 12 }}>
          {other.map((t) => (
            <div key={t.id} className="sl__row sl__row--2">
              <div>
                <div className="sl__name sl__name--sm">{t.title}</div>
                <div className="sl__sub">{t.sponsor_name ?? "Sponsor not listed"}</div>
              </div>
              <div className="sl__sub">
                {t.site_count} {t.site_count === 1 ? "site" : "sites"}
              </div>
            </div>
          ))}
        </div>
      </details>
    </>
  );
}

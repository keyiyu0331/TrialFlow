import Link from "next/link";
import { ApiUnreachable, getTrials } from "@/lib/api";
import { SourceTag } from "@/components/Chips";

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
  const tracked = (t: (typeof items)[number]) => t.activation_counts.in_startup + t.activation_counts.activated + t.activation_counts.on_hold;
  const sorted = [...items].sort((a, b) => tracked(b) - tracked(a) || b.site_count - a.site_count);

  return (
    <section className="section" style={{ paddingTop: 48 }}>
      <div className="section__head">
        <div>
          <div className="label">Registry</div>
          <h1 className="section__title">Trials</h1>
          <p className="section__sub">
            {items.length} recruiting trials pulled from ClinicalTrials.gov. TrialFlow tracks activation for the ones with synthetic
            start-up data.
          </p>
        </div>
      </div>
      <div className="trials">
        {sorted.map((t) => {
          const n = tracked(t);
          const body = (
            <>
              <span className="label">{t.nct_id}</span>
              <div className="trial-card__title">{t.title}</div>
              <div className="trial-card__foot">
                <span>{t.sponsor_name ?? "Sponsor not listed"}</span>
                <span>{t.site_count} registry sites</span>
              </div>
              <div className="chips" style={{ marginTop: 12 }}>
                <SourceTag source={t.source_type} what="Trial" />
                {n > 0 ? <span className="tag tag--real">Tracking {n} trial sites</span> : <span className="tag">Not tracked</span>}
              </div>
            </>
          );
          return n > 0 ? (
            <Link key={t.id} href={`/?trial=${t.id}`} className="card trial-card">
              {body}
            </Link>
          ) : (
            <div key={t.id} className="card trial-card" style={{ opacity: 0.75 }}>
              {body}
            </div>
          );
        })}
      </div>
    </section>
  );
}

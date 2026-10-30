import Link from "next/link";
import SiteList from "@/components/SiteList";
import {
  ApiUnreachable,
  type DelayLevel,
  getDashboard,
  getSiteDetails,
  getTrial,
  getTrials,
  type SiteHealth,
  type TrialSiteSummary,
  trackedTrials,
} from "@/lib/api";
import { DELAY_LABEL, HEALTH_LABEL, location, plural } from "@/lib/format";
import { openTasks, URGENT } from "@/lib/insights";
import { getSession } from "@/lib/session";

type Search = { trial?: string; health?: string; delay?: string; sort?: string; status?: string; q?: string };

const STATUSES = [
  { key: "in_startup", label: "In start-up" },
  { key: "on_hold", label: "On hold" },
];
const HEALTHS: SiteHealth[] = ["blocked", "at_risk", "on_track", "activated"];
const DELAYS: DelayLevel[] = ["1_7", "8_30", "over_30"];
const SORTS = [
  { key: "-delay", label: "Most delayed" },
  { key: "readiness", label: "Least ready" },
  { key: "target_activation_date", label: "Target date" },
];

function href(p: Record<string, string | undefined>) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(p)) if (v) q.set(k, v);
  const s = q.toString();
  return s ? `/?${s}` : "/";
}

function Offline() {
  return (
    <div className="section">
      <div className="notice">
        <h3>The API is not reachable</h3>
        <p>
          Start it with <code>cd backend &amp;&amp; uvicorn app.main:app --reload</code> (after{" "}
          <code>python scripts/import_registry.py</code> and <code>python scripts/seed.py</code>), then reload.
        </p>
      </div>
    </div>
  );
}

export default async function Dashboard({ searchParams }: { searchParams: Promise<Search> }) {
  const sp = await searchParams;
  const user = await getSession();

  let tracked;
  try {
    tracked = trackedTrials((await getTrials()).items);
  } catch (e) {
    if (e instanceof ApiUnreachable) return <Offline />;
    throw e;
  }
  if (tracked.length === 0) {
    return (
      <div className="section">
        <div className="notice">
          <h3>No trial sites in start-up yet</h3>
          <p>
            Run <code>python scripts/seed.py</code> to generate labeled synthetic activation data for a few trials.
          </p>
        </div>
      </div>
    );
  }

  const chosen = tracked.find((t) => String(t.id) === sp.trial) ?? tracked[0];
  const health = HEALTHS.find((h) => h === sp.health);
  const delay = DELAYS.find((d) => d === sp.delay);
  const sort = SORTS.find((s) => s.key === sp.sort)?.key ?? "-delay";
  const status = STATUSES.find((x) => x.key === sp.status)?.key;
  const q = (sp.q ?? "").trim().slice(0, 80);

  const [trial, page] = await Promise.all([getTrial(chosen.id), getDashboard(chosen.id, { sort })]);
  const all = page.items;
  const live = all.filter((r) => r.activation_status === "in_startup");
  const details = await getSiteDetails(live.map((r) => r.id));
  const urgent = openTasks(details).filter((t) => URGENT.includes(t.kind));
  const counts = Object.fromEntries(HEALTHS.map((h) => [h, all.filter((s) => s.health === h).length])) as Record<
    SiteHealth,
    number
  >;
  const needle = q.toLowerCase();
  const visible: TrialSiteSummary[] = all.filter(
    (s) =>
      (!health || s.health === health) &&
      (!delay || s.delay_level === delay) &&
      (!status || s.activation_status === status) &&
      (!needle || `${s.site.name} ${location(s.site)}`.toLowerCase().includes(needle)),
  );
  const base = { trial: String(chosen.id), sort: sort === "-delay" ? undefined : sort };
  const active = [
    status && {
      label: STATUSES.find((x) => x.key === status)!.label,
      off: href({ ...base, health, delay, q: q || undefined }),
    },
    delay && { label: DELAY_LABEL[delay], off: href({ ...base, health, status, q: q || undefined }) },
    q && { label: `“${q}”`, off: href({ ...base, health, delay, status }) },
  ].filter(Boolean) as { label: string; off: string }[];
  const blocked = counts.blocked;
  const first = user?.name.split(" ")[0];

  return (
    <>
      <section className="dh">
        <div>
          <div className="dh__eyebrow">
            {first ? `Welcome back, ${first}` : "Dashboard"} · {trial.acronym ?? trial.nct_id}
          </div>
          <h1 className="dh__title">
            {blocked > 0 ? (
              <>
                <b>{blocked}</b> of {live.length} sites are blocked
              </>
            ) : (
              "No sites are blocked"
            )}
          </h1>
          <p className="dh__sub">
            {trial.title}. Average readiness {Math.round(trial.avg_readiness_pct ?? 0)}%.
          </p>
        </div>
        <div className="dh__cta">
          <Link href="/brief" className="btn btn--primary">
            Today’s brief{urgent.length ? ` · ${urgent.length}` : ""} →
          </Link>
          <Link href="/insights" className="btn">
            Insights
          </Link>
        </div>
      </section>

      {tracked.length > 1 && (
        <div className="seg" role="tablist" aria-label="Trial">
          {tracked.map((t) => (
            <Link key={t.id} href={href({ trial: String(t.id) })} className={t.id === chosen.id ? "on" : ""}>
              {t.acronym ?? t.nct_id}
            </Link>
          ))}
        </div>
      )}

      <nav className="views" aria-label="Filter by health">
        <Link href={href({ ...base, delay, status, q: q || undefined })} className={!health ? "on" : ""}>
          All <span>{all.length}</span>
        </Link>
        {HEALTHS.map((h) => (
          <Link
            key={h}
            href={href({ ...base, health: h, delay, status, q: q || undefined })}
            className={health === h ? "on" : ""}
          >
            <i className="dot" data-h={h} /> {HEALTH_LABEL[h]} <span>{counts[h]}</span>
          </Link>
        ))}
      </nav>

      <div className="toolbar">
        <form action="/" method="get" className="toolbar__search" role="search">
          <input type="hidden" name="trial" value={chosen.id} />
          {base.sort && <input type="hidden" name="sort" value={base.sort} />}
          {health && <input type="hidden" name="health" value={health} />}
          {delay && <input type="hidden" name="delay" value={delay} />}
          {status && <input type="hidden" name="status" value={status} />}
          <input name="q" defaultValue={q} placeholder="Search sites, cities, states…" aria-label="Search sites" />
        </form>
        <details className="menu">
          <summary className="btn">
            Filters
            {active.length > 0 && (
              <span className="badge">{active.filter((a) => !a.label.startsWith("“")).length || ""}</span>
            )}
          </summary>
          <div className="menu__pop">
            <div className="menu__group">
              <span className="label">Status</span>
              <Link
                href={href({ ...base, health, delay, q: q || undefined })}
                className={`pill ${!status ? "pill--active" : ""}`}
              >
                Any
              </Link>
              {STATUSES.map((x) => (
                <Link
                  key={x.key}
                  href={href({ ...base, health, delay, status: x.key, q: q || undefined })}
                  className={`pill ${status === x.key ? "pill--active" : ""}`}
                >
                  {x.label}
                </Link>
              ))}
            </div>
            <div className="menu__group">
              <span className="label">Delay</span>
              <Link
                href={href({ ...base, health, status, q: q || undefined })}
                className={`pill ${!delay ? "pill--active" : ""}`}
              >
                Any
              </Link>
              {DELAYS.map((d) => (
                <Link
                  key={d}
                  href={href({ ...base, health, delay: d, status, q: q || undefined })}
                  className={`pill ${delay === d ? "pill--active" : ""}`}
                >
                  {DELAY_LABEL[d]}
                </Link>
              ))}
            </div>
            <div className="menu__group">
              <span className="label">Sort</span>
              {SORTS.map((s) => (
                <Link
                  key={s.key}
                  href={href({
                    trial: String(chosen.id),
                    sort: s.key === "-delay" ? undefined : s.key,
                    health,
                    delay,
                    status,
                    q: q || undefined,
                  })}
                  className={`pill ${sort === s.key ? "pill--active" : ""}`}
                >
                  {s.label}
                </Link>
              ))}
            </div>
          </div>
        </details>
      </div>

      {active.length > 0 && (
        <div className="fchips">
          {active.map((a) => (
            <Link key={a.label} href={a.off} className="fchip">
              {a.label} <span aria-hidden="true">×</span>
            </Link>
          ))}
          <Link href={href({ trial: String(chosen.id), health })} className="fchip fchip--clear">
            Clear all
          </Link>
        </div>
      )}

      {visible.length === 0 ? (
        <div className="empty">
          <h3>No trial sites match</h3>
          <p>Try clearing a filter or search.</p>
        </div>
      ) : (
        <SiteList sites={visible} />
      )}
      <p className="data-note" style={{ margin: "14px 2px 56px" }}>
        {plural(visible.length, "site")} shown. Sites are real ClinicalTrials.gov records; milestones, owners and dates
        are synthetic demo data.
      </p>
    </>
  );
}

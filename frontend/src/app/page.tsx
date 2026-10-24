import Link from "next/link";
import AttentionList from "@/components/AttentionList";
import Orbit from "@/components/Orbit";
import SiteTable from "@/components/SiteTable";
import TrialSummary from "@/components/TrialSummary";
import {
  ApiUnreachable,
  getDashboard,
  getSiteDetails,
  getTrial,
  getTrials,
  trackedTrials,
  type DelayLevel,
  type SiteHealth,
  type TrialSiteSummary,
} from "@/lib/api";
import { DELAY_LABEL, HEALTH_LABEL, location } from "@/lib/format";
import { URGENT, openTasks, trialInsight } from "@/lib/insights";

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
  const details = await getSiteDetails(all.filter((r) => r.activation_status === "in_startup").map((r) => r.id));
  const insight = trialInsight(all, details);
  const urgent = openTasks(details).filter((t) => URGENT.includes(t.kind));
  const counts = Object.fromEntries(HEALTHS.map((h) => [h, all.filter((s) => s.health === h).length])) as Record<SiteHealth, number>;
  const needle = q.toLowerCase();
  const visible: TrialSiteSummary[] = all.filter(
    (s) =>
      (!health || s.health === health) &&
      (!delay || s.delay_level === delay) &&
      (!status || s.activation_status === status) &&
      (!needle || `${s.site.name} ${location(s.site)}`.toLowerCase().includes(needle)),
  );
  const worst = Math.max(0, ...all.map((s) => s.top_blocker?.days_overdue ?? 0));
  const base = { trial: String(chosen.id), sort: sort === "-delay" ? undefined : sort, q: q || undefined };
  const filtered = !!(health || delay || status || q);

  return (
    <>
      <section className="hero">
        <div>
          <div className="eyebrow">
            <span className="eyebrow__dot" />
            Site activation · Demo data
          </div>
          <h1 className="hero__title">
            <span className="t1">See the blocker</span>
            <span className="t2">before it delays</span>
            <span className="t3">activation.</span>
          </h1>
          <p className="hero__lede">
            For every trial site: how ready it is, which milestone is holding it up, who owns the next action, and when it will really
            go live.
          </p>
          <div className="meta">
            <div className="meta__item">
              <div className="label">Logic</div>
              <div className="meta__value">Deterministic</div>
            </div>
            <div className="meta__item">
              <div className="label">Data</div>
              <div className="meta__value">Registry + synthetic</div>
            </div>
            <div className="meta__item">
              <div className="label">Status</div>
              <div className="meta__value">Monitoring</div>
            </div>
          </div>
        </div>
        <Orbit
          avgReadiness={trial.avg_readiness_pct}
          sitesInStartup={trial.activation_counts.in_startup}
          blockedSites={counts.blocked}
          worstDelayDays={worst}
        />
      </section>

      <section className="section" aria-labelledby="trial-h">
        <div className="section__head">
          <div>
            <div className="label">Trial</div>
            <h2 className="section__title" id="trial-h">
              {trial.acronym ?? trial.nct_id}
            </h2>
            <p className="section__sub">{trial.title}</p>
          </div>
        </div>

        {tracked.length > 1 && (
          <div className="filter-group" style={{ marginBottom: 18 }}>
            <span className="label">Trial</span>
            {tracked.map((t) => (
              <Link key={t.id} href={href({ trial: String(t.id) })} className={`pill ${t.id === chosen.id ? "pill--active" : ""}`}>
                {t.acronym ?? t.nct_id} · {t.activation_counts.in_startup} in start-up
              </Link>
            ))}
          </div>
        )}

        <div className="stats">
          {HEALTHS.map((h) => (
            <Link
              key={h}
              href={href({ ...base, health: health === h ? undefined : h, delay, status })}
              className={`card stat stat--${h} ${health === h ? "stat--on" : ""}`}
              aria-pressed={health === h}
            >
              <div className="label">{HEALTH_LABEL[h]}</div>
              <div className="stat__num">{counts[h]}</div>
            </Link>
          ))}
        </div>

        <div className="insights">
          <div className="card panel">
            <div className="label">Trial summary</div>
            <TrialSummary insight={insight} />
          </div>
          <div className="card panel">
            <div className="label">Needs attention</div>
            <AttentionList tasks={urgent.slice(0, 5)} total={urgent.length} />
          </div>
        </div>

        <form action="/" method="get" className="search" role="search">
          <input type="hidden" name="trial" value={chosen.id} />
          {base.sort && <input type="hidden" name="sort" value={base.sort} />}
          {health && <input type="hidden" name="health" value={health} />}
          {delay && <input type="hidden" name="delay" value={delay} />}
          {status && <input type="hidden" name="status" value={status} />}
          <input name="q" defaultValue={q} placeholder="Search site, city, or state" aria-label="Search sites" />
          <button className="btn" type="submit">Search</button>
        </form>

        <div className="filters">
          <div className="filter-group">
            <span className="label">Status</span>
            <Link href={href({ ...base, health, delay })} className={`pill ${!status ? "pill--active" : ""}`}>Any</Link>
            {STATUSES.map((x) => (
              <Link key={x.key} href={href({ ...base, health, delay, status: x.key })} className={`pill ${status === x.key ? "pill--active" : ""}`}>
                {x.label}
              </Link>
            ))}
          </div>
          <div className="filter-group">
            <span className="label">Delay</span>
            <Link href={href({ ...base, health, status })} className={`pill ${!delay ? "pill--active" : ""}`}>Any</Link>
            {DELAYS.map((d) => (
              <Link key={d} href={href({ ...base, health, delay: d, status })} className={`pill ${delay === d ? "pill--active" : ""}`}>
                {DELAY_LABEL[d]}
              </Link>
            ))}
          </div>
          <div className="filter-group">
            <span className="label">Sort</span>
            {SORTS.map((s) => (
              <Link
                key={s.key}
                href={href({ trial: String(chosen.id), sort: s.key === "-delay" ? undefined : s.key, health, delay, status, q: q || undefined })}
                className={`pill ${sort === s.key ? "pill--active" : ""}`}
              >
                {s.label}
              </Link>
            ))}
          </div>
          {filtered && (
            <Link href={href({ trial: String(chosen.id), sort: base.sort })} className="pill">Clear filters</Link>
          )}
        </div>

        <p className="data-note">Sites are real ClinicalTrials.gov records. Milestones, owners and dates are synthetic demo data.</p>

        {visible.length === 0 ? (
          <div className="card empty">
            <h3>No trial sites match</h3>
            <p>Try clearing a filter or search.</p>
          </div>
        ) : (
          <SiteTable sites={visible} />
        )}
      </section>
    </>
  );
}

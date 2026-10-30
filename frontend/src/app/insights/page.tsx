import Link from "next/link";
import { ApiUnreachable, getTrackedWorld } from "@/lib/api";
import { fmtDate, plural } from "@/lib/format";
import { cycleTimes, SLIP_BUCKETS, trialInsight } from "@/lib/insights";

export const metadata = { title: "Insights · TrialFlow" };
export const dynamic = "force-dynamic";

export default async function Insights() {
  let world;
  try {
    world = await getTrackedWorld();
  } catch (e) {
    if (e instanceof ApiUnreachable) {
      return (
        <section className="section">
          <div className="notice">The API is not reachable. Start the backend, then reload.</div>
        </section>
      );
    }
    throw e;
  }
  const details = world.flatMap((w) => w.details);
  const live = details.filter((d) => d.activation_status === "in_startup");
  const overall = trialInsight(live, details);
  const cycles = cycleTimes(details);
  const scale = Math.max(1, ...cycles.map((c) => Math.max(c.median, c.bench?.hi ?? 0))) * 1.08;
  const areaMax = Math.max(1, ...overall.areas.map((a) => a.sites));
  const slip = SLIP_BUCKETS.map((b) => ({ ...b, n: live.filter((s) => b.test(s.site_slip_days)).length }));
  const slipMax = Math.max(1, ...slip.map((s) => s.n));

  return (
    <>
      <section className="dh">
        <div>
          <div className="dh__eyebrow">All tracked trials</div>
          <h1 className="dh__title">Insights</h1>
          <p className="dh__sub">
            Where time goes, where sites get stuck, and how the go-live dates look. Computed from the activation data,
            nothing estimated.
          </p>
        </div>
        <div className="dh__cta">
          <Link href="/" className="btn">
            ← Dashboard
          </Link>
        </div>
      </section>

      <div className="kpis kpis--4">
        <div className="kpi2">
          <span className="label">Sites in start-up</span>
          <b>{overall.inStartup}</b>
        </div>
        <div className="kpi2">
          <span className="label">Blocked</span>
          <b className="late">{overall.blocked}</b>
        </div>
        <div className="kpi2">
          <span className="label">Average readiness</span>
          <b>{Math.round(overall.avgReadiness ?? 0)}%</b>
        </div>
        <div className="kpi2">
          <span className="label">Last site live</span>
          <b className="mono kpi2__date">{fmtDate(overall.latestGoLive, true)}</b>
        </div>
      </div>

      <section className="card panel">
        <div className="label">How long steps take</div>
        <h2 className="panel__title">Your sites vs. published benchmarks</h2>
        <p className="muted" style={{ marginTop: 6 }}>
          Median days from planned start to completion, across sites that finished the step. The shaded band is the
          published range where one exists.
        </p>
        <ul className="cyc">
          {cycles.map((c) => (
            <li key={c.code}>
              <div className="cyc__name">
                {c.name}
                <small>{plural(c.n, "site")}</small>
              </div>
              <div className="cyc__track">
                {c.bench && (
                  <i
                    className="cyc__band"
                    style={{
                      left: `${(c.bench.lo / scale) * 100}%`,
                      width: `${((c.bench.hi - c.bench.lo) / scale) * 100}%`,
                    }}
                  />
                )}
                <i
                  className="cyc__bar"
                  style={{ width: `${(c.median / scale) * 100}%` }}
                  data-slow={c.bench ? c.median > c.bench.hi : undefined}
                />
              </div>
              <div className="cyc__val">
                <b>{c.median}d</b>
                {c.bench && (
                  <small>
                    {c.median > c.bench.hi
                      ? "slower than published"
                      : c.median < c.bench.lo
                        ? "faster than published"
                        : "within published range"}
                  </small>
                )}
              </div>
            </li>
          ))}
        </ul>
        <p className="data-note" style={{ marginBottom: 0 }}>
          Your timings are synthetic demo data. Benchmarks:{" "}
          {cycles
            .filter((c) => c.bench)
            .map((c) => `${c.name}: ${c.bench!.note}`)
            .join("; ")}
          .
        </p>
      </section>

      <div className="two">
        <section className="card panel">
          <div className="label">Where sites get stuck</div>
          <h2 className="panel__title">Blockers by area</h2>
          {overall.areas.length === 0 ? (
            <p className="muted">Nothing is blocked.</p>
          ) : (
            <ul className="hbar">
              {overall.areas.map((a) => (
                <li key={a.area}>
                  <span className="hbar__l">{a.area.charAt(0).toUpperCase() + a.area.slice(1)}</span>
                  <span className="hbar__t">
                    <i style={{ width: `${(a.sites / areaMax) * 100}%` }} />
                  </span>
                  <b>{a.sites}</b>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card panel">
          <div className="label">Go-live outlook</div>
          <h2 className="panel__title">Projected vs. target date</h2>
          <ul className="hbar">
            {slip.map((s) => (
              <li key={s.key}>
                <span className="hbar__l">{s.label}</span>
                <span className="hbar__t">
                  <i data-bad={s.key !== "on" || undefined} style={{ width: `${(s.n / slipMax) * 100}%` }} />
                </span>
                <b>{s.n}</b>
              </li>
            ))}
          </ul>
        </section>
      </div>
      <div style={{ height: 56 }} />
    </>
  );
}

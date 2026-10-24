/** Hero visual: rings, orbiting dots, a dark central orb and two floating stat cards. */

const W = 600;
const H = 570;
const CX = W / 2;
const CY = H / 2;

function at(r: number, deg: number) {
  const a = (deg * Math.PI) / 180;
  return { left: `${((CX + r * Math.cos(a)) / W) * 100}%`, top: `${((CY + r * Math.sin(a)) / H) * 100}%` };
}

interface Props {
  avgReadiness: number | null;
  sitesInStartup: number;
  blockedSites: number;
  worstDelayDays: number;
}

export default function Orbit({ avgReadiness, sitesInStartup, blockedSites, worstDelayDays }: Props) {
  return (
    <div className="orbit" aria-label="Summary of site activation readiness">
      <svg className="orbit__svg" viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
        <circle className="ring dashed" cx={CX} cy={CY} r={128} />
        <circle className="ring" cx={CX} cy={CY} r={178} />
        <circle className="ring dashed" cx={CX} cy={CY} r={228} />
        <circle className="ring" cx={CX} cy={CY} r={278} />
      </svg>
      <div className="orbit__spin" aria-hidden="true">
        <span className="orbit__dot" style={{ ...at(178, -35), transform: "translate(-50%,-50%)" }} />
        <span className="orbit__dot orbit__dot--pink" style={{ ...at(228, 130), transform: "translate(-50%,-50%)" }} />
        <span className="orbit__dot orbit__dot--white" style={{ ...at(128, 215), transform: "translate(-50%,-50%)" }} />
      </div>
      <div className="orbit__spin orbit__spin--rev" aria-hidden="true">
        <span className="orbit__dot orbit__dot--pink" style={{ ...at(278, 20), transform: "translate(-50%,-50%)" }} />
        <span className="orbit__dot" style={{ ...at(228, 300), transform: "translate(-50%,-50%)" }} />
      </div>
      <div className="orbit__orb">
        <span className="label">Avg readiness</span>
        <span className="orbit__big">{avgReadiness === null ? "—" : `${Math.round(avgReadiness)}%`}</span>
        <span className="orbit__small">{sitesInStartup} sites in start-up</span>
      </div>
      <div className="orbit__card orbit__card--a">
        <span className="label">Blocked sites</span>
        <strong>{String(blockedSites).padStart(2, "0")}</strong>
      </div>
      <div className="orbit__card orbit__card--b">
        <span className="label">Worst delay</span>
        <strong>{worstDelayDays}D</strong>
      </div>
    </div>
  );
}

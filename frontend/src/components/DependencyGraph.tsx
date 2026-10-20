import type { GraphNode, TrialSiteGraph } from "@/lib/api";
import { fmtDate, roleLabel } from "@/lib/format";

const NW = 206;
const NH = 56;
const GX = 62;
const GY = 14;
const PAD = 12;
const TOP = 22;

/** Layer = longest path from any node with no predecessor, so edges always point right. */
function layers(g: TrialSiteGraph): Map<number, number> {
  const preds = new Map<number, number[]>();
  for (const n of g.nodes) preds.set(n.milestone_id, []);
  for (const e of g.edges) preds.get(e.successor_id)?.push(e.predecessor_id);
  const memo = new Map<number, number>();
  const depth = (id: number): number => {
    const hit = memo.get(id);
    if (hit !== undefined) return hit;
    const ps = preds.get(id) ?? [];
    const d = ps.length ? 1 + Math.max(...ps.map(depth)) : 0;
    memo.set(id, d);
    return d;
  };
  g.nodes.forEach((n) => depth(n.milestone_id));
  return memo;
}

function nodeClass(n: GraphNode) {
  const c = ["node", `node--${n.status}`];
  if (n.is_blocking) c.push("node--blocking");
  else if (n.is_overdue && !n.is_satisfied) c.push("node--overdue");
  return c.join(" ");
}

export default function DependencyGraph({ graph }: { graph: TrialSiteGraph }) {
  const depth = layers(graph);
  const cols = Math.max(0, ...depth.values()) + 1;
  const byCol: GraphNode[][] = Array.from({ length: cols }, () => []);
  for (const n of graph.nodes) byCol[depth.get(n.milestone_id) ?? 0].push(n);
  const tallest = Math.max(...byCol.map((c) => c.length));
  const innerH = tallest * NH + (tallest - 1) * GY;
  const W = PAD * 2 + cols * NW + (cols - 1) * GX;
  const H = TOP + innerH + PAD;

  const pos = new Map<number, { x: number; y: number }>();
  byCol.forEach((col, ci) => {
    const colH = col.length * NH + (col.length - 1) * GY;
    const off = (innerH - colH) / 2;
    col.forEach((n, ri) => pos.set(n.milestone_id, { x: PAD + ci * (NW + GX), y: TOP + off + ri * (NH + GY) }));
  });
  const nodeById = new Map(graph.nodes.map((n) => [n.milestone_id, n]));

  return (
    <div className="scroll-x">
      <svg className="graph" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Milestone dependency graph">
        {byCol.map((_, ci) => (
          <text key={ci} className="col-label" x={PAD + ci * (NW + GX)} y={11}>
            {ci === 0 ? "Start" : ci === cols - 1 ? "Green light" : `Then ${ci}`}
          </text>
        ))}
        {graph.edges.map((e) => {
          const a = pos.get(e.predecessor_id);
          const b = pos.get(e.successor_id);
          if (!a || !b) return null;
          const x1 = a.x + NW;
          const y1 = a.y + NH / 2;
          const x2 = b.x;
          const y2 = b.y + NH / 2;
          const mx = (x1 + x2) / 2;
          const pred = nodeById.get(e.predecessor_id);
          const cls = e.is_satisfied ? "edge--done" : pred?.is_blocking ? "edge--blocking" : "edge--open";
          return <path key={e.id} className={`edge ${cls}`} d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`} />;
        })}
        {graph.nodes.map((n) => {
          const p = pos.get(n.milestone_id)!;
          const sub = [n.due_date ? `Due ${fmtDate(n.due_date)}` : "No due date", n.owner ? roleLabel(n.owner.role) : null].filter(Boolean).join(" · ");
          return (
            <g key={n.milestone_id} className={nodeClass(n)} transform={`translate(${p.x},${p.y})`}>
              <title>{`${n.name} (${n.status.replace("_", " ")})`}</title>
              <rect width={NW} height={NH} rx={3} />
              <circle className="node__badge" cx={14} cy={19} r={4} />
              <text className="node__name" x={26} y={23}>
                {n.name}
              </text>
              <text className="node__sub" x={14} y={43}>
                {sub}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

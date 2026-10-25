import { getTrackedWorld } from "@/lib/api";
import { location } from "@/lib/format";
import { getSession } from "@/lib/session";
import { isSponsor } from "@/lib/session-token";

export const dynamic = "force-dynamic";

/** Sites the signed-in user may open, for the ⌘K palette. Read-only. */
export async function GET() {
  const user = await getSession();
  if (!user) return Response.json({ sites: [] }, { status: 401 });
  try {
    const world = await getTrackedWorld();
    const sites = world
      .flatMap((w) => w.rows.map((r) => ({ ...r, trial: w.trial.acronym ?? w.trial.nct_id })))
      .filter((r) => isSponsor(user.role) || r.site.id === user.siteId)
      .map((r) => ({ id: r.id, name: r.site.name, sub: `${location(r.site)} · ${r.trial}`, health: r.health }));
    return Response.json({ sites });
  } catch {
    return Response.json({ sites: [] }, { status: 503 });
  }
}

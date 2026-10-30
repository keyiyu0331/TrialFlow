import { ApiUnreachable, getTrackedWorld } from "@/lib/api";
import { answer } from "@/lib/ask";
import { getSession } from "@/lib/session";
import { isSponsor } from "@/lib/session-token";

export const dynamic = "force-dynamic";

/** Read-only: answers a question from live status. Never changes data. */
export async function POST(req: Request) {
  const user = await getSession();
  if (!user) return Response.json({ text: "Please sign in first.", links: [] }, { status: 401 });
  const body = await req.json().catch(() => ({}));
  const question = typeof body.question === "string" ? body.question.slice(0, 300) : "";
  try {
    const world = await getTrackedWorld();
    return Response.json(
      answer(
        question,
        world.flatMap((w) => w.details).filter((d) => isSponsor(user.role) || d.site.id === user.siteId),
      ),
    );
  } catch (e) {
    const msg =
      e instanceof ApiUnreachable
        ? "The API is not reachable. Start the backend and try again."
        : "Something went wrong reading the data.";
    return Response.json({ text: msg, links: [] }, { status: 503 });
  }
}

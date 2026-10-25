import { answer } from "@/lib/ask";
import { ApiUnreachable, getTrackedWorld } from "@/lib/api";

export const dynamic = "force-dynamic";

/** Read-only: answers a question from live status. Never changes data. */
export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const question = typeof body.question === "string" ? body.question.slice(0, 300) : "";
  try {
    const world = await getTrackedWorld();
    return Response.json(answer(question, world.flatMap((w) => w.details)));
  } catch (e) {
    const msg = e instanceof ApiUnreachable ? "The API is not reachable. Start the backend and try again." : "Something went wrong reading the data.";
    return Response.json({ text: msg, links: [] }, { status: 503 });
  }
}

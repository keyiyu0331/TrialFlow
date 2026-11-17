import { ApiUnreachable, getTrackedWorld, SERVER_API } from "@/lib/api";
import { type Answer, answer } from "@/lib/ask";
import { getSession } from "@/lib/session";
import type { SessionUser } from "@/lib/session-token";
import { isSponsor } from "@/lib/session-token";

export const dynamic = "force-dynamic";

const MAX_QUESTION = 300;
const MAX_HISTORY = 10;
/** A little over the backend's own 20s budget, so its 503 arrives before we give up. */
const CLAUDE_TIMEOUT_MS = 25_000;

interface Turn {
  role: "user" | "assistant";
  text: string;
}

function cleanHistory(raw: unknown): Turn[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((t) => t && (t.role === "user" || t.role === "assistant") && typeof t.text === "string" && t.text.trim())
    .slice(-MAX_HISTORY)
    .map((t) => ({ role: t.role, text: String(t.text).slice(0, 4000) }));
}

/** Claude via the FastAPI assistant. Null when it is not configured, fails, or times out. */
async function askClaude(user: SessionUser, question: string, history: Turn[]): Promise<Answer | null> {
  try {
    const res = await fetch(`${SERVER_API}/assistant/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history, role: user.role, site_id: user.siteId }),
      cache: "no-store",
      signal: AbortSignal.timeout(CLAUDE_TIMEOUT_MS),
    });
    return res.ok ? ((await res.json()) as Answer) : null;
  } catch {
    return null;
  }
}

/**
 * Read-only: answers a question from live status. Never changes data.
 * Tries Claude first (backend /assistant/ask); falls back to the rule-based answer in lib/ask.ts
 * when no API key is set, the model call fails, or it times out.
 */
export async function POST(req: Request) {
  const user = await getSession();
  if (!user) return Response.json({ text: "Please sign in first.", links: [] }, { status: 401 });
  const body = await req.json().catch(() => ({}));
  const question = typeof body.question === "string" ? body.question.trim().slice(0, MAX_QUESTION) : "";

  if (question) {
    const claude = await askClaude(user, question, cleanHistory(body.history));
    if (claude) return Response.json(claude);
  }

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

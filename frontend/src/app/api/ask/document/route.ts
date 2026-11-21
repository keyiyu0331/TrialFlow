import { SERVER_API } from "@/lib/api";
import { getSession } from "@/lib/session";

export const dynamic = "force-dynamic";

const MAX_BYTES = 2 * 1024 * 1024;
/** The backend gives Claude 20s, then falls back to a rule-based summary. */
const TIMEOUT_MS = 30_000;

/**
 * Summarizes and categorizes an uploaded site document (PDF, .txt or .md).
 * A suggestion only: the backend never changes a milestone and never stores the file.
 */
export async function POST(req: Request) {
  const user = await getSession();
  if (!user) return Response.json({ detail: "Please sign in first.", code: "unauthorized" }, { status: 401 });

  const form = await req.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof File)) {
    return Response.json({ detail: "Choose a file to upload.", code: "no_file" }, { status: 400 });
  }
  if (file.size > MAX_BYTES) {
    return Response.json({ detail: "The file is larger than 2 MB.", code: "file_too_large" }, { status: 413 });
  }

  try {
    const res = await fetch(`${SERVER_API}/assistant/document?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: await file.arrayBuffer(),
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    return Response.json(await res.json(), { status: res.status });
  } catch {
    return Response.json(
      { detail: "The API is not reachable. Start the backend and try again.", code: "api_unreachable" },
      { status: 503 },
    );
  }
}

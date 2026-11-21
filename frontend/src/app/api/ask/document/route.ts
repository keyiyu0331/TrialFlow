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

  // Refuse an oversized upload before reading it. (The form adds a little overhead, so allow some slack.)
  const declared = Number(req.headers.get("content-length") ?? 0);
  if (declared > MAX_BYTES + 64 * 1024) {
    return Response.json({ detail: "The file is larger than 2 MB.", code: "file_too_large" }, { status: 413 });
  }

  const form = await req.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof File)) {
    return Response.json({ detail: "Choose a file to upload.", code: "no_file" }, { status: 400 });
  }
  if (file.size > MAX_BYTES) {
    return Response.json({ detail: "The file is larger than 2 MB.", code: "file_too_large" }, { status: 413 });
  }

  let res: Response;
  try {
    res = await fetch(`${SERVER_API}/assistant/document?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: await file.arrayBuffer(),
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch {
    return Response.json(
      { detail: "The API is not reachable. Start the backend and try again.", code: "api_unreachable" },
      { status: 503 },
    );
  }
  // The API answered. If the body is not JSON (a plain-text 500, say), that is a server error, not "unreachable".
  const body = await res.json().catch(() => null);
  if (body === null) {
    return Response.json(
      { detail: "The server could not process that file. Try a different one.", code: "server_error" },
      { status: 502 },
    );
  }
  return Response.json(body, { status: res.status });
}

import { type NextRequest, NextResponse } from "next/server";
import { COOKIE, decodeSession, isSponsor } from "@/lib/session-token";

/** Site staff may only use their tasks and their own site's pages. */
const SITE_STAFF_PATHS = [/^\/tasks/, /^\/sites\//, /^\/api\//];

export function proxy(req: NextRequest) {
  const { pathname, search } = req.nextUrl;
  const user = decodeSession(req.cookies.get(COOKIE)?.value);
  const home = user && isSponsor(user.role) ? "/" : "/tasks";

  if (pathname.startsWith("/login")) {
    return user ? NextResponse.redirect(new URL(home, req.url)) : NextResponse.next();
  }
  if (!user) {
    if (pathname.startsWith("/api/"))
      return NextResponse.json({ text: "Please sign in first.", links: [] }, { status: 401 });
    const url = new URL("/login", req.url);
    if (pathname !== "/") url.searchParams.set("next", pathname + search);
    return NextResponse.redirect(url);
  }
  if (!isSponsor(user.role) && !SITE_STAFF_PATHS.some((r) => r.test(pathname))) {
    return NextResponse.redirect(new URL("/tasks", req.url));
  }
  return NextResponse.next();
}

export const config = { matcher: ["/((?!_next/static|_next/image|icon.svg|favicon.ico).*)"] };

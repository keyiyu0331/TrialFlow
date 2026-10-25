import { cookies } from "next/headers";
import { COOKIE, decodeSession, type SessionUser } from "./session-token";

export async function getSession(): Promise<SessionUser | null> {
  return decodeSession((await cookies()).get(COOKIE)?.value);
}

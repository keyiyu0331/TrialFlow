/** Signed session cookie (HMAC-SHA256). Demo-grade auth: proves who you are to the frontend; the API does not enforce roles. */
import { createHmac, timingSafeEqual } from "node:crypto";

export interface SessionUser {
  id: number;
  name: string;
  email: string;
  role: string;
  siteId: number | null;
}

export const COOKIE = "tf_session";
export const MAX_AGE = 60 * 60 * 8;
const SECRET = process.env.AUTH_SECRET ?? "trialflow-dev-secret-change-me";

/** Sponsor/CRO staff see the whole portfolio; everyone else is site staff. */
const SPONSOR_ROLES = new Set(["startup_manager", "cra", "sponsor_supply"]);
export const isSponsor = (role: string) => SPONSOR_ROLES.has(role);

const sign = (payload: string) => createHmac("sha256", SECRET).update(payload).digest("base64url");

export function encodeSession(user: SessionUser): string {
  const payload = Buffer.from(JSON.stringify({ ...user, exp: Math.floor(Date.now() / 1000) + MAX_AGE })).toString("base64url");
  return `${payload}.${sign(payload)}`;
}

export function decodeSession(token: string | undefined | null): SessionUser | null {
  if (!token) return null;
  const [payload, sig] = token.split(".");
  if (!payload || !sig) return null;
  const a = Buffer.from(sig);
  const b = Buffer.from(sign(payload));
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;
  try {
    const { exp, ...user } = JSON.parse(Buffer.from(payload, "base64url").toString());
    return exp > Date.now() / 1000 ? (user as SessionUser) : null;
  } catch {
    return null;
  }
}

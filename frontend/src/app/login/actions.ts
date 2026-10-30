"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ApiUnreachable, getUsers, type User } from "@/lib/api";
import { COOKIE, MAX_AGE, encodeSession, isSponsor } from "@/lib/session-token";

export interface LoginState {
  error?: string;
  /** Echoed back so the form keeps what was typed after a failed attempt. */
  email?: string;
}

/** Shared demo password for the synthetic users. Set TRIALFLOW_DEMO_PASSWORD to change it. */
const DEMO_PASSWORD = process.env.TRIALFLOW_DEMO_PASSWORD ?? "trialflow";

const safeNext = (next: FormDataEntryValue | null) => (typeof next === "string" && next.startsWith("/") && !next.startsWith("//") ? next : null);

async function start(user: User, next: string | null): Promise<never> {
  (await cookies()).set(
    COOKIE,
    encodeSession({ id: user.id, name: user.name, email: user.email, role: user.role, siteId: user.site_id }),
    { httpOnly: true, sameSite: "lax", path: "/", maxAge: MAX_AGE },
  );
  redirect(isSponsor(user.role) ? (next ?? "/") : "/tasks");
}

async function findUser(email: string): Promise<User | null | "down"> {
  try {
    return (await getUsers()).find((u) => u.email.toLowerCase() === email.trim().toLowerCase()) ?? null;
  } catch (e) {
    if (e instanceof ApiUnreachable) return "down";
    throw e;
  }
}

export async function signIn(_prev: LoginState, form: FormData): Promise<LoginState> {
  const email = String(form.get("email") ?? "");
  const password = String(form.get("password") ?? "");
  const portal = form.get("portal");
  const user = await findUser(email);
  if (user === "down") return { error: "The API is not reachable. Start the backend and try again.", email };
  if (!user || password !== DEMO_PASSWORD) return { error: "That email or password is not right.", email };
  if (portal === "sponsor" && !isSponsor(user.role)) return { error: "That is a site staff account. Choose Site staff above.", email };
  if (portal === "site" && isSponsor(user.role)) return { error: "That is a sponsor account. Choose Start-up manager above.", email };
  return start(user, safeNext(form.get("next")));
}

/** One-click demo sign-in for a synthetic user (no password). */
export async function demoSignIn(form: FormData): Promise<void> {
  const user = await findUser(String(form.get("email") ?? ""));
  if (!user || user === "down") redirect("/login");
  await start(user, null);
}

export async function signOut(): Promise<void> {
  (await cookies()).delete(COOKIE);
  redirect("/login");
}

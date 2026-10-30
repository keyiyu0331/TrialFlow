import LoginForm from "@/components/LoginForm";
import { ApiUnreachable, getTrackedWorld, getUsers, type User } from "@/lib/api";
import { openTasks } from "@/lib/insights";

export const metadata = { title: "Sign in · TrialFlow" };
export const dynamic = "force-dynamic";

export default async function Login({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  let manager: User | undefined;
  let staff: User | undefined;
  let down = false;
  try {
    const users = await getUsers();
    manager = users.find((u) => u.role === "startup_manager");
    // Offer the site coordinator with the most open work, so the demo account has something to do.
    const coordinators = users.filter((u) => u.role === "site_coordinator");
    staff = coordinators[0];
    try {
      const open = openTasks((await getTrackedWorld()).flatMap((w) => w.details));
      const load = new Map<number, number>();
      for (const t of open)
        if (t.milestone.owner) load.set(t.milestone.owner.id, (load.get(t.milestone.owner.id) ?? 0) + 1);
      staff = [...coordinators].sort((a, b) => (load.get(b.id) ?? 0) - (load.get(a.id) ?? 0))[0] ?? staff;
    } catch {
      /* fall back to the first coordinator */
    }
  } catch (e) {
    if (!(e instanceof ApiUnreachable)) throw e;
    down = true;
  }
  return <LoginForm next={next ?? ""} manager={manager} staff={staff} apiDown={down} />;
}

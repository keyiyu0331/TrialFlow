import Link from "next/link";
import PersonSelect from "@/components/PersonSelect";
import TaskList from "@/components/TaskList";
import { ApiUnreachable, getTrackedWorld } from "@/lib/api";
import { roleLabel } from "@/lib/format";
import { getSession } from "@/lib/session";
import { isSponsor } from "@/lib/session-token";
import { TASK_LABEL, openTasks, peopleFrom, type TaskKind } from "@/lib/insights";

export const metadata = { title: "My tasks · TrialFlow" };

type Search = { role?: string; person?: string; kind?: string };
const LIMIT = 60;

function href(p: Record<string, string | undefined>) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(p)) if (v) q.set(k, v);
  return q.toString() ? `/tasks?${q}` : "/tasks";
}

export default async function Tasks({ searchParams }: { searchParams: Promise<Search> }) {
  const sp = await searchParams;
  const user = await getSession();
  const sponsor = !user || isSponsor(user.role);
  let world;
  try {
    world = await getTrackedWorld();
  } catch (e) {
    if (e instanceof ApiUnreachable) {
      return (
        <section className="section" style={{ paddingTop: 48 }}>
          <div className="notice">The API is not reachable. Start the backend, then reload.</div>
        </section>
      );
    }
    throw e;
  }

  // Site staff only ever see their own site; by default just their own tasks.
  const siteDetails = world.flatMap((w) => w.details).filter((d) => sponsor || d.site.id === user?.siteId);
  const all = openTasks(siteDetails);
  const everyone = sp.person === "all";
  const people = peopleFrom(all);
  const roles = [...new Set(people.map((p) => p.role))].sort();
  const role = roles.find((r) => r === sp.role);
  const inRole = role ? people.filter((p) => p.role === role) : people;
  const person = sponsor ? inRole.find((p) => String(p.id) === sp.person) : everyone ? undefined : inRole.find((p) => p.id === user?.id) ?? { id: user!.id, name: user!.name, role: user!.role, team_name: null, tasks: 0 };
  const kind = (Object.keys(TASK_LABEL) as TaskKind[]).find((k) => k === sp.kind);

  const scoped = all.filter(
    (t) => (!role || t.milestone.owner?.role === role) && (!person || t.milestone.owner?.id === person.id),
  );
  const shown = scoped.filter((t) => !kind || t.kind === kind);
  const counts = (Object.keys(TASK_LABEL) as TaskKind[]).map((k) => [k, scoped.filter((t) => t.kind === k).length] as const);

  const options = [
    { value: "", label: `Everyone${role ? ` (${roleLabel(role)})` : ""}`, href: href({ role, kind: sp.kind }) },
    ...inRole.map((p) => ({
      value: String(p.id),
      label: `${p.name} · ${roleLabel(p.role)} (${p.tasks})`,
      href: href({ role, person: String(p.id), kind: sp.kind }),
    })),
  ];

  return (
    <section className="section" style={{ paddingTop: 48 }}>
      <div className="section__head">
        <div>
          <div className="label">{sponsor ? "Everyone's open work" : "Your site"}</div>
          <h1 className="section__title">{sponsor ? "My tasks" : `Hi ${user?.name.split(" ")[0]}, here is your list`}</h1>
          <p className="section__sub">
            {sponsor
              ? "Open milestones assigned to each person, most urgent first. Pick someone, update a status, and the dashboard recomputes."
              : "Your open milestones, most urgent first. You can update the ones you own. Switch to see what everyone else at your site is working on."}
          </p>
        </div>
      </div>

      {!sponsor && (
        <div className="filters">
          <div className="filter-group">
            <span className="label">Show</span>
            <Link href={href({ kind: sp.kind })} className={`pill ${!everyone ? "pill--active" : ""}`}>Mine</Link>
            <Link href={href({ person: "all", kind: sp.kind })} className={`pill ${everyone ? "pill--active" : ""}`}>Everyone at my site</Link>
          </div>
        </div>
      )}
      {sponsor && (
      <div className="filters">
        <div className="filter-group">
          <span className="label">Role</span>
          <Link href={href({ kind: sp.kind })} className={`pill ${!role ? "pill--active" : ""}`}>All</Link>
          {roles.map((r) => (
            <Link key={r} href={href({ role: r, kind: sp.kind })} className={`pill ${role === r ? "pill--active" : ""}`}>
              {roleLabel(r)}
            </Link>
          ))}
        </div>
        <div className="filter-group">
          <span className="label">Person</span>
          <PersonSelect options={options} value={person ? String(person.id) : ""} />
        </div>
      </div>
      )}
      <div className="filters">
        <div className="filter-group">
          <span className="label">Show</span>
          <Link href={href({ role, person: person && String(person.id) })} className={`pill ${!kind ? "pill--active" : ""}`}>
            All ({scoped.length})
          </Link>
          {counts
            .filter(([, n]) => n > 0)
            .map(([k, n]) => (
              <Link
                key={k}
                href={href({ role, person: person && String(person.id), kind: k })}
                className={`pill ${kind === k ? "pill--active" : ""}`}
              >
                {TASK_LABEL[k]} ({n})
              </Link>
            ))}
        </div>
      </div>
      <p className="data-note">Owners, tasks and dates are synthetic demo data.</p>

      {shown.length === 0 ? (
        <div className="card empty">
          <h3>No open tasks</h3>
          <p>Nothing matches these filters.</p>
        </div>
      ) : (
        <div className="card panel">
          <TaskList tasks={shown.slice(0, LIMIT)} showOwner={!person} />
          {shown.length > LIMIT && <p className="data-note" style={{ marginTop: 14 }}>Showing the {LIMIT} most urgent of {shown.length}. Narrow by role or person.</p>}
        </div>
      )}
    </section>
  );
}

import { signOut } from "@/app/login/actions";
import { roleLabel } from "@/lib/format";
import type { SessionUser } from "@/lib/session-token";

export default function UserMenu({ user }: { user: SessionUser }) {
  const initials = user.name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <details className="usermenu">
      <summary className="avatar" aria-label={`Signed in as ${user.name}`}>
        {initials}
        <span className="avatar__dot" />
      </summary>
      <div className="usermenu__pop">
        <div className="usermenu__name">{user.name}</div>
        <div className="usermenu__meta">{roleLabel(user.role)}</div>
        <div className="usermenu__meta">{user.email}</div>
        <form action={signOut}>
          <button className="btn" style={{ width: "100%", marginTop: 12 }}>
            Sign out
          </button>
        </form>
      </div>
    </details>
  );
}

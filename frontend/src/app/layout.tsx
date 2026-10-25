import type { Metadata } from "next";
import Link from "next/link";
import "@fontsource-variable/inter-tight";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./globals.css";
import Logo from "@/components/Logo";
import AskTrialFlow from "@/components/AskTrialFlow";
import NavTabs from "@/components/NavTabs";
import { SessionProvider } from "@/components/SessionProvider";
import UserMenu from "@/components/UserMenu";
import { getSession } from "@/lib/session";
import { isSponsor } from "@/lib/session-token";

export const metadata: Metadata = {
  title: "TrialFlow · Site activation readiness",
  description: "See which milestone is blocking each trial site, and who owns the next action.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const user = await getSession();
  if (!user) {
    return (
      <html lang="en">
        <body>{children}</body>
      </html>
    );
  }
  const sponsor = isSponsor(user.role);
  return (
    <html lang="en">
      <body>
        <SessionProvider me={{ id: user.id, name: user.name, role: user.role, sponsor }}>
        <div className="bg" aria-hidden="true">
          <div className="bg__grid" />
          <div className="bg__glow" />
          <div className="bg__glow bg__glow--2" />
          <div className="bg__line" />
        </div>
        <div className="wrap">
          <header className="topbar">
            <Link href="/" aria-label="TrialFlow home">
              <Logo />
            </Link>
            <div className="topbar__right">
              <span className="btn-ghost" title="Trials and sites are real; activation data is synthetic">
                Demo data
              </span>
              <UserMenu user={user} />
            </div>
          </header>
          <NavTabs sponsor={sponsor} />
          <main>{children}</main>
          <footer className="footer">
            <div>
              <strong>TrialFlow</strong> · CS 146S class project. Proves the workflow, not a production system.
            </div>
            <div>
              Trials and sites: real, from ClinicalTrials.gov. Milestones, owners, dates and history: synthetic, generated for the demo.
            </div>
          </footer>
        </div>
        <AskTrialFlow />
        </SessionProvider>
      </body>
    </html>
  );
}

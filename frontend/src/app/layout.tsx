import type { Metadata } from "next";
import Link from "next/link";
import "@fontsource-variable/inter-tight";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./globals.css";
import Logo from "@/components/Logo";
import NavTabs from "@/components/NavTabs";

export const metadata: Metadata = {
  title: "TrialFlow · Site activation readiness",
  description: "See which milestone is blocking each trial site, and who owns the next action.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
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
              <span className="avatar" title="Study start-up manager (synthetic user)">
                SM
                <span className="avatar__dot" />
              </span>
            </div>
          </header>
          <NavTabs />
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
      </body>
    </html>
  );
}

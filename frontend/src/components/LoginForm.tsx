"use client";

import { useActionState, useState } from "react";
import { demoSignIn, signIn, type LoginState } from "@/app/login/actions";
import type { User } from "@/lib/api";
import Logo from "./Logo";

const CHAIN = [
  { n: "IRB approval", s: "done" },
  { n: "Contract", s: "done" },
  { n: "Budget", s: "done" },
  { n: "Pharmacy setup", s: "blocked" },
  { n: "Drug shipment", s: "wait" },
  { n: "Green light", s: "wait" },
];

export default function LoginForm({ next, manager, staff, apiDown }: { next: string; manager?: User; staff?: User; apiDown: boolean }) {
  const [portal, setPortal] = useState<"sponsor" | "site">("sponsor");
  const [state, action, pending] = useActionState<LoginState, FormData>(signIn, {});
  const hint = portal === "sponsor" ? manager : staff;

  return (
    <main className="login">
      <section className="login__story">
        <Logo />
        <div className="login__copy">
          <p className="login__kicker">SITE ACTIVATION, MADE VISIBLE</p>
          <h1>
            One trial.
            <br />
            <em>Every site, ready.</em>
          </h1>
          <p>See which milestone is holding each site back, who owns the next step, and when it will really go live.</p>
        </div>
        <ol className="login__chain" aria-hidden="true">
          {CHAIN.map((c) => (
            <li key={c.n} data-s={c.s}>
              <i />
              <span>{c.n}</span>
            </li>
          ))}
        </ol>
        <div className="login__foot">
          <span>REAL TRIALS · SYNTHETIC ACTIVATION DATA</span>
        </div>
      </section>

      <section className="login__auth">
        <div className="login__inner">
          <p className="login__kicker login__kicker--dark">WELCOME BACK</p>
          <h2>Sign in to TrialFlow</h2>
          <p className="login__intro">Choose the view that fits your role.</p>

          <div className="login__roles" role="tablist" aria-label="Choose a role">
            <button type="button" role="tab" aria-selected={portal === "sponsor"} className={portal === "sponsor" ? "on" : ""} onClick={() => setPortal("sponsor")}>
              <b>01</b>
              <span>
                <strong>Start-up manager</strong>
                <small>Every site, one view</small>
              </span>
            </button>
            <button type="button" role="tab" aria-selected={portal === "site"} className={portal === "site" ? "on" : ""} onClick={() => setPortal("site")}>
              <b>02</b>
              <span>
                <strong>Site staff</strong>
                <small>Your tasks, your site</small>
              </span>
            </button>
          </div>

          <form action={action} className="login__form">
            <input type="hidden" name="portal" value={portal} />
            <input type="hidden" name="next" value={next} />
            <label htmlFor="email">Email</label>
            <input id="email" name="email" type="email" required autoComplete="username" defaultValue={state.email ?? ""} key={state.email ?? "new"} placeholder={hint?.email ?? "name@example.org"} />
            <label htmlFor="password">Password</label>
            <input id="password" name="password" type="password" required autoComplete="current-password" placeholder="Demo password: trialflow" />
            {state.error && (
              <p className="login__error" role="alert">
                {state.error}
              </p>
            )}
            {apiDown && (
              <p className="login__error" role="alert">
                The API is not reachable. Start the backend, then reload.
              </p>
            )}
            <button className="login__submit" disabled={pending}>
              {pending ? "Signing in…" : `Continue as ${portal === "sponsor" ? "start-up manager" : "site staff"}`} <span aria-hidden="true">↗</span>
            </button>
          </form>

          <div className="login__divider">
            <span>OR TRY A DEMO ACCOUNT</span>
          </div>
          <div className="login__demos">
            {manager && (
              <form action={demoSignIn}>
                <input type="hidden" name="email" value={manager.email} />
                <button>
                  <strong>{manager.name}</strong>
                  <small>Start-up manager · sees everything</small>
                </button>
              </form>
            )}
            {staff && (
              <form action={demoSignIn}>
                <input type="hidden" name="email" value={staff.email} />
                <button>
                  <strong>{staff.name}</strong>
                  <small>Site coordinator · own site only</small>
                </button>
              </form>
            )}
          </div>
          <p className="login__note">
            Prototype sign-in. Accounts are the synthetic users in the demo data, and every one uses the demo password. The backend does not enforce roles yet.
          </p>
        </div>
      </section>
    </main>
  );
}

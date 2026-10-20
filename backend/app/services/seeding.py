"""Synthetic site activation data for the demo.

The registry has no activation data (see docs/data-mapping.md), so this module
builds a labeled synthetic subset: it picks real trial sites from the imported
registry data and gives each one a scenario (on track, contract stall, IRB delay,
and so on). Everything it writes has ``source_type = synthetic``, and a site's
registry ``reported_recruitment_status`` is never used to decide activation.

Dates are laid out relative to ``as_of`` so the scenarios stay live whenever the
seed is run. ``expected_health`` documents what each scenario should look like on
the dashboard and is checked by tests.
"""

import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import models as m
from ..enums import (
    SATISFIED_STATUSES,
    ActivationStatus,
    EventType,
    MilestoneStatus,
    SiteHealth,
    SourceType,
    UserRole,
)
from .templates import DEFAULT_TEMPLATES, ensure_templates, instantiate_trial_site

# (NCT ID, number of trial sites to put into start-up). Both trials have many real, named US sites.
SEED_TRIALS: tuple[tuple[str, int], ...] = (("NCT07578116", 12), ("NCT06312176", 6))

C, P, NA = "complete", "in_progress", "na"


def _blocked(reason: str) -> str:
    return f"blocked:{reason}"


def _done(*codes: str) -> dict[str, str]:
    return {code: C for code in codes}


_EIGHT = (
    "IRB_APPROVAL", "CONTRACT_EXECUTED", "BUDGET_FINALIZED", "REGULATORY_DOCS",
    "STAFF_TRAINING", "PHARMACY_SETUP", "LAB_SYSTEMS_ACCESS", "DRUG_SHIPMENT",
)
_ALL_BUT = lambda *skip: _done(*(c for c in _EIGHT if c not in skip))  # noqa: E731


@dataclass(frozen=True)
class Scenario:
    label: str
    selected_days_ago: int
    states: dict[str, str]
    expected_health: SiteHealth
    due_shift: dict[str, int] = field(default_factory=dict)
    activation: ActivationStatus = ActivationStatus.in_startup


SCENARIOS: dict[str, Scenario] = {s.label: s for s in (
    Scenario("contract_stall", 80,
             {**_ALL_BUT("CONTRACT_EXECUTED"), "CONTRACT_EXECUTED": _blocked("Legal review: indemnification language unresolved")},
             SiteHealth.blocked),
    Scenario("irb_delay", 75, {**_ALL_BUT("IRB_APPROVAL", "DRUG_SHIPMENT"), "IRB_APPROVAL": P}, SiteHealth.blocked),
    Scenario("irb_delay_long", 100, {**_ALL_BUT("IRB_APPROVAL", "DRUG_SHIPMENT"), "IRB_APPROVAL": P}, SiteHealth.blocked),
    Scenario("budget_dispute", 62,
             {**_ALL_BUT("CONTRACT_EXECUTED", "BUDGET_FINALIZED"), "CONTRACT_EXECUTED": P,
              "BUDGET_FINALIZED": _blocked("Awaiting sponsor response on per-visit rates")},
             SiteHealth.blocked),
    Scenario("pharmacy_delay", 55,
             {**_done("IRB_APPROVAL", "BUDGET_FINALIZED", "REGULATORY_DOCS", "STAFF_TRAINING", "LAB_SYSTEMS_ACCESS"),
              "CONTRACT_EXECUTED": P, "PHARMACY_SETUP": P},
             SiteHealth.blocked),
    Scenario("shipment_late", 66, {**_ALL_BUT("DRUG_SHIPMENT"), "DRUG_SHIPMENT": P}, SiteHealth.blocked),
    Scenario("lab_access_delay", 45,
             {**_done("IRB_APPROVAL", "BUDGET_FINALIZED", "REGULATORY_DOCS", "STAFF_TRAINING", "PHARMACY_SETUP"),
              "CONTRACT_EXECUTED": P, "LAB_SYSTEMS_ACCESS": P},
             SiteHealth.blocked),
    Scenario("training_gap", 50,
             {**_ALL_BUT("CONTRACT_EXECUTED", "STAFF_TRAINING"), "CONTRACT_EXECUTED": P, "STAFF_TRAINING": P},
             SiteHealth.blocked),
    Scenario("on_hold", 90,
             {**_ALL_BUT("CONTRACT_EXECUTED"), "CONTRACT_EXECUTED": _blocked("Site paused start-up pending PI change")},
             SiteHealth.blocked, activation=ActivationStatus.on_hold),
    Scenario("at_risk_slack", 60, {**_ALL_BUT("CONTRACT_EXECUTED"), "CONTRACT_EXECUTED": P},
             SiteHealth.at_risk, due_shift={"CONTRACT_EXECUTED": 5}),
    Scenario("on_track_mid", 40,
             {**_done("BUDGET_FINALIZED", "REGULATORY_DOCS", "STAFF_TRAINING", "PHARMACY_SETUP", "LAB_SYSTEMS_ACCESS"),
              "IRB_APPROVAL": P, "CONTRACT_EXECUTED": P},
             SiteHealth.on_track),
    Scenario("on_track_early", 14,
             {"REGULATORY_DOCS": C, "IRB_APPROVAL": P, "CONTRACT_EXECUTED": P, "BUDGET_FINALIZED": P, "STAFF_TRAINING": P},
             SiteHealth.on_track),
    Scenario("na_pharmacy", 35,
             {**_done("REGULATORY_DOCS", "STAFF_TRAINING", "BUDGET_FINALIZED", "LAB_SYSTEMS_ACCESS"),
              "PHARMACY_SETUP": NA, "DRUG_SHIPMENT": NA, "IRB_APPROVAL": P, "CONTRACT_EXECUTED": P},
             SiteHealth.on_track),
    Scenario("almost_ready", 66, {**_ALL_BUT(), "SIV": P}, SiteHealth.on_track),
    Scenario("green_light_pending", 70, {**_ALL_BUT(), "SIV": C, "GREEN_LIGHT": P}, SiteHealth.on_track),
    Scenario("activated_a", 105, {**_ALL_BUT(), "SIV": C, "GREEN_LIGHT": C}, SiteHealth.activated,
             activation=ActivationStatus.activated),
    Scenario("activated_b", 130, {**_ALL_BUT(), "SIV": C, "GREEN_LIGHT": C}, SiteHealth.activated,
             activation=ActivationStatus.activated),
)}

# Scenario per seeded site, in the order sites are picked for each trial.
TRIAL_PLANS: dict[str, tuple[str, ...]] = {
    "NCT07578116": ("contract_stall", "irb_delay", "budget_dispute", "pharmacy_delay", "shipment_late",
                    "on_track_mid", "on_track_early", "almost_ready", "activated_a", "lab_access_delay",
                    "training_gap", "at_risk_slack"),
    "NCT06312176": ("irb_delay_long", "green_light_pending", "na_pharmacy", "on_hold", "activated_b", "on_track_mid"),
}

COMPLETION_NOTES = {
    "IRB_APPROVAL": "Approval letter received",
    "CONTRACT_EXECUTED": "Fully executed CTA received",
    "BUDGET_FINALIZED": "Budget signed off by site and sponsor",
    "REGULATORY_DOCS": "1572, CVs, and delegation log filed",
    "STAFF_TRAINING": "GCP and protocol training complete",
    "PHARMACY_SETUP": "Storage and accountability log verified",
    "LAB_SYSTEMS_ACCESS": "Lab kits and system logins confirmed",
    "DRUG_SHIPMENT": "Shipment received and logged",
    "SIV": "Initiation visit complete, no open gating items",
    "GREEN_LIGHT": "Sponsor authorized enrollment",
}

FIRST_NAMES = ("Amara", "Jonas", "Lucia", "Devon", "Mei", "Tariq", "Sofia", "Owen", "Ingrid", "Rahul", "Nadia", "Caleb")
LAST_NAMES = ("Okoye", "Brandt", "Moreno", "Hale", "Tanaka", "Haddad", "Rossi", "Quinn", "Lund", "Mehta", "Farah", "Whitaker")


@dataclass(frozen=True)
class SeedResult:
    trial_sites: int
    users: int
    events: int


def _at(day: date, hour: int = 15) -> datetime:
    return datetime.combine(day, time(hour, 0), tzinfo=timezone.utc)


def _spread(items: list, count: int) -> list:
    """Pick ``count`` items spread evenly across the list, so sites vary in location."""
    if count >= len(items):
        return list(items)
    if count == 1:
        return [items[0]]
    return [items[round(i * (len(items) - 1) / (count - 1))] for i in range(count)]


def is_seeded(session: Session) -> bool:
    return session.scalar(select(m.TrialSite.id).where(m.TrialSite.scenario_label.is_not(None)).limit(1)) is not None


def clear_seed(session: Session) -> None:
    """Remove all synthetic activation data and put the trial sites back to the imported state."""
    seeded = select(m.TrialSite.id).where(m.TrialSite.scenario_label.is_not(None))
    milestone_ids = select(m.Milestone.id).where(m.Milestone.trial_site_id.in_(seeded))
    session.execute(delete(m.MilestoneEvent).where(m.MilestoneEvent.milestone_id.in_(milestone_ids)))
    session.execute(delete(m.MilestoneDependency).where(m.MilestoneDependency.trial_site_id.in_(seeded)))
    session.execute(delete(m.Milestone).where(m.Milestone.trial_site_id.in_(seeded)))
    for ts in session.scalars(select(m.TrialSite).where(m.TrialSite.scenario_label.is_not(None))).all():
        ts.activation_status = ActivationStatus.selected
        ts.selected_date = ts.target_activation_date = ts.actual_activation_date = None
        ts.scenario_label = None
        ts.source_type = SourceType.public_registry
    session.execute(delete(m.User).where(m.User.source_type == SourceType.synthetic))
    session.flush()


def seed(session: Session, as_of: date, seed_trials: tuple[tuple[str, int], ...] = SEED_TRIALS,
         rng_seed: int = 7) -> SeedResult:
    """Create the synthetic subset. Raises ValueError if it was already seeded."""
    if is_seeded(session):
        raise ValueError("already seeded; call clear_seed first")
    rng = random.Random(rng_seed)
    ensure_templates(session)
    sponsor = _sponsor_users(session)
    cra_cycle = 0
    picked_total = events_total = 0

    for nct_id, count in seed_trials:
        trial = session.scalar(select(m.Trial).where(m.Trial.nct_id == nct_id))
        if trial is None:
            continue
        eligible = session.scalars(
            select(m.TrialSite).join(m.Site).where(m.TrialSite.trial_id == trial.id, ~m.Site.is_placeholder_name)
            .order_by(m.TrialSite.ctgov_location_index)
        ).all()
        plan = TRIAL_PLANS[nct_id]
        picked = _spread(list(eligible), min(count, len(plan)))
        trial.target_site_count = len(picked)
        trial.target_fpi_date = as_of + timedelta(days=30)

        for ts, label in zip(picked, plan):
            site_users = _site_users(session, ts.site)
            owners = {**site_users, UserRole.startup_manager: sponsor["manager"],
                      UserRole.sponsor_supply: sponsor["supply"],
                      UserRole.cra: sponsor["cras"][cra_cycle % len(sponsor["cras"])]}
            cra_cycle += 1
            events_total += _apply_scenario(session, ts, SCENARIOS[label], owners, as_of, rng)
            picked_total += 1

    session.flush()
    return SeedResult(trial_sites=picked_total, users=_count_users(session), events=events_total)


def _count_users(session: Session) -> int:
    return len(session.scalars(select(m.User.id)).all())


def _sponsor_users(session: Session) -> dict:
    def make(name: str, email: str, role: UserRole, team: str | None = None) -> m.User:
        user = m.User(name=name, email=email, role=role, team_name=team, source_type=SourceType.synthetic)
        session.add(user)
        return user

    users = {
        "manager": make("Priya Nair", "priya.nair@example.org", UserRole.startup_manager),
        "cras": [make("Marco Ruiz", "marco.ruiz@example.org", UserRole.cra),
                 make("Elena Petrova", "elena.petrova@example.org", UserRole.cra)],
        "supply": make("Sponsor clinical supply", "clinical.supply@example.org", UserRole.sponsor_supply,
                       "Sponsor clinical supply"),
    }
    session.flush()
    return users


def _site_users(session: Session, site: m.Site) -> dict[UserRole, m.User]:
    where = site.city or site.name
    first, last = FIRST_NAMES[site.id % len(FIRST_NAMES)], LAST_NAMES[(site.id * 5) % len(LAST_NAMES)]
    first2, last2 = FIRST_NAMES[(site.id + 4) % len(FIRST_NAMES)], LAST_NAMES[(site.id * 3 + 1) % len(LAST_NAMES)]

    def make(role: UserRole, name: str, email: str, team: str | None = None) -> m.User:
        user = m.User(name=name, email=email.lower(), role=role, site_id=site.id, team_name=team,
                      source_type=SourceType.synthetic)
        session.add(user)
        return user

    users = {
        UserRole.regulatory: make(UserRole.regulatory, f"{where} regulatory office", f"regulatory.{site.id}@example.org",
                                  f"{where} regulatory office"),
        UserRole.contracts: make(UserRole.contracts, f"{where} contracts office", f"contracts.{site.id}@example.org",
                                 f"{where} contracts office"),
        UserRole.pharmacist: make(UserRole.pharmacist, f"{where} research pharmacy", f"pharmacy.{site.id}@example.org",
                                  f"{where} research pharmacy"),
        UserRole.site_coordinator: make(UserRole.site_coordinator, f"{first} {last}", f"{first}.{last}.{site.id}@example.org"),
        UserRole.lab_manager: make(UserRole.lab_manager, f"{first2} {last2}", f"{first2}.{last2}.{site.id}@example.org"),
    }
    session.flush()
    return users


def _apply_scenario(session: Session, ts: m.TrialSite, sc: Scenario, owners: dict[UserRole, m.User],
                    as_of: date, rng: random.Random) -> int:
    selected = as_of - timedelta(days=sc.selected_days_ago)
    milestones = instantiate_trial_site(session, ts, selected, owners)
    preds = {spec.code: spec.predecessors for spec in DEFAULT_TEMPLATES}
    last_day = as_of - timedelta(days=1)  # history never reaches into today or the future
    completed_on: dict[str, date] = {}
    events: list[m.MilestoneEvent] = []

    def event(ms: m.Milestone, kind: EventType, old: str | None, new: str | None, when: datetime,
              note: str | None = None) -> None:
        events.append(m.MilestoneEvent(milestone_id=ms.id, changed_by_user_id=ms.owner_user_id, event_type=kind,
                                       old_value=old, new_value=new, note=note, occurred_at=when,
                                       source_type=SourceType.synthetic))

    original_green_due = milestones["GREEN_LIGHT"].due_date
    for spec in sorted(DEFAULT_TEMPLATES, key=lambda s: s.sort_order):
        ms = milestones[spec.code]
        state = sc.states.get(spec.code)
        ms.status_changed_at = _at(selected, 9)  # untouched milestones have been waiting since selection

        shift = sc.due_shift.get(spec.code)
        if shift:
            old_due = ms.due_date
            ms.due_date = old_due + timedelta(days=shift)
            event(ms, EventType.due_date_change, old_due.isoformat(), ms.due_date.isoformat(),
                  _at(as_of - timedelta(days=6)), "Due date moved after a site request")

        if state is None:
            continue
        if state in (C, NA):
            unmet = [p for p in preds[spec.code] if p not in completed_on and sc.states.get(p) != NA]
            if state == C and unmet:
                raise ValueError(f"{sc.label}: {spec.code} complete before {unmet}")

        if state == C:
            lo = max([ms.planned_start_date] + [completed_on[p] for p in preds[spec.code] if p in completed_on])
            if lo > last_day:
                raise ValueError(f"{sc.label}: cannot complete {spec.code} before today")
            done = max(lo, min(min(ms.due_date, last_day) - timedelta(days=rng.randint(0, 4)), last_day))
            started = min(done, ms.planned_start_date + timedelta(days=rng.randint(0, 3)))
            completed_on[spec.code] = done
            ms.status, ms.started_at, ms.completed_at = MilestoneStatus.complete, _at(started, 14), _at(done, 16)
            ms.status_changed_at = ms.completed_at
            event(ms, EventType.status_change, "not_started", "in_progress", ms.started_at)
            event(ms, EventType.status_change, "in_progress", "complete", ms.completed_at, COMPLETION_NOTES[spec.code])
        elif state == P:
            started = max(ms.planned_start_date, as_of - timedelta(days=rng.randint(2, 12)))
            ms.status, ms.started_at, ms.status_changed_at = MilestoneStatus.in_progress, _at(started, 14), _at(started, 14)
            event(ms, EventType.status_change, "not_started", "in_progress", ms.started_at)
        elif state.startswith("blocked:"):
            reason = state.split(":", 1)[1]
            started = max(ms.planned_start_date, as_of - timedelta(days=rng.randint(20, 30)))
            blocked_at = max(started, as_of - timedelta(days=rng.randint(3, 14)))
            ms.status, ms.blocked_reason = MilestoneStatus.blocked, reason
            ms.started_at, ms.status_changed_at = _at(started, 14), _at(blocked_at, 11)
            event(ms, EventType.status_change, "not_started", "in_progress", ms.started_at)
            event(ms, EventType.status_change, "in_progress", "blocked", ms.status_changed_at, reason)
        elif state == NA:
            when = _at(max(selected, as_of - timedelta(days=rng.randint(10, 25))), 13)
            ms.status, ms.status_changed_at = MilestoneStatus.not_applicable, when
            event(ms, EventType.status_change, "not_started", "not_applicable", when, "Not required at this site")
            completed_on.setdefault(spec.code, selected)
        else:
            raise ValueError(f"unknown state {state!r}")

    session.add_all(events)
    ts.selected_date = selected
    ts.target_activation_date = original_green_due
    ts.activation_status = sc.activation
    ts.scenario_label = sc.label
    ts.source_type = SourceType.synthetic
    if sc.activation == ActivationStatus.activated:
        ts.actual_activation_date = completed_on["GREEN_LIGHT"]
    session.flush()
    return len(events)

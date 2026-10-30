"""The synthetic seed: every scenario must produce the dashboard state it documents."""

from datetime import UTC, datetime

import pytest
from app import models as m
from app.enums import ActivationStatus, MilestoneStatus, SourceType
from app.services import views
from app.services.seeding import SCENARIOS, SEED_TRIALS, TRIAL_PLANS, clear_seed, is_seeded, seed
from app.services.templates import DEFAULT_TEMPLATES, ensure_templates, instantiate_trial_site
from conftest import AS_OF
from sqlalchemy import func, select


def seeded_trial_sites(session):
    return session.scalars(select(m.TrialSite).where(m.TrialSite.scenario_label.is_not(None))).all()


def test_every_scenario_produces_its_documented_health(seeded):
    sites = seeded_trial_sites(seeded)
    bundles = views.load_bundles(seeded, sites, AS_OF)
    for ts in sites:
        expected = SCENARIOS[ts.scenario_label].expected_health
        assert bundles[ts.id].analysis.health == expected, ts.scenario_label


def test_eighteen_sites_across_two_real_trials(seeded):
    sites = seeded_trial_sites(seeded)
    assert len(sites) == sum(len(plan) for plan in TRIAL_PLANS.values()) == 18
    assert {s.trial.nct_id for s in sites} == {nct for nct, _ in SEED_TRIALS}
    assert {s.scenario_label for s in sites} == set(SCENARIOS)


def test_seeded_sites_are_real_named_sites(seeded):
    for ts in seeded_trial_sites(seeded):
        assert not ts.site.is_placeholder_name
        assert ts.site.source_type == SourceType.public_registry  # the site itself stays real


def test_everything_synthetic_is_labeled_synthetic(seeded):
    for model in (m.Milestone, m.MilestoneDependency, m.MilestoneEvent, m.User):
        assert (
            seeded.scalar(select(func.count()).select_from(model).where(model.source_type != SourceType.synthetic)) == 0
        )
    assert all(ts.source_type == SourceType.synthetic for ts in seeded_trial_sites(seeded))
    assert all(u.email.endswith("@example.org") for u in seeded.scalars(select(m.User)))


def test_unseeded_trial_sites_are_untouched(seeded):
    untouched = seeded.scalar(
        select(func.count())
        .select_from(m.TrialSite)
        .where(
            m.TrialSite.scenario_label.is_(None),
            m.TrialSite.activation_status == ActivationStatus.selected,
            m.TrialSite.source_type == SourceType.public_registry,
        )
    )
    assert untouched == 1715 - 18
    assert seeded.scalar(select(func.count(m.Site.id))) == 1662


def test_activated_sites_have_a_real_activation_date_in_the_past(seeded):
    activated = [ts for ts in seeded_trial_sites(seeded) if ts.activation_status == ActivationStatus.activated]
    assert {ts.scenario_label for ts in activated} == {"activated_a", "activated_b"}
    for ts in activated:
        assert ts.actual_activation_date < AS_OF
        green = next(ms for ms in ts.milestones if ms.template.code == "GREEN_LIGHT")
        assert green.status == MilestoneStatus.complete


def test_history_never_reaches_past_today(seeded):
    cutoff = datetime(AS_OF.year, AS_OF.month, AS_OF.day, tzinfo=UTC)
    for ev in seeded.scalars(select(m.MilestoneEvent)):
        assert views.as_utc(ev.occurred_at) < cutoff or ev.occurred_at.date() <= AS_OF


def test_every_completed_milestone_has_a_completion_event(seeded):
    for ms in seeded.scalars(select(m.Milestone).where(m.Milestone.status == MilestoneStatus.complete)):
        kinds = {(e.old_value, e.new_value) for e in ms.events}
        assert ("in_progress", "complete") in kinds


def test_seeding_twice_is_refused_and_reset_restores_the_import(seeded):
    assert is_seeded(seeded)
    with pytest.raises(ValueError, match="already seeded"):
        seed(seeded, AS_OF)
    clear_seed(seeded)
    assert not is_seeded(seeded)
    assert seeded.scalar(select(func.count(m.Milestone.id))) == 0
    assert seeded.scalar(select(func.count(m.User.id))) == 0
    assert (
        seeded.scalar(
            select(func.count()).select_from(m.TrialSite).where(m.TrialSite.source_type == SourceType.synthetic)
        )
        == 0
    )
    seed(seeded, AS_OF)  # and it can be seeded again
    assert is_seeded(seeded)


def test_instantiation_builds_ten_milestones_and_eleven_dependencies(session, world):
    ts = world["trial_sites"][1]
    from datetime import date

    milestones = instantiate_trial_site(session, ts, date(2026, 10, 1))
    assert len(milestones) == len(DEFAULT_TEMPLATES) == 10
    deps = session.scalars(select(m.MilestoneDependency).where(m.MilestoneDependency.trial_site_id == ts.id)).all()
    assert len(deps) == 11  # shipment 2, SIV 8, green light 1
    # Forward pass: shipment starts when IRB (45 days) is due, SIV when the contract (60 days) is.
    assert milestones["IRB_APPROVAL"].due_date == date(2026, 11, 15)
    assert milestones["DRUG_SHIPMENT"].planned_start_date == date(2026, 11, 15)
    assert milestones["SIV"].planned_start_date == milestones["CONTRACT_EXECUTED"].due_date == date(2026, 11, 30)
    assert milestones["GREEN_LIGHT"].due_date == date(2026, 12, 10)


def test_instantiating_twice_is_refused_and_templates_are_idempotent(session, world):
    from datetime import date

    ts = world["trial_sites"][1]
    instantiate_trial_site(session, ts, date(2026, 10, 1))
    with pytest.raises(ValueError, match="already has milestones"):
        instantiate_trial_site(session, ts, date(2026, 10, 1))
    first = ensure_templates(session)
    assert ensure_templates(session).keys() == first.keys()

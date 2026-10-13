from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, StatementError

from app import models as m
from app.enums import ActivationStatus, EventType, MilestoneStatus, SourceType, UserRole, Workstream


def _milestone(trial_site, name="IRB approval", workstream=Workstream.regulatory, **kw):
    return m.Milestone(trial_site=trial_site, name=name, workstream=workstream, **kw)


def _assert_rejected(session, *objs):
    session.add_all(objs)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_full_graph_can_be_created(session, world):
    ts = world["trial_sites"][0]
    irb = _milestone(ts, owner=world["user"])
    contract = _milestone(ts, name="Contract executed", template=world["template"],
                          workstream=Workstream.contracts)
    session.add_all([irb, contract])
    session.flush()
    session.add_all([
        m.MilestoneDependency(trial_site_id=ts.id, predecessor_id=irb.id, successor_id=contract.id),
        m.MilestoneEvent(milestone=contract, changed_by=world["user"],
                         event_type=EventType.status_change,
                         old_value="not_started", new_value="in_progress"),
    ])
    other = m.MilestoneTemplate(code="IRB_APPROVAL", name="IRB approval",
                                workstream=Workstream.regulatory,
                                default_owner_role=UserRole.regulatory,
                                default_duration_days=45, sort_order=10)
    session.add(other)
    session.flush()
    session.add(m.TemplateDependency(predecessor_template_id=other.id,
                                     successor_template_id=world["template"].id))
    session.commit()

    assert session.scalar(select(m.MilestoneDependency).limit(1)).successor.name == "Contract executed"
    assert [e.event_type for e in contract.events] == [EventType.status_change]
    assert world["trial"].trial_sites[0].site.name.startswith("Smilow")
    assert world["trial"].phases == ["PHASE3"]


def test_duplicate_trial_site_rejected(session, world):
    trial, (derby, _) = world["trial"], world["sites"]
    _assert_rejected(session, m.TrialSite(trial=trial, site=derby, source_type=SourceType.synthetic))


def test_duplicate_site_dedup_key_rejected(session, world):
    derby = world["sites"][0]
    _assert_rejected(session, m.Site(dedup_key=derby.dedup_key, name="Smilow Derby (dup)",
                                     source_type=SourceType.public_registry))


def test_milestone_self_dependency_rejected(session, world):
    ts = world["trial_sites"][0]
    irb = _milestone(ts)
    session.add(irb)
    session.flush()
    _assert_rejected(session, m.MilestoneDependency(trial_site_id=ts.id, predecessor_id=irb.id,
                                                    successor_id=irb.id))


def test_template_self_dependency_rejected(session, world):
    tpl = world["template"]
    _assert_rejected(session, m.TemplateDependency(predecessor_template_id=tpl.id,
                                                   successor_template_id=tpl.id))


def test_cross_trial_site_dependency_rejected(session, world):
    ts_a, ts_b = world["trial_sites"]
    a, b = _milestone(ts_a), _milestone(ts_b)
    session.add_all([a, b])
    session.flush()
    _assert_rejected(session, m.MilestoneDependency(trial_site_id=ts_a.id, predecessor_id=a.id,
                                                    successor_id=b.id))


def test_duplicate_dependency_rejected(session, world):
    ts = world["trial_sites"][0]
    a, b = _milestone(ts), _milestone(ts, name="Contract executed")
    session.add_all([a, b])
    session.flush()
    session.add(m.MilestoneDependency(trial_site_id=ts.id, predecessor_id=a.id, successor_id=b.id))
    session.commit()
    _assert_rejected(session, m.MilestoneDependency(trial_site_id=ts.id, predecessor_id=a.id,
                                                    successor_id=b.id))


def test_template_instantiated_once_per_trial_site(session, world):
    ts, tpl = world["trial_sites"][0], world["template"]
    session.add(_milestone(ts, template=tpl))
    session.commit()
    _assert_rejected(session, _milestone(ts, template=tpl))


def test_completed_at_must_match_status(session, world):
    ts = world["trial_sites"][0]
    _assert_rejected(session, _milestone(ts, status=MilestoneStatus.complete))
    _assert_rejected(session, _milestone(ts, status=MilestoneStatus.in_progress,
                                         completed_at=datetime.now(timezone.utc)))


def test_activation_date_requires_activated(session, world):
    ts = world["trial_sites"][1]
    ts.actual_activation_date = date(2026, 10, 1)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    ts.activation_status = ActivationStatus.activated
    ts.actual_activation_date = date(2026, 10, 1)
    session.commit()


def test_registry_trial_requires_nct_id(session):
    _assert_rejected(session, m.Trial(title="No NCT", source_type=SourceType.public_registry))


def test_unchanged_event_rejected(session, world):
    ts = world["trial_sites"][0]
    ms = _milestone(ts)
    session.add(ms)
    session.flush()
    _assert_rejected(session, m.MilestoneEvent(milestone_id=ms.id, event_type=EventType.owner_change,
                                               old_value="7", new_value="7"))


def test_invalid_enum_value_rejected(session, world):
    with pytest.raises(StatementError):
        session.add(_milestone(world["trial_sites"][0], status="done"))
        session.commit()
    session.rollback()
    # Raw SQL bypasses the ORM; the CHECK constraint still rejects it.
    with pytest.raises(IntegrityError):
        session.execute(text("UPDATE trial_sites SET activation_status = 'live'"))
    session.rollback()

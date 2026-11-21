"""Trial types: drug, device, and no-product trials get different milestone checklists (rule D14)."""

from datetime import date

import pytest
from app import models as m
from app.enums import MilestoneStatus, SourceType, TrialType
from app.services.seeding import DEVICE_TRIAL_KEY, SCENARIOS, TRIAL_PLANS, seed
from app.services.templates import CHECKLISTS, checklist_for, ensure_templates, instantiate_trial_site
from app.services.trial_types import classify_trial_type
from conftest import AS_OF
from sqlalchemy import func, select


@pytest.mark.parametrize(
    ("types", "expected"),
    [
        (["DRUG"], TrialType.drug),
        (["BIOLOGICAL", "DRUG", "PROCEDURE", "RADIATION"], TrialType.drug),
        (["DIAGNOSTIC_TEST"], TrialType.drug),  # radiotracers go through the site pharmacy
        (["DEVICE"], TrialType.device),
        (["DEVICE", "BEHAVIORAL"], TrialType.device),
        (["DEVICE", "DRUG"], TrialType.drug),  # drug wins: pharmacy and shipment are the longer path
        (["BEHAVIORAL"], TrialType.no_product),
        (["PROCEDURE", "RADIATION"], TrialType.no_product),
        (["OTHER"], TrialType.no_product),
        ([], TrialType.no_product),
        (None, TrialType.no_product),
        (["drug"], TrialType.drug),
    ],
)
def test_classify_trial_type(types, expected):
    assert classify_trial_type(types) == expected


def codes(trial_type):
    return [spec.code for spec in checklist_for(trial_type)]


def test_each_type_has_its_own_milestones():
    assert len(codes(TrialType.drug)) == 10
    assert "PHARMACY_SETUP" in codes(TrialType.drug) and "DRUG_SHIPMENT" in codes(TrialType.drug)
    device = codes(TrialType.device)
    assert len(device) == 11
    assert {"DEVICE_SAFETY_CHECK", "DEVICE_SHIPMENT", "DEVICE_TRAINING"} <= set(device)
    assert not {"PHARMACY_SETUP", "DRUG_SHIPMENT"} & set(device)
    plain = codes(TrialType.no_product)
    assert len(plain) == 8
    assert not {"PHARMACY_SETUP", "DRUG_SHIPMENT", "DEVICE_SHIPMENT"} & set(plain)


def test_every_checklist_is_a_valid_acyclic_graph_ending_in_green_light():
    for trial_type, checklist in CHECKLISTS.items():
        order = {spec.code: spec.sort_order for spec in checklist}
        assert len(order) == len(checklist), trial_type
        for spec in checklist:
            for pred in spec.predecessors:
                assert pred in order and order[pred] < spec.sort_order, (trial_type, spec.code, pred)
        siv = next(s for s in checklist if s.code == "SIV")
        assert set(siv.predecessors) == {s.code for s in checklist if not s.is_gate}
        assert checklist[-1].code == "GREEN_LIGHT" and checklist[-1].predecessors == ("SIV",)


def test_sort_order_is_unique_across_all_types(session):
    templates = ensure_templates(session)
    assert len(templates) == len({s.code for c in CHECKLISTS.values() for s in c}) == 13
    assert len({t.sort_order for t in templates.values()}) == len(templates)


def test_a_device_trial_site_gets_device_milestones_and_dates(session, world):
    ts = world["trial_sites"][1]
    ts.trial.intervention_types = ["DEVICE"]
    milestones = instantiate_trial_site(session, ts, date(2026, 10, 1))
    assert len(milestones) == 11
    # Shipment waits for IRB (45 days) and the safety check (21 days); training waits for shipment.
    assert milestones["DEVICE_SHIPMENT"].planned_start_date == milestones["IRB_APPROVAL"].due_date == date(2026, 11, 15)
    assert milestones["DEVICE_TRAINING"].planned_start_date == milestones["DEVICE_SHIPMENT"].due_date
    assert milestones["SIV"].planned_start_date == milestones["DEVICE_TRAINING"].due_date == date(2026, 12, 9)
    deps = session.scalars(select(m.MilestoneDependency).where(m.MilestoneDependency.trial_site_id == ts.id)).all()
    assert len(deps) == 2 + 1 + 9 + 1  # shipment 2, training 1, SIV 9, green light 1


def test_a_no_product_trial_site_skips_pharmacy_and_shipment(session, world):
    ts = world["trial_sites"][1]
    ts.trial.intervention_types = ["BEHAVIORAL"]
    milestones = instantiate_trial_site(session, ts, date(2026, 10, 1))
    assert set(milestones) == set(codes(TrialType.no_product))
    assert milestones["SIV"].planned_start_date == milestones["CONTRACT_EXECUTED"].due_date


def test_an_explicit_trial_type_overrides_the_derived_one(session, world):
    ts = world["trial_sites"][1]  # the world trial is a drug trial
    milestones = instantiate_trial_site(session, ts, date(2026, 10, 1), trial_type=TrialType.device)
    assert "DEVICE_SHIPMENT" in milestones and "DRUG_SHIPMENT" not in milestones


def test_the_importer_stores_intervention_types_for_every_registry_trial(seeded):
    registry = seeded.scalars(select(m.Trial).where(m.Trial.source_type == SourceType.public_registry)).all()
    assert len(registry) == 25
    kinds = {t.nct_id: classify_trial_type(t.intervention_types) for t in registry}
    assert kinds["NCT07578116"] == kinds["NCT06312176"] == kinds["NCT06058377"] == TrialType.drug
    assert kinds["NCT05866458"] == TrialType.no_product  # observational
    assert TrialType.device not in kinds.values()  # the registry pull has no device trial


def test_seeded_milestones_match_each_sites_trial_type(seeded):
    seen = set()
    for ts in seeded.scalars(select(m.TrialSite).where(m.TrialSite.scenario_label.is_not(None))):
        trial_type = classify_trial_type(ts.trial.intervention_types)
        assert SCENARIOS[ts.scenario_label].trial_type == trial_type
        assert {ms.template.code for ms in ts.milestones} == set(codes(trial_type))
        seen.add(trial_type)
    assert seen == set(TrialType)


def test_the_device_trial_is_synthetic_with_a_plan_per_site(seeded):
    trial = seeded.scalar(select(m.Trial).where(m.Trial.source_type == SourceType.synthetic))
    assert trial.nct_id is None and "synthetic" in trial.title.lower()
    assert trial.intervention_types == ["DEVICE"]
    count = seeded.scalar(select(func.count()).select_from(m.TrialSite).where(m.TrialSite.trial_id == trial.id))
    assert count == len(TRIAL_PLANS[DEVICE_TRIAL_KEY]) == 6


def test_a_scenario_for_the_wrong_trial_type_is_refused(session):
    from app.services import seeding

    with pytest.raises(ValueError, match="scenario"):
        seeding.TRIAL_PLANS["NCT05866458"] = ("contract_stall",)  # a drug scenario on a no-product trial
        try:
            import json

            from app.services.registry_import import import_registry
            from conftest import RAW  # noqa: F401

            import_registry(session, json.loads(RAW.read_text(encoding="utf-8")))
            seed(session, AS_OF, (("NCT05866458", 1),))
        finally:
            seeding.TRIAL_PLANS["NCT05866458"] = (
                "plain_irb_delay",
                "plain_budget_dispute",
                "plain_on_track",
                "plain_activated",
            )


def test_milestone_statuses_are_unaffected_by_type(seeded):
    device_site = seeded.scalar(select(m.TrialSite).where(m.TrialSite.scenario_label == "device_shipment_late"))
    status = {ms.template.code: ms.status for ms in device_site.milestones}
    assert status["DEVICE_SHIPMENT"] == MilestoneStatus.in_progress
    assert status["DEVICE_TRAINING"] == MilestoneStatus.not_started


def test_api_exposes_trial_type_and_a_checklist_per_type(client):
    trials = client.get("/trials?limit=500").json()["items"]
    by_type = {}
    for t in trials:
        by_type.setdefault(t["trial_type"], []).append(t)
    assert set(by_type) == {"drug", "device", "no_product"}
    assert len(by_type["device"]) == 1 and by_type["device"][0]["source_type"] == "synthetic"

    device_rows = client.get(f"/trials/{by_type['device'][0]['id']}/sites").json()
    row = next(r for r in device_rows["items"] if r["scenario_label"] == "device_shipment_late")
    detail = client.get(f"/trial-sites/{row['id']}").json()
    assert detail["trial"]["trial_type"] == "device"
    assert {ms["template_code"] for ms in detail["milestones"]} == set(codes(TrialType.device))

    assert len(client.get("/templates").json()) == 10  # drug is the default
    device = client.get("/templates?trial_type=device").json()
    assert [t["code"] for t in device][-1] == "GREEN_LIGHT" and len(device) == 11
    shipment = next(t for t in device if t["code"] == "DEVICE_SHIPMENT")
    assert shipment["predecessor_codes"] == ["DEVICE_SAFETY_CHECK", "IRB_APPROVAL"]
    assert len(client.get("/templates?trial_type=no_product").json()) == 8
    assert client.get("/templates?trial_type=bogus").status_code == 422

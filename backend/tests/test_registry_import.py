"""The importer, run against the real 25-trial extract in data/.

Expected counts are the ones documented in docs/data-mapping.md.
"""

import json
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app import models as m
from app.enums import ActivationStatus, SourceType
from app.services.registry_import import (
    import_registry,
    is_placeholder_facility,
    parse_registry_date,
    site_dedup_key,
)

RAW = Path(__file__).resolve().parents[2] / "data" / "raw_25_studies.json"


@pytest.fixture(scope="module")
def studies():
    return json.loads(RAW.read_text(encoding="utf-8"))


@pytest.fixture()
def imported(session, studies):
    result = import_registry(session, studies)
    session.commit()
    return result


def test_counts_match_the_documented_dataset(session, imported):
    assert imported.trials == 25
    assert session.scalar(select(func.count(m.Trial.id))) == 25
    assert session.scalar(select(func.count(m.Site.id))) == 1662
    assert session.scalar(select(func.count(m.TrialSite.id))) == 1715


def test_importing_twice_adds_nothing(session, studies, imported):
    again = import_registry(session, studies)
    session.commit()
    assert (again.sites, again.trial_sites) == (0, 0)
    assert session.scalar(select(func.count(m.TrialSite.id))) == 1715


def test_everything_imported_is_labeled_registry_and_not_activated(session, imported):
    for model in (m.Trial, m.Site, m.TrialSite):
        assert session.scalar(select(func.count()).select_from(model).where(model.source_type != SourceType.public_registry)) == 0
    assert session.scalar(select(func.count()).select_from(m.TrialSite).where(m.TrialSite.activation_status != ActivationStatus.selected)) == 0


def test_placeholder_sites_are_never_merged(session, imported):
    placeholders = session.scalars(select(m.Site).where(m.Site.is_placeholder_name)).all()
    assert len(placeholders) == 715
    assert all(":" in s.dedup_key and s.dedup_key.startswith("NCT") for s in placeholders)


def test_real_site_shared_across_trials_is_one_site(session, imported):
    shared = session.execute(
        select(m.TrialSite.site_id).group_by(m.TrialSite.site_id).having(func.count() > 1)
    ).all()
    assert len(shared) == 53


def test_trial_fields(session, imported):
    trial = session.scalar(select(m.Trial).where(m.Trial.nct_id == "NCT07870148"))
    assert trial.acronym == "MAMTIR"
    assert trial.phases == ["NA"]
    assert trial.overall_status.value == "RECRUITING"
    assert trial.start_date == date(2024, 5, 9)
    observational = session.scalars(select(m.Trial).where(m.Trial.study_type == "OBSERVATIONAL")).all()
    assert len(observational) == 3 and all(t.phases == [] for t in observational)


def test_no_contact_people_are_stored(session, imported):
    assert session.scalar(select(func.count(m.User.id))) == 0


@pytest.mark.parametrize(
    "value, expected",
    [("2027-08", date(2027, 8, 1)), ("2024-05-09", date(2024, 5, 9)), ("2026", date(2026, 1, 1)), (None, None), ("", None), ("garbage", None)],
)
def test_parse_registry_date(value, expected):
    assert parse_registry_date(value) == expected


def test_dedup_key_rules():
    key, placeholder = site_dedup_key("NCT1", 7, {"facility": "  Smilow  Derby ", "city": "Derby", "state": "Connecticut", "country": "United States"})
    assert key == "smilow derby|derby|connecticut|united states" and not placeholder
    assert site_dedup_key("NCT1", 7, {"facility": "Research Site", "city": "Chicago"}) == ("NCT1:7", True)
    assert is_placeholder_facility("research  facility") and is_placeholder_facility(None)

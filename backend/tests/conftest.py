from datetime import date

import pytest
from sqlalchemy.orm import Session

from app import models as m
from app.db import Base, make_engine
from app.enums import ActivationStatus, RecruitmentStatus, SourceType, UserRole, Workstream


@pytest.fixture()
def session():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


@pytest.fixture()
def world(session):
    """One real trial, two real sites, two trial sites, a user, and a template."""
    trial = m.Trial(nct_id="NCT07578116", title="SWOG HER2+ metastatic", phases=["PHASE3"],
                    overall_status=RecruitmentStatus.RECRUITING, start_date=date(2027, 3, 9),
                    source_type=SourceType.public_registry)
    derby = m.Site(dedup_key="smilow derby|derby|connecticut|united states",
                   name="Smilow Cancer Hospital-Derby Care Center", city="Derby",
                   state="Connecticut", country="United States",
                   source_type=SourceType.public_registry)
    fairfield = m.Site(dedup_key="smilow fairfield|fairfield|connecticut|united states",
                       name="Smilow Cancer Hospital Care Center-Fairfield", city="Fairfield",
                       state="Connecticut", country="United States",
                       source_type=SourceType.public_registry)
    ts_a = m.TrialSite(trial=trial, site=derby, ctgov_location_index=2,
                       reported_recruitment_status=RecruitmentStatus.RECRUITING,
                       activation_status=ActivationStatus.in_startup,
                       source_type=SourceType.synthetic, scenario_label="contract_stall")
    ts_b = m.TrialSite(trial=trial, site=fairfield, ctgov_location_index=3,
                       activation_status=ActivationStatus.in_startup,
                       source_type=SourceType.synthetic)
    user = m.User(name="Site contracts office", email="contracts@example.org",
                  role=UserRole.contracts, site=derby, team_name="Site contracts office")
    tpl = m.MilestoneTemplate(code="CONTRACT_EXECUTED", name="Contract executed",
                              workstream=Workstream.contracts, default_owner_role=UserRole.contracts,
                              default_duration_days=60, sort_order=20)
    session.add_all([trial, derby, fairfield, ts_a, ts_b, user, tpl])
    session.commit()
    return {"trial": trial, "sites": (derby, fairfield), "trial_sites": (ts_a, ts_b),
            "user": user, "template": tpl}

import json
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models as m
from app.db import Base, get_session, make_engine
from app.deps import get_today
from app.enums import ActivationStatus, RecruitmentStatus, SourceType, UserRole, Workstream
from app.main import app
from app.services.registry_import import import_registry
from app.services.seeding import seed

RAW = Path(__file__).resolve().parents[2] / "data" / "raw_25_studies.json"
AS_OF = date(2026, 10, 20)  # "today" in every seeded test, so scenarios are deterministic


def _sqlite_engine():
    """In-memory SQLite that can be used from the TestClient's worker thread."""
    return make_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})


@pytest.fixture(scope="session")
def _seeded_template():
    """The real registry data plus the synthetic seed, built once for the whole run."""
    engine = _sqlite_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        import_registry(s, json.loads(RAW.read_text(encoding="utf-8")))
        seed(s, AS_OF)
        s.commit()
    yield engine
    engine.dispose()


@pytest.fixture()
def seeded_engine(_seeded_template):
    """A private copy of the seeded database, so tests may change it freely."""
    engine = _sqlite_engine()
    source = _seeded_template.raw_connection()
    target = engine.raw_connection()
    source.driver_connection.backup(target.driver_connection)
    source.close()
    target.close()
    yield engine
    engine.dispose()


@pytest.fixture()
def seeded(seeded_engine):
    with Session(seeded_engine) as s:
        yield s


@pytest.fixture()
def client(seeded_engine):
    """TestClient wired to the seeded copy, with "today" pinned to AS_OF."""
    from fastapi.testclient import TestClient

    def _session():
        with Session(seeded_engine) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_today] = lambda: AS_OF
    yield TestClient(app)
    app.dependency_overrides.clear()


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

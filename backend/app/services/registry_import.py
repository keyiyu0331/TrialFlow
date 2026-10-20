"""Import real ClinicalTrials.gov API v2 studies into trials, sites, and trial sites.

Follows docs/data-mapping.md. Reads the raw JSON (not the CSVs). Idempotent: running
it twice updates trials and adds nothing new. Location contacts (real people) are
never read.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..enums import ActivationStatus, RecruitmentStatus, SourceType

PLACEHOLDER_FACILITIES = {"research site", "research facility"}


@dataclass(frozen=True)
class ImportResult:
    trials: int
    sites: int
    trial_sites: int


def parse_registry_date(value: str | None) -> date | None:
    """Registry dates may be YYYY-MM-DD, YYYY-MM, or YYYY. Partial dates become the 1st."""
    if not value:
        return None
    parts = value.split("-")
    try:
        year, month, day = int(parts[0]), int(parts[1]) if len(parts) > 1 else 1, int(parts[2]) if len(parts) > 2 else 1
        return date(year, month, day)
    except (ValueError, IndexError):
        return None


def _norm(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def is_placeholder_facility(facility: str | None) -> bool:
    return _norm(facility) in PLACEHOLDER_FACILITIES or not _norm(facility)


def site_dedup_key(nct_id: str, location_index: int, location: dict) -> tuple[str, bool]:
    """Return (dedup_key, is_placeholder_name).

    Registry locations have no stable ID. Real names merge on name|city|state|country.
    Placeholder names ("Research Site") never merge: they are keyed by trial and position.
    """
    facility = location.get("facility")
    if is_placeholder_facility(facility):
        return f"{nct_id}:{location_index}", True
    key = "|".join(_norm(location.get(f)) for f in ("facility", "city", "state", "country"))
    return key, False


def _recruitment_status(value: str | None) -> RecruitmentStatus | None:
    if not value:
        return None
    try:
        return RecruitmentStatus(value)
    except ValueError:
        return RecruitmentStatus.UNKNOWN


def import_registry(session: Session, studies: list[dict], retrieved_at: datetime | None = None) -> ImportResult:
    """Upsert trials, sites, and trial sites from raw API v2 study objects."""
    trials_by_nct = {t.nct_id: t for t in session.scalars(select(m.Trial)) if t.nct_id}
    sites_by_key = {s.dedup_key: s for s in session.scalars(select(m.Site))}
    seen_pairs = {(ts.trial_id, ts.site_id) for ts in session.scalars(select(m.TrialSite))}

    new_sites = new_trial_sites = 0
    for study in studies:
        protocol = study["protocolSection"]
        ident = protocol["identificationModule"]
        status = protocol.get("statusModule", {})
        sponsor = protocol.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {})
        design = protocol.get("designModule", {})
        nct_id = ident["nctId"]

        trial = trials_by_nct.get(nct_id)
        if trial is None:
            trial = m.Trial(nct_id=nct_id, title=ident["briefTitle"], source_type=SourceType.public_registry)
            session.add(trial)
            trials_by_nct[nct_id] = trial
        trial.title = ident["briefTitle"]
        trial.acronym = ident.get("acronym")
        trial.phases = list(design.get("phases", []))
        trial.study_type = design.get("studyType")
        trial.sponsor_name = sponsor.get("name")
        trial.lead_sponsor_class = sponsor.get("class")
        trial.overall_status = _recruitment_status(status.get("overallStatus"))
        trial.start_date = parse_registry_date(status.get("startDateStruct", {}).get("date"))
        trial.primary_completion_date = parse_registry_date(status.get("primaryCompletionDateStruct", {}).get("date"))
        trial.completion_date = parse_registry_date(status.get("completionDateStruct", {}).get("date"))
        trial.last_update_posted_date = parse_registry_date(status.get("lastUpdatePostDateStruct", {}).get("date"))
        trial.last_registry_sync_at = retrieved_at
        session.flush()

        # Contacts are deliberately never read: they are real people.
        for index, loc in enumerate(protocol.get("contactsLocationsModule", {}).get("locations", []), start=1):
            key, placeholder = site_dedup_key(nct_id, index, loc)
            site = sites_by_key.get(key)
            if site is None:
                geo = loc.get("geoPoint") or {}
                site = m.Site(
                    dedup_key=key,
                    name=(loc.get("facility") or "Unnamed facility").strip(),
                    is_placeholder_name=placeholder,
                    city=loc.get("city"),
                    state=loc.get("state"),
                    zip=loc.get("zip"),
                    country=loc.get("country"),
                    latitude=geo.get("lat"),
                    longitude=geo.get("lon"),
                    source_type=SourceType.public_registry,
                )
                session.add(site)
                session.flush()
                sites_by_key[key] = site
                new_sites += 1
            if (trial.id, site.id) in seen_pairs:
                continue
            session.add(
                m.TrialSite(
                    trial_id=trial.id,
                    site_id=site.id,
                    ctgov_location_index=index,
                    reported_recruitment_status=_recruitment_status(loc.get("status")),
                    activation_status=ActivationStatus.selected,
                    source_type=SourceType.public_registry,
                )
            )
            seen_pairs.add((trial.id, site.id))
            new_trial_sites += 1

    session.flush()
    return ImportResult(trials=len(trials_by_nct), sites=new_sites, trial_sites=new_trial_sites)

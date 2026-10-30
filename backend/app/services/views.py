"""Turn database rows into API objects.

Every computed value (overdue, delay level, blocking, top blocker, readiness,
health, projected activation) comes from ``readiness.analyze``; nothing computed
is stored. Routers stay thin and call into this module.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from .. import models as m
from .. import schemas as s
from ..enums import SATISFIED_STATUSES, ActivationStatus, DelayLevel
from . import readiness as rd

DELAY_RANK = {DelayLevel.on_time: 0, DelayLevel.days_1_7: 1, DelayLevel.days_8_30: 2, DelayLevel.over_30: 3}


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; everything stored is UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


@dataclass
class SiteBundle:
    """One trial site with its milestones, dependencies, and computed analysis."""

    trial_site: m.TrialSite
    milestones: list[m.Milestone]  # in checklist order
    deps: list[m.MilestoneDependency]
    analysis: rd.SiteAnalysis

    @property
    def by_id(self) -> dict[int, m.Milestone]:
        return {ms.id: ms for ms in self.milestones}

    @property
    def predecessors(self) -> dict[int, list[int]]:
        out: dict[int, list[int]] = defaultdict(list)
        for dep in self.deps:
            out[dep.successor_id].append(dep.predecessor_id)
        return out


def _order_key(ms: m.Milestone) -> tuple[int, int]:
    return (ms.template.sort_order if ms.template else 1000, ms.id)


def build_bundle(
    ts: m.TrialSite, milestones: list[m.Milestone], deps: list[m.MilestoneDependency], today: date
) -> SiteBundle:
    milestones = sorted(milestones, key=_order_key)
    inputs = [
        rd.MilestoneInput(
            id=ms.id,
            status=ms.status,
            due_date=ms.due_date,
            planned_start_date=ms.planned_start_date,
            completed_date=as_utc(ms.completed_at).date() if ms.completed_at else None,
            code=ms.template.code if ms.template else None,
            sort_order=_order_key(ms)[0],
        )
        for ms in milestones
    ]
    analysis = rd.analyze(inputs, [(d.predecessor_id, d.successor_id) for d in deps], today)
    return SiteBundle(ts, milestones, deps, analysis)


def load_bundles(session: Session, trial_sites: list[m.TrialSite], today: date) -> dict[int, SiteBundle]:
    """Load milestones and dependencies for many trial sites in two queries."""
    ids = [ts.id for ts in trial_sites]
    if not ids:
        return {}
    milestones: dict[int, list[m.Milestone]] = defaultdict(list)
    for ms in session.scalars(
        select(m.Milestone)
        .where(m.Milestone.trial_site_id.in_(ids))
        .options(joinedload(m.Milestone.template), joinedload(m.Milestone.owner))
    ).unique():
        milestones[ms.trial_site_id].append(ms)
    deps: dict[int, list[m.MilestoneDependency]] = defaultdict(list)
    for dep in session.scalars(select(m.MilestoneDependency).where(m.MilestoneDependency.trial_site_id.in_(ids))):
        deps[dep.trial_site_id].append(dep)
    return {ts.id: build_bundle(ts, milestones[ts.id], deps[ts.id], today) for ts in trial_sites}


def owner_ref(user: m.User | None) -> s.OwnerRef | None:
    return s.OwnerRef.model_validate(user) if user else None


def milestone_out(ms: m.Milestone, bundle: SiteBundle, now: datetime) -> s.MilestoneOut:
    state = bundle.analysis.milestones[ms.id]
    changed = as_utc(ms.status_changed_at)
    return s.MilestoneOut(
        id=ms.id,
        template_code=ms.template.code if ms.template else None,
        name=ms.name,
        workstream=ms.workstream,
        status=ms.status,
        owner=owner_ref(ms.owner),
        planned_start_date=ms.planned_start_date,
        due_date=ms.due_date,
        started_at=as_utc(ms.started_at),
        completed_at=as_utc(ms.completed_at),
        status_changed_at=changed,
        blocked_reason=ms.blocked_reason,
        notes=ms.notes,
        predecessor_ids=sorted(bundle.predecessors.get(ms.id, [])),
        is_overdue=state.overdue,
        days_overdue=state.days_overdue,
        delay_level=state.delay_level,
        days_in_status=max(0, (now - changed).days) if changed else 0,
        is_blocking=state.blocking,
        is_ready=state.ready,
        projected_finish=state.projected_finish,
        slip_days=state.slip_days,
        is_impacted=state.impacted,
        source_type=ms.source_type,
    )


def _blocker_summary(bundle: SiteBundle) -> s.BlockerSummary | None:
    top_id = bundle.analysis.top_blocker_id
    if top_id is None:
        return None
    ms = bundle.by_id[top_id]
    state = bundle.analysis.milestones[top_id]
    return s.BlockerSummary(
        milestone_id=ms.id,
        milestone_name=ms.name,
        status=ms.status,
        due_date=ms.due_date,
        days_overdue=state.days_overdue,
        delay_level=state.delay_level,
        owner=owner_ref(ms.owner),
        blocked_reason=ms.blocked_reason,
        downstream_unsatisfied=state.downstream_unsatisfied,
    )


def _summary_kwargs(bundle: SiteBundle, site: m.Site) -> dict:
    ts, analysis = bundle.trial_site, bundle.analysis
    states = analysis.milestones.values()
    total = len(bundle.milestones)
    satisfied = sum(1 for st in states if st.satisfied)
    worst_overdue = max((st.days_overdue for st in states if not st.satisfied), default=0)
    green = next((ms for ms in bundle.milestones if ms.template and ms.template.code == rd.GREEN_LIGHT_CODE), None)
    blocker = _blocker_summary(bundle)
    return dict(
        id=ts.id,
        site=s.SiteOut.model_validate(site),
        reported_recruitment_status=ts.reported_recruitment_status,
        activation_status=ts.activation_status,
        target_activation_date=ts.target_activation_date,
        actual_activation_date=ts.actual_activation_date,
        scenario_label=ts.scenario_label,
        source_type=ts.source_type,
        readiness_pct=round(satisfied / total * 100, 1) if total else 0.0,
        milestones_satisfied=satisfied,
        milestones_total=total,
        is_ready=total > 0 and satisfied == total,
        delay_level=rd.delay_level(worst_overdue),
        top_blocker=blocker,
        next_action_owner=blocker.owner if blocker else None,
        health=analysis.health,
        site_slip_days=analysis.site_slip_days,
        projected_activation_date=analysis.milestones[green.id].projected_finish if green else None,
    )


def trial_site_summary(bundle: SiteBundle, site: m.Site) -> s.TrialSiteSummary:
    return s.TrialSiteSummary(**_summary_kwargs(bundle, site))


def trial_site_detail(bundle: SiteBundle, site: m.Site, trial: m.Trial, now: datetime) -> s.TrialSiteDetail:
    return s.TrialSiteDetail(
        **_summary_kwargs(bundle, site),
        trial=s.TrialRef.model_validate(trial),
        selected_date=bundle.trial_site.selected_date,
        milestones=[milestone_out(ms, bundle, now) for ms in bundle.milestones],
    )


def graph(bundle: SiteBundle) -> s.TrialSiteGraph:
    states = bundle.analysis.milestones
    green = next((ms for ms in bundle.milestones if ms.template and ms.template.code == rd.GREEN_LIGHT_CODE), None)
    blocking = sorted((st for st in states.values() if st.blocking), key=lambda st: (-st.days_overdue, st.id))
    return s.TrialSiteGraph(
        trial_site_id=bundle.trial_site.id,
        green_light_milestone_id=green.id if green else None,
        nodes=[
            s.GraphNode(
                milestone_id=ms.id,
                template_code=ms.template.code if ms.template else None,
                name=ms.name,
                workstream=ms.workstream,
                status=ms.status,
                is_gate=bool(ms.template and ms.template.is_gate),
                owner=owner_ref(ms.owner),
                due_date=ms.due_date,
                is_satisfied=states[ms.id].satisfied,
                is_overdue=states[ms.id].overdue,
                is_blocking=states[ms.id].blocking,
                is_ready=states[ms.id].ready,
                is_impacted=states[ms.id].impacted,
            )
            for ms in bundle.milestones
        ],
        edges=[
            s.GraphEdge(
                id=d.id,
                predecessor_id=d.predecessor_id,
                successor_id=d.successor_id,
                is_satisfied=states[d.predecessor_id].satisfied,
                source_type=d.source_type,
            )
            for d in sorted(bundle.deps, key=lambda d: d.id)
        ],
        blocking_milestone_ids=[st.id for st in blocking],
    )


def event_out(ev: m.MilestoneEvent) -> s.EventOut:
    return s.EventOut(
        id=ev.id,
        milestone_id=ev.milestone_id,
        milestone_name=ev.milestone.name,
        event_type=ev.event_type,
        old_value=ev.old_value,
        new_value=ev.new_value,
        note=ev.note,
        changed_by=owner_ref(ev.changed_by),
        occurred_at=as_utc(ev.occurred_at),
        source_type=ev.source_type,
    )


def activation_counts(session: Session, trial_ids: list[int]) -> dict[int, s.ActivationCounts]:
    counts: dict[int, s.ActivationCounts] = {tid: s.ActivationCounts() for tid in trial_ids}
    if not trial_ids:
        return counts
    rows = session.execute(
        select(m.TrialSite.trial_id, m.TrialSite.activation_status, func.count())
        .where(m.TrialSite.trial_id.in_(trial_ids))
        .group_by(m.TrialSite.trial_id, m.TrialSite.activation_status)
    )
    for trial_id, status, n in rows:
        setattr(counts[trial_id], ActivationStatus(status).value, n)
    return counts


def trial_summary(trial: m.Trial, counts: s.ActivationCounts) -> s.TrialSummary:
    return s.TrialSummary(
        id=trial.id,
        nct_id=trial.nct_id,
        title=trial.title,
        acronym=trial.acronym,
        phases=trial.phases,
        sponsor_name=trial.sponsor_name,
        overall_status=trial.overall_status,
        site_count=sum(counts.model_dump().values()),
        activation_counts=counts,
        source_type=trial.source_type,
    )


def trial_detail(session: Session, trial: m.Trial, counts: s.ActivationCounts, today: date) -> s.TrialDetail:
    """Trial detail. Average readiness is over trial sites that have synthetic milestones."""
    tracked = session.scalars(
        select(m.TrialSite).where(
            m.TrialSite.trial_id == trial.id, m.TrialSite.activation_status != ActivationStatus.selected
        )
    ).all()
    bundles = load_bundles(session, list(tracked), today)
    readiness = [
        sum(1 for ms in b.milestones if ms.status in SATISFIED_STATUSES) / len(b.milestones) * 100
        for b in bundles.values()
        if b.milestones
    ]
    base = trial_summary(trial, counts).model_dump()
    return s.TrialDetail(
        **base,
        study_type=trial.study_type,
        lead_sponsor_class=trial.lead_sponsor_class,
        start_date=trial.start_date,
        primary_completion_date=trial.primary_completion_date,
        completion_date=trial.completion_date,
        last_update_posted_date=trial.last_update_posted_date,
        last_registry_sync_at=as_utc(trial.last_registry_sync_at),
        target_site_count=trial.target_site_count,
        target_fpi_date=trial.target_fpi_date,
        registry_url=f"https://clinicaltrials.gov/study/{trial.nct_id}" if trial.nct_id else None,
        avg_readiness_pct=round(sum(readiness) / len(readiness), 1) if readiness else 0.0,
    )

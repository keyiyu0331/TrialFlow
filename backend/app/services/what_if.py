"""What-if projection (rule D15): when would this trial site go live if some milestones finished on given dates?

Pure over a loaded ``SiteBundle``: no clock, no writes. It re-runs ``readiness.analyze`` with the
assumed finishes and diffs the result against the bundle's real analysis.
"""

from datetime import date

from .. import schemas as s
from ..enums import SATISFIED_STATUSES
from . import readiness as rd
from .views import SiteBundle


class InvalidAssumption(ValueError):
    """An assumption the simulation can't use; the router returns it as 422 invalid_assumption."""


def _fmt(d: date) -> str:
    return f"{d:%b} {d.day}, {d.year}"


def simulate(bundle: SiteBundle, assumptions: list[s.WhatIfAssumption], as_of: date) -> s.WhatIfResult:
    by_id = bundle.by_id
    assumed: dict[int, date] = {}
    for a in assumptions:
        ms = by_id.get(a.milestone_id)
        if ms is None:
            raise InvalidAssumption(f"Milestone {a.milestone_id} is not in trial site {bundle.trial_site.id}")
        if a.milestone_id in assumed:
            raise InvalidAssumption(f"Milestone {a.milestone_id} appears twice")
        if ms.status in SATISFIED_STATUSES:
            raise InvalidAssumption(f"{ms.name} is already {ms.status.value.replace('_', ' ')}")
        if a.finish_date < as_of:
            raise InvalidAssumption(f"{ms.name}: the assumed finish {a.finish_date} is before today ({as_of})")
        assumed[a.milestone_id] = a.finish_date

    base = bundle.analysis
    sim = rd.analyze(bundle.inputs, bundle.edges, as_of, assumed)

    warnings = []
    preds = bundle.predecessors
    for mid, when in assumed.items():
        late = [
            (sim.milestones[p].projected_finish, by_id[p].name)
            for p in preds.get(mid, [])
            if sim.milestones[p].projected_finish is not None and sim.milestones[p].projected_finish > when
        ]
        if late:
            finish, name = max(late)
            warnings.append(f"{by_id[mid].name} waits on {name}, which isn't expected to finish until {_fmt(finish)}.")

    changed = []
    for ms in bundle.milestones:  # checklist order
        b, n = base.milestones[ms.id], sim.milestones[ms.id]
        if b.projected_finish == n.projected_finish and b.slip_days == n.slip_days:
            continue
        changed.append(
            s.WhatIfMilestone(
                milestone_id=ms.id,
                name=ms.name,
                baseline_finish=b.projected_finish,
                projected_finish=n.projected_finish,
                baseline_slip_days=b.slip_days,
                slip_days=n.slip_days,
                impacted=n.impacted,
                assumed=ms.id in assumed,
            )
        )

    green = next((ms for ms in bundle.milestones if ms.template and ms.template.code == rd.GREEN_LIGHT_CODE), None)
    base_go = base.milestones[green.id].projected_finish if green else None
    sim_go = sim.milestones[green.id].projected_finish if green else None
    return s.WhatIfResult(
        trial_site_id=bundle.trial_site.id,
        as_of=as_of,
        baseline_activation_date=base_go,
        projected_activation_date=sim_go,
        delta_days=(sim_go - base_go).days if base_go and sim_go else None,
        baseline_site_slip_days=base.site_slip_days,
        site_slip_days=sim.site_slip_days,
        baseline_health=base.health,
        health=sim.health,
        still_blocked=bool(sim.root_blocker_ids),
        changed=changed,
        warnings=warnings,
    )

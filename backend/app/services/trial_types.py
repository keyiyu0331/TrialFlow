"""Trial type: what a trial ships to its sites, which decides its milestone checklist.

Pure function, no database. The registry has no "drug or device" field, so the type
is derived from the intervention types (docs/domain-rules.md, rule D14).
"""

from collections.abc import Iterable

from ..enums import TrialType

# Registry intervention types that mean an investigational device is shipped.
_DEVICE = {"DEVICE"}
# Types that mean a drug-like product is shipped. Diagnostic tests in the registry data
# are radiotracers, which a site pharmacy handles like a drug. Radiation is treated the
# same way only when it comes with one of these (it ships nothing by itself).
_DRUG = {"DRUG", "BIOLOGICAL", "DIETARY_SUPPLEMENT", "GENETIC", "COMBINATION_PRODUCT", "DIAGNOSTIC_TEST"}

TRIAL_TYPE_LABELS: dict[TrialType, str] = {
    TrialType.drug: "Drug trial",
    TrialType.device: "Device trial",
    TrialType.no_product: "No study product",
}


def classify_trial_type(intervention_types: Iterable[str] | None) -> TrialType:
    """Drug if any drug-like intervention, else device if a device, else no product.

    A trial with both a drug and a device is a drug trial: pharmacy setup and drug
    shipment are the longer, riskier path, so the drug checklist covers it.
    Behavioral, procedure, radiation-only, and observational trials ship nothing.
    """
    types = {t.upper() for t in (intervention_types or [])}
    if types & _DRUG:
        return TrialType.drug
    if types & _DEVICE:
        return TrialType.device
    return TrialType.no_product

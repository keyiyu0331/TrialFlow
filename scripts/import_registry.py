"""Load the real ClinicalTrials.gov extract (data/raw_25_studies.json) into the database.

Usage (from the repo root):
    DATABASE_URL=sqlite:///trialflow.db python scripts/import_registry.py

Creates the tables if they do not exist. Safe to run more than once.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy.orm import Session  # noqa: E402

from app.db import Base, get_engine  # noqa: E402
from app.services.registry_import import import_registry  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw", type=Path, default=ROOT / "data" / "raw_25_studies.json")
    parser.add_argument("--metadata", type=Path, default=ROOT / "data" / "sample_metadata.json")
    args = parser.parse_args()

    studies = json.loads(args.raw.read_text(encoding="utf-8"))
    retrieved_at = None
    if args.metadata.exists():
        retrieved_at = datetime.fromisoformat(json.loads(args.metadata.read_text())["retrieved_at_utc"])

    engine = get_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = import_registry(session, studies, retrieved_at)
        session.commit()
    print(f"Trials: {result.trials}. New sites: {result.sites}. New trial sites: {result.trial_sites}.")


if __name__ == "__main__":
    main()

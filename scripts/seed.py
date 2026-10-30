"""Create the synthetic site activation data on top of the imported registry data.

Usage (from the repo root, after scripts/import_registry.py):
    DATABASE_URL=sqlite:///trialflow.db python scripts/seed.py [--as-of 2026-10-20] [--reset]

Every row written here is labeled source_type = synthetic. Dates are relative to
--as-of (default: today), so scenarios such as "contract stall" stay current.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.db import Base, get_engine  # noqa: E402
from app.services.seeding import clear_seed, is_seeded, seed  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--reset", action="store_true", help="remove existing synthetic data first")
    args = parser.parse_args()

    engine = get_engine()
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        if is_seeded(session):
            if not args.reset:
                sys.exit("Already seeded. Re-run with --reset to rebuild the synthetic data.")
            clear_seed(session)
        result = seed(session, args.as_of)
        session.commit()
    print(
        f"Seeded {result.trial_sites} trial sites, {result.users} users, "
        f"{result.events} history events (as of {args.as_of})."
    )


if __name__ == "__main__":
    main()

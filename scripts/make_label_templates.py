"""Split the pilot into tune/test folds and create one key-fact label template per pilot note.

- Folds are written once to data/derived/pilot_folds.csv and reused afterwards (never re-drawn).
- Existing label files are kept unless --overwrite is passed.

Usage: uv run python scripts/make_label_templates.py [--overwrite]
"""

import argparse

import pandas as pd

from clinsum.labels import PILOT_FOLDS, PILOT_LABELS_DIR, make_pilot_folds, write_templates
from clinsum.paths import DERIVED_DIR

# Notes whose key facts were already discussed with an LLM: their labels are not blind,
# so they may only be used for tuning, never for reported agreement.
FORCE_TUNE = ("10291942-DS-10",)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--overwrite", action="store_true", help="replace existing label files")
    args = parser.parse_args()

    pilot = pd.read_csv(DERIVED_DIR / "pilot_set.csv")
    if PILOT_FOLDS.exists():
        folds = pd.read_csv(PILOT_FOLDS)
    else:
        folds = make_pilot_folds(pilot, force_tune=FORCE_TUNE)
        folds.to_csv(PILOT_FOLDS, index=False)
        print(f"Wrote folds to {PILOT_FOLDS}: {folds['fold'].value_counts().to_dict()}")

    written = write_templates(pilot, folds, overwrite=args.overwrite)
    print(f"Wrote {len(written)} templates to {PILOT_LABELS_DIR} "
          f"({len(pilot) - len(written)} existing files kept).")


if __name__ == "__main__":
    main()

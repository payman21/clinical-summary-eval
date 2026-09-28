"""Draw the fresh post-freeze validation set and create its key-fact label templates.

The fresh set measures how well the frozen spec + extractor generalize to notes that were never
used to write rules (the pilot test half was partly used). It is drawn from the *pilot* patient
partition, excluding the 30 pilot patients, with the same eligibility rules and strata as
make_splits.py and a new seed. Allocation is proportional, so the set resembles the eval
population, which is what the generalization estimate is about.

Never use these notes to change the spec or tune prompts.

Usage: uv run python scripts/make_fresh_set.py [--n 10] [--seed 2026]
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from make_splits import allocate_largest_remainder, apply_eligibility, stratified_sample  # noqa: E402

from clinsum.labels import FRESH_LABELS_DIR, write_templates  # noqa: E402
from clinsum.paths import DERIVED_DIR  # noqa: E402

FRESH_SET = DERIVED_DIR / "fresh_set.csv"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    if FRESH_SET.exists():
        sys.exit(f"{FRESH_SET} already exists; the fresh set is drawn once. Delete it to redraw.")
    rng = np.random.default_rng(args.seed)

    notes = pd.read_parquet(DERIVED_DIR / "note_features.parquet").sort_values("note_id", ignore_index=True)
    split = pd.read_parquet(DERIVED_DIR / "patient_split.parquet")
    notes = notes.merge(split, on="subject_id")
    # Same eligibility filters (and length trim computed on all notes) as the original sampling.
    eligible, _ = apply_eligibility(notes)

    edges = json.loads((DERIVED_DIR / "sampling_log.json").read_text())["length_quartile_edges_chars"]
    eligible["length_q"] = pd.cut(eligible["n_chars"], edges, labels=["Q1", "Q2", "Q3", "Q4"],
                                  include_lowest=True).astype(str)
    eligible["cell"] = eligible["length_q"] + "|" + eligible["service_group"]
    population_share = eligible["cell"].value_counts(normalize=True)

    pilot_subjects = set(pd.read_csv(DERIVED_DIR / "pilot_set.csv")["subject_id"])
    candidates = eligible[(eligible["split"] == "pilot") & ~eligible["subject_id"].isin(pilot_subjects)]
    fresh = stratified_sample(candidates, args.n, weights=population_share, rng=rng,
                              allocator=allocate_largest_remainder)

    cols = ["note_id", "subject_id", "hadm_id", "n_chars", "length_q", "service", "service_group", "cell"]
    fresh[cols].to_csv(FRESH_SET, index=False)
    folds = pd.DataFrame({"note_id": fresh["note_id"], "fold": "fresh"})
    written = write_templates(fresh[cols], folds, out_dir=FRESH_LABELS_DIR)

    assert not set(fresh["subject_id"]) & pilot_subjects
    assert fresh["subject_id"].is_unique
    print(f"Drew {len(fresh)} fresh notes (seed {args.seed}) from {candidates['subject_id'].nunique():,} "
          f"eligible pilot-partition patients -> {FRESH_SET}")
    print("strata:", fresh["cell"].value_counts().sort_index().to_dict())
    print(f"Wrote {len(written)} templates to {FRESH_LABELS_DIR}")


if __name__ == "__main__":
    main()

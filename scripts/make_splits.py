"""Patient-level split + stratified pilot/eval note sampling.

1. Assign every patient (subject_id) to pilot / eval / train once, so no patient ever
   appears in more than one split (eval never leaks into distillation training).
2. Apply eligibility filters to discharge notes; log how many each one removes.
3. Sample notes (at most one per patient, to avoid within-patient correlation).
4. Stratify on note length quartile x service group:
   - pilot: equal allocation across cells (maximise diversity for taxonomy/judge work)
   - eval:  proportional allocation (representative of the eligible population)
5. Write a Table 1 comparing pilot / eval / eligible population, with standardized
   mean differences, so representativeness is shown rather than assumed.

Outputs (all MIMIC-derived, git-ignored) go to data/derived/. Note text is not
copied; join back to discharge notes on note_id when needed.

Usage: uv run python scripts/make_splits.py [--n-pilot 30] [--n-eval 500] [--seed 42]
"""

import argparse
import json

import duckdb
import numpy as np
import pandas as pd

from clinsum.paths import DERIVED_DIR, DISCHARGE_NOTES, MIMIC_HOSP_DIR

SPLIT_FRACTIONS = {"pilot": 0.05, "eval": 0.15, "train": 0.80}

# Discharge service (last curr_service of the admission) -> coarse group.
SERVICE_GROUPS = {
    "medical": {"MED", "CMED", "OMED", "NMED"},
    "surgical": {
        "SURG", "ORTHO", "NSURG", "CSURG", "VSURG", "TRAUM", "TSURG",
        "PSURG", "GU", "GYN", "ENT", "DENT", "EYE",
    },
    # Everything else (OBS, PSYCH, NB, NBB, missing) -> "other".
}

ELECTIVE_TYPES = {"ELECTIVE", "SURGICAL SAME DAY ADMISSION"}

# Notes outside these length percentiles are dropped (truncated stubs / extreme outliers).
LENGTH_TRIM = (0.01, 0.99)


def load_note_features() -> pd.DataFrame:
    """One row per discharge note with header flags and admission covariates (no text)."""
    hosp = MIMIC_HOSP_DIR
    query = f"""
    WITH notes AS (
        SELECT note_id, subject_id, hadm_id,
               length(text) AS n_chars,
               text ILIKE '%Brief Hospital Course:%'                  AS has_bhc,
               text ILIKE '%Discharge Medications:%'                  AS has_dc_meds,
               text ILIKE '%Discharge Diagnosis:%'                    AS has_dc_dx,
               regexp_matches(text, '(?i)Follow-?up Instructions:')   AS has_followup
        FROM read_csv('{DISCHARGE_NOTES}', header = true)
    ),
    svc AS (
        SELECT hadm_id, arg_max(curr_service, transfertime) AS service
        FROM '{hosp / "services.csv.gz"}' GROUP BY hadm_id
    ),
    dx AS (
        SELECT hadm_id, count(*) AS n_diagnoses
        FROM '{hosp / "diagnoses_icd.csv.gz"}' GROUP BY hadm_id
    )
    SELECT n.*, s.service,
           a.admission_type, a.discharge_location,
           date_diff('hour', a.admittime, a.dischtime) / 24.0      AS los_days,
           p.gender,
           p.anchor_age + (year(a.admittime) - p.anchor_year)      AS age,
           coalesce(dx.n_diagnoses, 0)                              AS n_diagnoses
    FROM notes n
    LEFT JOIN svc s USING (hadm_id)
    LEFT JOIN '{hosp / "admissions.csv.gz"}' a USING (hadm_id)
    LEFT JOIN '{hosp / "patients.csv.gz"}' p ON p.subject_id = n.subject_id
    LEFT JOIN dx USING (hadm_id)
    """
    return duckdb.sql(query).df()


def service_group(service) -> str:
    for group, codes in SERVICE_GROUPS.items():
        if service in codes:
            return group
    return "other"


def assign_patient_splits(subject_ids: np.ndarray, rng: np.random.Generator) -> pd.DataFrame:
    ids = rng.permutation(np.unique(subject_ids))
    bounds = np.cumsum([int(round(f * len(ids))) for f in SPLIT_FRACTIONS.values()])
    bounds[-1] = len(ids)
    splits = np.empty(len(ids), dtype=object)
    start = 0
    for name, end in zip(SPLIT_FRACTIONS, bounds):
        splits[start:end] = name
        start = end
    return pd.DataFrame({"subject_id": ids, "split": splits})


def apply_eligibility(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    lo, hi = df["n_chars"].quantile(list(LENGTH_TRIM))
    filters = [
        ("has 'Brief Hospital Course:' header", df["has_bhc"]),
        ("has discharge meds / diagnosis / follow-up headers",
         df["has_dc_meds"] & df["has_dc_dx"] & df["has_followup"]),
        ("patient did not die in hospital", df["discharge_location"] != "DIED"),
        (f"length within {LENGTH_TRIM[0]:.0%}-{LENGTH_TRIM[1]:.0%} percentile "
         f"({lo:.0f}-{hi:.0f} chars)", df["n_chars"].between(lo, hi)),
    ]
    keep = pd.Series(True, index=df.index)
    log = [{"step": "all discharge notes", "remaining": len(df)}]
    for name, mask in filters:
        mask = mask.fillna(False).astype(bool)
        removed = int((keep & ~mask).sum())
        keep &= mask
        log.append({"step": name, "removed": removed, "remaining": int(keep.sum())})
    return df[keep].copy(), log


def allocate(cell_sizes: pd.Series, n: int, weights: pd.Series, rng) -> pd.Series:
    """Largest-remainder allocation of n across cells, capped at available candidates."""
    weights = weights.reindex(cell_sizes.index).fillna(0)
    alloc = pd.Series(0, index=cell_sizes.index)
    remaining = n
    while remaining > 0:
        open_cells = alloc < cell_sizes
        if not open_cells.any():
            raise ValueError("Not enough candidates to allocate the requested sample size.")
        w = weights.where(open_cells, 0)
        if w.sum() == 0:
            w = open_cells.astype(float)
        exact = remaining * w / w.sum()
        add = np.floor(exact).astype(int).clip(upper=cell_sizes - alloc)
        if add.sum() == 0:
            # Hand out single units by largest remainder, random tie-break.
            order = (exact - np.floor(exact) + rng.random(len(exact)) * 1e-9)
            add = pd.Series(0, index=alloc.index)
            for cell in order[open_cells].sort_values(ascending=False).index[:remaining]:
                add[cell] = 1
        alloc += add
        remaining = n - int(alloc.sum())
    return alloc


def stratified_sample(candidates: pd.DataFrame, n: int, weights: pd.Series, rng) -> pd.DataFrame:
    """Sample notes (not patients) per cell, skipping notes whose patient is already used.

    Drawing notes rather than patients keeps the sample representative of the note-level
    population (patients with many admissions contribute proportionally), while the
    skip rule still guarantees at most one note per patient.
    """
    cell_sizes = candidates.groupby("cell")["subject_id"].nunique()
    alloc = allocate(cell_sizes, n, weights, rng)
    shuffled = candidates.sample(frac=1, random_state=rng)
    used_subjects: set = set()
    picked = []
    # Fill the smallest allocations first so rare cells get first claim on shared patients.
    for cell in alloc[alloc > 0].sort_values().index:
        need = int(alloc[cell])
        for row in shuffled[shuffled["cell"] == cell].itertuples():
            if need == 0:
                break
            if row.subject_id not in used_subjects:
                used_subjects.add(row.subject_id)
                picked.append(row.Index)
                need -= 1
        if need:
            raise ValueError(f"Cell {cell} ran out of distinct patients.")
    return candidates.loc[picked].sort_values("note_id").reset_index(drop=True)


def smd(a: pd.Series, b: pd.Series) -> float:
    pooled = np.sqrt((a.var() + b.var()) / 2)
    return float((a.mean() - b.mean()) / pooled) if pooled > 0 else 0.0


def table_one(groups: dict[str, pd.DataFrame], reference: str) -> pd.DataFrame:
    def features(df: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame({
            "note length (chars)": df["n_chars"],
            "age (years)": df["age"],
            "female": (df["gender"] == "F").astype(float),
            "length of stay (days)": df["los_days"],
            "non-elective admission": (~df["admission_type"].isin(ELECTIVE_TYPES)).astype(float),
            "ICD diagnoses (count)": df["n_diagnoses"],
        })
        for g in [*SERVICE_GROUPS, "other"]:
            out[f"service: {g}"] = (df["service_group"] == g).astype(float)
        return out

    feats = {name: features(df) for name, df in groups.items()}
    ref = feats[reference]
    rows = []
    for var in ref.columns:
        binary = set(ref[var].dropna().unique()) <= {0.0, 1.0}
        row = {"variable": var}
        for name, f in feats.items():
            x = f[var].dropna()
            row[name] = (f"{x.mean():.1%}" if binary
                         else f"{x.median():.1f} [{x.quantile(.25):.1f}-{x.quantile(.75):.1f}]")
            if name != reference:
                row[f"SMD {name} vs {reference}"] = round(smd(x, ref[var].dropna()), 3)
        rows.append(row)
    n_row = {"variable": "n notes", **{name: str(len(df)) for name, df in groups.items()}}
    return pd.DataFrame([n_row, *rows])


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n-pilot", type=int, default=30)
    parser.add_argument("--n-eval", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rng = np.random.default_rng(args.seed)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading note features (reads discharge.csv.gz; takes a minute or two)...")
    notes = load_note_features()
    notes["service_group"] = notes["service"].map(service_group)

    patient_split = assign_patient_splits(notes["subject_id"].to_numpy(), rng)
    notes = notes.merge(patient_split, on="subject_id")

    eligible, elig_log = apply_eligibility(notes)
    quartile_edges = eligible["n_chars"].quantile([0, .25, .5, .75, 1]).to_numpy()
    eligible["length_q"] = pd.cut(
        eligible["n_chars"], quartile_edges, labels=["Q1", "Q2", "Q3", "Q4"], include_lowest=True
    ).astype(str)
    eligible["cell"] = eligible["length_q"] + "|" + eligible["service_group"]

    population_share = eligible["cell"].value_counts(normalize=True)
    pilot = stratified_sample(
        eligible[eligible["split"] == "pilot"], args.n_pilot,
        weights=pd.Series(1.0, index=population_share.index), rng=rng,
    )
    eval_set = stratified_sample(
        eligible[eligible["split"] == "eval"], args.n_eval,
        weights=population_share, rng=rng,
    )

    t1 = table_one({"eligible population": eligible, "pilot": pilot, "eval": eval_set},
                   reference="eligible population")

    keep_cols = ["note_id", "subject_id", "hadm_id", "n_chars", "length_q", "service",
                 "service_group", "cell"]
    patient_split.to_parquet(DERIVED_DIR / "patient_split.parquet", index=False)
    notes.drop(columns="split").to_parquet(DERIVED_DIR / "note_features.parquet", index=False)
    pilot[keep_cols].to_csv(DERIVED_DIR / "pilot_set.csv", index=False)
    eval_set[keep_cols].to_csv(DERIVED_DIR / "eval_set.csv", index=False)
    t1.to_csv(DERIVED_DIR / "table1.csv", index=False)
    cell_counts = pd.DataFrame({
        "population_share": population_share,
        "pilot": pilot["cell"].value_counts(),
        "eval": eval_set["cell"].value_counts(),
    }).fillna(0).sort_index()
    cell_counts.to_csv(DERIVED_DIR / "strata_counts.csv")
    (DERIVED_DIR / "sampling_log.json").write_text(json.dumps({
        "seed": args.seed,
        "split_fractions": SPLIT_FRACTIONS,
        "patients_per_split": patient_split["split"].value_counts().to_dict(),
        "eligibility": elig_log,
        "length_quartile_edges_chars": quartile_edges.tolist(),
        "n_pilot": len(pilot),
        "n_eval": len(eval_set),
    }, indent=2))

    pd.set_option("display.width", 200, "display.max_columns", 20)
    print("\nEligibility:")
    for step in elig_log:
        print(f"  {step['step']}: removed {step.get('removed', '-')}, remaining {step['remaining']}")
    print("\nStrata (population share vs. sampled counts):\n", cell_counts)
    print("\nTable 1:\n", t1.to_string(index=False))
    print(f"\nWrote outputs to {DERIVED_DIR}")


if __name__ == "__main__":
    main()

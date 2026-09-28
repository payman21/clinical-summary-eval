"""Hand-labeled key facts (actionable delta): templates, loading, validation.

One YAML file per note in outputs/labels/pilot/<note_id>.yaml (git-ignored; back up separately).
Definitions follow docs/task_spec.md, "Key facts (actionable delta)".
"""

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from clinsum.paths import DERIVED_DIR, OUTPUTS_DIR

PILOT_LABELS_DIR = OUTPUTS_DIR / "labels" / "pilot"
PILOT_FOLDS = DERIVED_DIR / "pilot_folds.csv"

FACT_TYPES = ("principal_diagnosis", "diagnosis", "medication_change", "management_change", "follow_up")
SEVERITIES = ("major", "minor")

TEMPLATE = """\
note_id: {note_id}
# stratum: {length_q} length quartile, {service} ({service_group}), {n_chars} chars | fold: {fold}
labeler:
date:
status: todo   # todo | in_progress | done

# Key facts = actionable delta (see docs/task_spec.md). No cap on the number.
# Exactly one principal_diagnosis (the reason for THIS admission).
# type: principal_diagnosis | diagnosis | medication_change | management_change | follow_up
# severity: major | minor
key_facts: []
#  - id: 1
#    type: principal_diagnosis
#    fact: <one actionable fact, with the context needed to act on it>
#    severity: major
#    evidence: "<short quote from the note>"

# Rules in the spec that made you hesitate on this note.
spec_questions: []

# Optional: your own summary under the spec (only for the ~5 notes used to check the word limit).
reference_summary:
"""


def make_pilot_folds(sample: pd.DataFrame, seed: int = 42, force_tune: tuple[str, ...] = ()) -> pd.DataFrame:
    """Split pilot notes into tune/test halves, alternating within each stratum (seeded).

    Notes in force_tune (e.g. ones already discussed with an LLM) are always put in tune.
    """
    rng = np.random.default_rng(seed)
    df = sample[["note_id", "cell"]].copy()
    df["fold"] = None
    df.loc[df["note_id"].isin(force_tune), "fold"] = "tune"
    # Order remaining notes stratum by stratum (random stratum order, random within stratum) and
    # alternate tune/test continuously across strata: each stratum splits as evenly as possible
    # and the halves differ in size by at most one.
    order = [
        i
        for cell in rng.permutation(df["cell"].unique())
        for i in rng.permutation(df.index[(df["cell"] == cell) & df["fold"].isna()])
    ]
    n_tune = int((df["fold"] == "tune").sum())
    turn = "test" if n_tune > 0 else "tune"
    for i in order:
        df.loc[i, "fold"] = turn
        turn = "test" if turn == "tune" else "tune"
    return df[["note_id", "fold"]]


def write_templates(sample: pd.DataFrame, folds: pd.DataFrame, out_dir: Path = PILOT_LABELS_DIR,
                    overwrite: bool = False) -> list[Path]:
    """Write one template per note. Existing files are kept unless overwrite=True."""
    out_dir.mkdir(parents=True, exist_ok=True)
    merged = sample.merge(folds, on="note_id")
    written = []
    for row in merged.itertuples():
        path = out_dir / f"{row.note_id}.yaml"
        if path.exists() and not overwrite:
            continue
        path.write_text(TEMPLATE.format(**row._asdict()))
        written.append(path)
    return written


def _validate(doc: dict, path: Path) -> list[str]:
    problems = []
    if doc.get("note_id") != path.stem:
        problems.append(f"note_id {doc.get('note_id')!r} does not match file name")
    facts = doc.get("key_facts") or []
    ids = [f.get("id") for f in facts]
    if len(ids) != len(set(ids)):
        problems.append("duplicate key-fact ids")
    for f in facts:
        where = f"fact {f.get('id')}"
        if f.get("type") not in FACT_TYPES:
            problems.append(f"{where}: type {f.get('type')!r} not in {FACT_TYPES}")
        if f.get("severity") not in SEVERITIES:
            problems.append(f"{where}: severity {f.get('severity')!r} not in {SEVERITIES}")
        if not f.get("fact"):
            problems.append(f"{where}: empty fact text")
    n_principal = sum(f.get("type") == "principal_diagnosis" for f in facts)
    if facts and n_principal != 1:
        problems.append(f"expected exactly 1 principal_diagnosis, found {n_principal}")
    return problems


_QUOTABLE_KEYS = ("fact", "evidence", "item")


def fix_quoting(path: Path) -> int:
    """Single-quote scalar values like `"quote" (note)` that YAML rejects. Returns lines changed."""
    changed, out = 0, []
    for line in path.read_text().splitlines():
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        for key in _QUOTABLE_KEYS:
            prefix = f"{key}: "
            if stripped.startswith(prefix):
                val = stripped[len(prefix):]
                quoted_with_trailing_text = (
                    val.startswith('"') and not (val.endswith('"') and val.count('"') == 2)
                )
                unquoted_with_yaml_syntax = (
                    val[:1] not in ('"', "'") and (": " in val or " #" in val)
                )
                if quoted_with_trailing_text or unquoted_with_yaml_syntax:
                    line = f"{indent}{prefix}'" + val.replace("'", "''") + "'"
                    changed += 1
                break
        out.append(line)
    if changed:
        path.write_text("\n".join(out) + "\n")
    return changed


def _flatten_text(value) -> str:
    """Summary text written as plain text, a list, or a heading->text mapping (headings count as words)."""
    if isinstance(value, dict):
        return " ".join(f"{k} {_flatten_text(v)}" for k, v in value.items())
    if isinstance(value, list):
        return " ".join(_flatten_text(v) for v in value)
    return "" if value is None else str(value)


def load_labels(label_dir: Path = PILOT_LABELS_DIR, strict: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load all label files.

    Returns (facts, notes):
      facts: one row per key fact (note_id, fold, id, type, fact, severity, evidence)
      notes: one row per note (fold, status, labeler, n_facts, n_major, n_spec_questions,
             reference_summary_words)
    With strict=True, raises on schema problems; otherwise prints them.
    """
    folds = pd.read_csv(PILOT_FOLDS).set_index("note_id")["fold"] if PILOT_FOLDS.exists() else {}
    fact_rows, note_rows, problems = [], [], []
    for path in sorted(label_dir.glob("*.yaml")):
        try:
            doc = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError as e:
            # Report location only: the message itself may quote note text.
            mark = getattr(e, "problem_mark", None)
            where = f"line {mark.line + 1}" if mark else "unknown line"
            problems.append(f"{path.name}: YAML syntax error at {where}")
            continue
        problems += [f"{path.name}: {p}" for p in _validate(doc, path)]
        nid = doc.get("note_id")
        fold = folds.get(nid) if len(folds) else None
        facts = doc.get("key_facts") or []
        for f in facts:
            fact_rows.append({"note_id": nid, "fold": fold, **f})
        summary = doc.get("reference_summary")
        note_rows.append({
            "note_id": nid,
            "fold": fold,
            "status": doc.get("status"),
            "labeler": doc.get("labeler"),
            "n_facts": len(facts),
            "n_major": sum(f.get("severity") == "major" for f in facts),
            "n_spec_questions": len(doc.get("spec_questions") or []),
            "reference_summary_words": len(_flatten_text(summary).split()) if summary else None,
        })
    if problems:
        msg = "Label problems:\n  " + "\n  ".join(problems)
        if strict:
            raise ValueError(msg)
        print(msg)
    fact_cols = ["note_id", "fold", "id", "type", "fact", "severity", "evidence"]
    return pd.DataFrame(fact_rows).reindex(columns=fact_cols), pd.DataFrame(note_rows)

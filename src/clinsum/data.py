"""Load sampled discharge notes (with text) and split them into sections."""

import re

import duckdb
import pandas as pd

from clinsum.paths import DERIVED_DIR, DISCHARGE_NOTES, DISCHARGE_PARQUET

# Top-level section headers of MIMIC-IV discharge summaries, in their usual order.
# Sub-headers inside sections (e.g. "ADMISSION LABS:", "TRANSITIONAL ISSUES:") are not split on.
SECTION_HEADERS = [
    "Allergies",
    "Chief Complaint",
    "Major Surgical or Invasive Procedure",
    "History of Present Illness",
    "Past Medical History",
    "Social History",
    "Family History",
    "Physical Exam",
    "Pertinent Results",
    "Brief Hospital Course",
    "Medications on Admission",
    "Discharge Medications",
    "Discharge Disposition",
    "Facility",
    "Discharge Diagnosis",
    "Discharge Condition",
    "Discharge Instructions",
    "Followup Instructions",
]

_HEADER_RE = re.compile(
    r"^[ \t]*(" + "|".join(re.escape(h) for h in SECTION_HEADERS).replace("Followup", "Follow-?up")
    + r")[ \t]*:",
    re.IGNORECASE | re.MULTILINE,
)


def _discharge_source() -> str:
    if DISCHARGE_PARQUET.exists():
        return f"'{DISCHARGE_PARQUET}'"
    return f"read_csv('{DISCHARGE_NOTES}', header = true)"


def load_notes(note_ids: list[str]) -> pd.DataFrame:
    """Return note_id, subject_id, hadm_id, charttime, text for the given note_ids."""
    ids = pd.DataFrame({"note_id": list(note_ids)})  # noqa: F841 (referenced by duckdb)
    return duckdb.sql(f"""
        SELECT d.note_id, d.subject_id, d.hadm_id, d.charttime, d.text
        FROM {_discharge_source()} d
        JOIN ids USING (note_id)
        ORDER BY d.note_id
    """).df()


def load_set(name: str) -> pd.DataFrame:
    """Load a sampled set ("pilot" or "eval") from data/derived with note text attached."""
    sample = pd.read_csv(DERIVED_DIR / f"{name}_set.csv")
    notes = load_notes(sample["note_id"].tolist())
    return sample.merge(notes[["note_id", "charttime", "text"]], on="note_id", how="left")


def load_pilot() -> pd.DataFrame:
    return load_set("pilot")


def load_eval() -> pd.DataFrame:
    return load_set("eval")


def split_sections(text: str) -> dict[str, str]:
    """Split a note into {canonical header: body}. Text before the first header goes under "preamble".

    If a header appears more than once, bodies are concatenated.
    """
    canonical = {h.lower(): h for h in SECTION_HEADERS}
    matches = list(_HEADER_RE.finditer(text))
    sections = {"preamble": text[: matches[0].start()].strip() if matches else text.strip()}
    for m, nxt in zip(matches, [*matches[1:], None]):
        key = canonical.get(m.group(1).lower().replace("follow-up", "followup"), m.group(1))
        body = text[m.end() : nxt.start() if nxt else len(text)].strip()
        sections[key] = f"{sections[key]}\n\n{body}" if key in sections else body
    return sections


def section_lengths(df: pd.DataFrame) -> pd.DataFrame:
    """Character length of each section per note (rows = note_id, columns = sections)."""
    rows = {nid: {k: len(v) for k, v in split_sections(t).items()}
            for nid, t in zip(df["note_id"], df["text"])}
    cols = ["preamble", *SECTION_HEADERS]
    return pd.DataFrame.from_dict(rows, orient="index").reindex(columns=cols).fillna(0).astype(int)

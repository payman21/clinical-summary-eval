# clinical-summary-eval

Does a LoRA-distilled open-source model match a closed-API model's discharge-summary faithfulness (primary endpoint: per-note omission rate) at a fraction of the cost?

- [Project plan](clinical-summary-eval-and-distillation-plan.md): stages, current status
- [Task spec v1.0 (frozen)](docs/task_spec.md): summary format, key-fact reference standard, endpoints
- [Methods draft](docs/methods.md): paper-ready methods and limitations
- [Decision log](docs/decision_log.md): dated decisions, rationale, dead ends
- [Reference summary guide](docs/reference_summary_guide.md): how word-limit reference summaries are written

## Layout

```
src/clinsum/   library code (paths, data loading, generation, judge, stats)
scripts/       runnable entry points for each stage
notebooks/     exploration (outputs stripped on commit)
configs/       model / run configs (no secrets)
docs/          task spec, taxonomy, write-up
tests/
data/          MIMIC raw + derived data        -- git-ignored
outputs/       summaries, judge scores, labels -- git-ignored
```

## Data use

MIMIC-IV and MIMIC-IV-Note are credentialed PhysioNet data. Raw files, samples, generated summaries, and hand labels are all derived data and must never be committed or shared. Note text is sent only to AWS Bedrock.

## Setup

```bash
uv sync
uv run nbstripout --install   # strip notebook outputs on commit, so note text never lands in git
```

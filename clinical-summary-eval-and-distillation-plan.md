# Clinical summary evaluation + distillation — project plan

Working title: does a fine-tuned open-source model match a closed-API model's summary faithfulness, at a fraction of the cost?

Data on hand: `data/physionet.org/files/mimic-iv-note/2.2/note/discharge.csv.gz` (discharge summaries), `data/physionet.org/files/mimiciv/3.1/hosp/*` (admissions, diagnoses, labs — useful for spot-checking factual claims against structured data).

**Core plan (Stages 0–4):** define the task, build a lightweight eval harness on hand-labeled MIMIC cases, establish a closed-API baseline, fine-tune/distill an open model, and compare the two on a frozen MIMIC held-out set. This is the original scope. Each stage produces something usable even if you stop there.

**Extensions:** two independent additions below the core plan, neither of which modifies it — Extension A trains a second model on a different corpus and compares it against the core plan's models; Extension B adds a second, parallel evaluation set alongside your own hand-labeled one. Both are optional and can be dropped without touching Stages 0–4.

---

## Stage 0 — Scope the task (before writing any code)

- **Document type:** one discharge summary section, or the full note — decide based on length. A full MIMIC discharge summary can be very long; consider starting with the **"Brief Hospital Course"** section only, since it's the part most analogous to what a real summarization product outputs.
- **Summary spec (write this down, freeze it):**
  - Must retain: final diagnoses, medications at discharge, follow-up instructions, major procedures, abnormal findings that drove decisions.
  - May omit: routine normal labs, administrative boilerplate.
  - How to represent uncertainty/negation ("no evidence of X") and chronology (order of events) — decide explicitly, this is where models fail most.
- **Primary endpoint — omission, not hallucination.** Freeze this before any comparison. The primary metric is the **per-note omission rate**: the proportion of must-retain findings (per the spec above) that the summary fails to include. Hallucination (unsupported additions) is a **secondary** endpoint.
  - *Why this ordering:* Park, Chen & Dettmers, "Synthetic Hospital" (arXiv:2609.30027, Sept 2026), Appendix Table A, evaluated 10 frontier and open models on clinical summarization and found hallucination rates of **0.001–0.009 across every model and prompting strategy**, while omission ran **0.45–0.62** for whole-patient summaries (0.47–0.79 on the harder specialty-conditioned variant). Their conclusion: "modern frontier models rarely fabricate unsupported clinical findings. Instead, the dominant failure mode is omission."
  - *Consequence:* an endpoint built around unsupported additions risks a floor effect with almost nothing left to measure. Omission is where the signal is.
  - *Caveat worth testing:* that prior comes from education-derived synthetic records, not messy real notes. Whether near-zero hallucination replicates on MIMIC discharge summaries is itself a reportable secondary result.

**Output of this stage:** a one-paragraph task spec you can paste at the top of every later document.

---

## Stage 1 — Lightweight eval harness (pilot scale)

Goal: enough infrastructure to measure quality, not the full production version.

1. **Sample ~30 discharge summaries** from `discharge.csv.gz`, stratified a little (e.g., mix of short/long, medical/surgical if `admissions.csv.gz` diagnosis codes are easy to join in).
2. **Generate one summary per note** with a single baseline prompt (see Stage 2).
3. **Build the error taxonomy** from what you actually see in these 30, not from theory. Likely categories: material omission, unsupported addition, negation error, temporal error, wrong attribution. Define severity (major/minor) with 2–3 concrete examples per category, pulled from your own pilot outputs. Expect omission to dominate (see the Stage 0 endpoint note) and budget labeling effort accordingly: enumerate the must-retain findings for each note up front, so omission is scored against an explicit list rather than judged holistically.
4. **Hand-label the 30 pilot cases yourself** against the source note using the taxonomy.
5. **Draft an LLM-judge prompt** that takes (source note, generated summary) and returns taxonomy-coded errors + severity.
6. **Validate the judge** against your 30 hand labels: report false negatives on major errors (the dangerous failure mode), false positives, and agreement by category.
7. If judge agreement is weak, iterate the judge prompt (few-shot examples from your labeled cases usually helps most) before scaling up.

**Output of this stage:** a taxonomy, ~30 labeled cases, and a judge you've measured (not assumed) to be reasonably reliable.

**Stopping point if short on time:** this stage alone is already a defensible portfolio artifact — "I built and validated an LLM-as-judge for clinical summary faithfulness" — even without Stages 2–4.

---

## Stage 2 — Baseline: closed-API summarizer

1. Call Claude or GPT API with the frozen prompt from Stage 0 on a larger sample (e.g., 100–150 notes).
2. Score all outputs with the Stage 1 judge.
3. Report: per-note omission rate (primary), hallucination rate (secondary), latency, and cost per summary. This is your reference point — call it **System A**.

**Output of this stage:** a numeric baseline (error rate + cost/latency) that Stage 4 has to beat or match.

---

## Stage 3 — Fine-tune / distill an open-source model

1. **Pick a small open model** you can run locally or on modest cloud GPU — e.g., a 7–8B instruction-tuned model (Llama, Qwen, Mistral class). Use LoRA/QLoRA, not full fine-tuning.
2. **Build training data via distillation**: take a separate set of MIMIC notes (disjoint from your eval set — no overlap, this matters), generate target summaries with the closed API (System A's prompt), and use those (note, summary) pairs as supervised fine-tuning targets for the open model. This sidesteps needing hand-written gold summaries at scale.
3. Fine-tune the open model on this distilled data.
4. Run the fine-tuned model on the **same held-out eval set** used in Stage 2 (never seen during training) — call it **System B**.
5. Score System B with the same judge from Stage 1.

**Supporting evidence for this stage's premise.** Lehman et al. ("Do We Still Need Clinical Language Models?", 2023) found that small clinical-pretrained models (220M–345M params) match or outperform GPT-3 (175B) and Flan-T5-XXL (11B) used via in-context learning, on three clinical NLP tasks (MedNLI, RadQA, CLIP) — fine-tuned specialized models beat ICL with a much larger general model even in low-data settings. Their finding that pretraining-domain match matters more than raw parameter count or total FLOPs is direct precedent for this stage's hypothesis, that a smaller model trained on clinical text can match a larger general-purpose API model's quality. They also give a compute breakeven formula (their Eq. 7) for when pretraining/fine-tuning a small specialized model pays off versus running inference on a larger general model — useful if Stage 4 wants a quantitative framing of the cost tradeoff, not just an empirical one.

**Precedent for the judge/verifier pattern.** Chaturvedi et al. ("Early Risk Prediction with Temporally and Contextually Grounded Clinical Language Processing", 2026) introduce REVEAL, a framework structurally close to Stage 1 + Stage 3 combined: a large reasoner LLM generates predictions with explanations, and a much smaller fine-tuned verifier LLM (1B params, LoRA) scores the credibility of each reasoning path against human-labeled correctness — the same "small model validates/distills a larger model's output" structure as this project's judge-validation and distillation steps, applied to a different clinical task (T2D risk prediction rather than summarization). Worth citing as precedent, and worth reading their verifier fine-tuning setup (LoRA rank 8, alpha 16, dropout 0.1) as a starting hyperparameter reference for Stage 3's LoRA fine-tune.

**Output of this stage:** a fine-tuned model and its judge-scored outputs on the frozen eval set.

---

## Stage 4 — Compare and decide

1. **Paired comparison**: System A and System B scored on the identical set of notes. Compute the per-note difference in omission rate (the primary endpoint frozen in Stage 0).
2. **Statistical test**: because the primary endpoint is a continuous per-note rate rather than a binary flag, use a **paired bootstrap confidence interval** on the mean difference, or a Wilcoxon signed-rank test. Reserve McNemar's for the secondary binary endpoints ("≥1 major omission", "≥1 unsupported addition"). Do not dichotomize the primary endpoint — it discards power for no benefit. If a note contributes to more than one grouped unit (shouldn't happen here since one summary per note, but check), account for that grouping.
3. **Report together**: quality difference (with CI) + cost/latency difference. The actual finding you're chasing: *"System B matches System A's faithfulness within [X]% at [Y]x lower cost/latency"* — or the honest negative result if it doesn't.
4. If System B loses badly, that's still a valid, reportable result — investigate on your distillation training data (not the frozen eval set) rather than re-tuning against the eval set itself.

**Output of this stage:** a written comparison with a number and a confidence interval, not a qualitative impression.

---

## Extensions (optional, additive — do not modify Stages 0–4)

---

### Extension A — does a synthetic training substrate generalize to real notes as well as MIMIC does?

**The question.** Does fine-tuning on *real but narrow* clinical text (MIMIC discharge summaries) or on *synthetic but carefully curated, ontology-grounded* records produce a model that generalizes better to real-world discharge summaries? Both arms are evaluated on the same real MIMIC held-out set, so real-world performance is the fixed yardstick and only the training substrate varies.

**The synthetic corpus.** Synthetic Hospital (Park, Chen & Dettmers, arXiv:2609.30027; code at `github.com/sparkcpark/synthetic_hospital`): 1,268 fully synthetic longitudinal patients across 5,602 encounters, built entirely from public medical-education material with no PHI. Every diagnosis, finding, and temporal relation is grounded in ICD-10-CM / SNOMED CT / LOINC with provenance back to its source. Openly redistributable with no DUA or credentialing. The training split alone provides 800 patients / 7,619 instances with full ground truth. In blinded review, physicians distinguished its records from real charts at 53% (chance).

**Design.** Hold everything constant except the training corpus:

| | Arm B (from Stage 3) | Arm C (new) | Arm D (optional) |
|---|---|---|---|
| Training corpus | MIMIC notes | Synthetic Hospital | both, combined |
| Base model + LoRA config | identical | identical | identical |
| Teacher model + target prompt | identical | identical | identical |
| Training set size | matched | matched | ~2× (note the confound) |
| Evaluation set | frozen MIMIC held-out | same | same |
| Judge + primary endpoint | same | same | same |

**Two confounds to control, or the result is uninterpretable.**

1. **Task format.** Synthetic Hospital's native summarization task is whole-patient longitudinal synthesis across encounters; your MIMIC arm is single-note summarization. Training Arm C on the longitudinal task and testing on single notes confounds *synthetic vs. real* with *longitudinal vs. single-note*. Render Synthetic Hospital records into the same single-note task format before training. The paper's Appendix G demonstrates the reverse normalization (real MIMIC notes into the Synthetic Hospital schema, preserving clinical content), which is evidence the harmonization is tractable in either direction.
2. **Target quality.** Do **not** train Arm C on Synthetic Hospital's graph-derived key-finding lists while training Arm B on teacher-generated summaries — that confounds target quality with data source. Use the same teacher and the same prompt to generate training targets for both arms. The graph labels are then free *evaluation* signal, not training targets.

**Why it lands.** The Synthetic Hospital paper frames open redistributability as its contribution but does not test whether a model trained on it transfers to real records — that transfer question is the unoccupied part. It also has a direct deployment consequence: if synthetic open data trains a model that matches one trained on real data, that is a route around the DUA bottleneck gating most clinical NLP work. And it is the same generalization question as the fMRI foundation-model transfer work, asked in a second domain.

**Done when.** Two (or three) arms scored on the identical frozen MIMIC eval set, with paired confidence intervals on the primary omission endpoint, and a statement of which training substrate transfers better and by how much — including the honest negative result if they are indistinguishable.

---

### Extension B — Synthetic Hospital as a second, parallel evaluation set

**The idea.** Run the public split of Synthetic Hospital (200 patients / 1,859 instances) alongside your own 30 hand-labeled MIMIC cases from Stage 1 — as a second, larger judge-validation set, **in parallel with** the one you build yourself, not instead of it. This is purely an evaluation-side addition; it does not touch Stages 0–4's training or the frozen MIMIC comparison in Stage 4.

**Why it's useful.** Synthetic Hospital's summarization task ships with a deterministic, graph-derived list of must-include key findings per patient (mean 18.8), scored by an abbreviation- and negation-aware matcher — which is exactly the quantity your primary endpoint (omission rate) measures. That gives you hundreds of omission-labeled instances to check judge agreement against, instead of 30.

**How the two eval sets divide the work — do not let one substitute for the other:**
- **Your 30 hand-labeled MIMIC cases** stay the anchor for what Synthetic Hospital's graph *cannot* score: negation errors, temporal errors, wrong-encounter attribution, and clinical judgment about whether an omission would actually matter to a treating clinician. This is where your MD is the differentiator.
- **Synthetic Hospital's public split** is a large-scale, free check on omission-detection specifically — nothing else.

**Two caveats to report, not paper over:**
1. **Judge validity may not transfer across registers.** A judge validated on Synthetic Hospital's clean, education-derived prose is not automatically valid on MIMIC's telegraphic, abbreviation-heavy discharge notes — the paper itself notes physicians could still tell the two registers apart in its format-normalized realism study. Validate on Synthetic Hospital, then re-check agreement on your small MIMIC hand-labeled set; a drop is a finding, not a failure to hide.
2. **The construct isn't identical.** Synthetic Hospital's "key findings" are derived from board-question vignettes built to be diagnostically clean; what matters for real clinical continuity of care isn't guaranteed to be the same list. Report agreement, don't assume equivalence.

**Keep MIMIC as the headline.** Do not let Synthetic Hospital become the primary evaluation set — the paper already benchmarked ten frontier models on it two days before you read it, so "I ran the same benchmark" carries no signal on its own. Its value here is entirely as a validation aid for the judge you built for MIMIC.

**Done when.** Judge agreement (false-negative/false-positive rate on omission) reported on both eval sets side by side, with an explicit statement of whether they agree.

**Lowest priority, optional third source — ProbSum.** The BioNLP 2023 ProbSum shared task (Gao et al.) offers a third possible judge-validation source: 768 train / 237 test MIMIC-III daily progress notes with human-annotated active-problem lists (ground truth extracted from each note's own Plan section), released via PhysioNet — real data, same DUA family as the rest of this project. If pursued, use it narrowly: prompt for "the active problem list" (matching ProbSum's actual task, not a discharge-style summary), score only the diagnosis-omission slice against their annotations, and report it as a third, separate generalization check — never pooled with the discharge-summary or Synthetic Hospital numbers. Real caveats that keep this bottom-of-list: different note type (SOAP progress notes, not discharge summaries), different MIMIC version (III vs. your IV data), and it only covers diagnoses — no meds, follow-up, negation, or temporal errors. Skip unless Extension B's other two sources leave time and the judge-generalization question still feels open.

---

## What "done" looks like

**Core plan:**
- A frozen task spec and taxonomy.
- A judge, validated against your own hand labels, with reported false-negative/false-positive rates.
- Two systems (closed-API baseline, fine-tuned open model) scored on the same frozen MIMIC held-out set.
- A statistically grounded comparison (paired test, CI) covering both quality and cost/latency.
- A short write-up: question, data, method, result, limitations — the same structure as the BrainLM paper.

**If extensions are completed (either is independently optional):**
- Extension A: a second comparison, on the same frozen MIMIC eval set, of models fine-tuned on real versus synthetic training substrates.
- Extension B: judge agreement reported on both the hand-labeled MIMIC set and the Synthetic Hospital public split, side by side.

## Open questions to resolve early

**Core plan:**
- Compute budget and access for LoRA fine-tuning (local GPU vs. cloud — decide before Stage 3).
- Whether "Brief Hospital Course" alone or the full discharge summary is the right scope — a quick look at 5–10 real notes will settle this.
- How large the final eval set needs to be to detect a meaningful effect size with reasonable confidence — worth a quick power calculation once Stage 1's pilot gives you a rough sense of baseline omission rate and variance.

**Extensions:**
- Extension A: how much work it actually is to render Synthetic Hospital records into your single-note task format — inspect a few released patients before committing.
- Extension A: whether to run the combined-corpus Arm D at all, given it doubles training size and therefore confounds substrate with data volume unless you subsample to match.
- Extension B: whether to run it before or after Stage 1 — running it first could inform your taxonomy design, but delays Stage 1's own completion.

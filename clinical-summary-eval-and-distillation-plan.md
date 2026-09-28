# Clinical summary evaluation + distillation — project plan

Working title: does a fine-tuned open-source model match a closed-API model's summary faithfulness, at a fraction of the cost?

Data on hand: `data/physionet.org/files/mimic-iv-note/2.2/note/discharge.csv.gz` (discharge summaries), `data/physionet.org/files/mimiciv/3.1/hosp/*` (admissions, diagnoses, labs — useful for spot-checking factual claims against structured data).

**Core plan (Stages 0–4):** define the task, build a lightweight eval harness on hand-labeled MIMIC cases, establish a closed-API baseline, fine-tune/distill an open model, and compare the two on a frozen MIMIC held-out set. This is the original scope. Each stage produces something usable even if you stop there.

**Extensions:** two independent additions below the core plan, neither of which modifies it — Extension A trains a second model on a different corpus and compares it against the core plan's models; Extension B adds a second, parallel evaluation set alongside your own hand-labeled one. Both are optional and can be dropped without touching Stages 0–4.

## Status (2026-09-28)

| Stage | Status |
|---|---|
| 0 — Task spec | **Done.** [docs/task_spec.md](docs/task_spec.md) frozen at v1.0. |
| 1 — Eval harness | **In progress.** Pilot (30 notes) sampled and labeled by the clinician. Next: fresh validation set, Bedrock setup, key-fact extractor and presence judge. |
| 2 — System A | Eval set (500 notes) sampled and frozen; not yet run. |
| 3 — System B | Not started. |
| 4 — Comparison | Not started. |

Details of every decision are in [docs/decision_log.md](docs/decision_log.md); the paper-ready version is [docs/methods.md](docs/methods.md).

**Key changes from the original plan:**
- **Scope:** full discharge summary, not the Brief Hospital Course only.
- **Reference standard:** exhaustive must-retain lists were replaced by clinician-defined **"actionable delta" key facts**, following MedFactEval (Grolleau et al., 2025).
- **Key facts on the eval set:** extracted by a validated LLM extractor, not hand-labeled.
- **Eval set:** 500 notes rather than 100–150, with the final analysis n set by a power calculation.

---

## Stage 0 — Scope the task ✅ (frozen v1.0)

Settled, see [docs/task_spec.md](docs/task_spec.md):
- **Reader:** the patient's primary care physician (PCP) after discharge. The summary conveys what is **new or changed and actionable** because of this admission.
- **Input:** the full discharge summary.
- **Output:** fixed headings (Diagnoses / Hospital course / Med changes / Pending), ≤250 words, with the complete medication delta. The limit was validated on the 5 densest pilot notes (all ≤216 words).
- **Reference standard, "key facts":**
  - always the principal diagnosis (reason for *this* admission, with its suspected cause);
  - every medication change, determined mechanically from the admission vs. discharge lists;
  - every other candidate that passes a four-question test: new or changed? matters after discharge? for a clinician? distinct?
  - fixed defaults when the note is silent;
  - no cap on the number of facts.
- **Severity:** major/minor. Medications are graded mechanically: major if and only if on the ISMP 2021 community/ambulatory high-alert list, plus oral antiplatelets and class I/III antiarrhythmics.
- **Primary endpoint — omission, not hallucination.** The primary metric is the **per-note key-fact omission rate**: omitted key facts ÷ key facts in the note, averaged across notes. Secondary endpoints:
  - hallucination (unsupported statements), with a strict definition that counts unstated inferences
  - omission rate by fact type
  - ≥1 major omission
  - contradiction of a key fact
  - *Why this ordering:* Park, Chen & Dettmers, "Synthetic Hospital" (arXiv:2609.30027, Sept 2026), Appendix Table A, evaluated 10 frontier and open models on clinical summarization and found hallucination rates of **0.001–0.009 across every model and prompting strategy**, while omission ran **0.45–0.62** for whole-patient summaries (0.47–0.79 on the harder specialty-conditioned variant). Their conclusion: "modern frontier models rarely fabricate unsupported clinical findings. Instead, the dominant failure mode is omission."
  - *Consequence:* an endpoint built around unsupported additions risks a floor effect with almost nothing left to measure. Omission is where the signal is.
  - *Caveat worth testing:* that prior comes from education-derived synthetic records, not messy real notes. Whether near-zero hallucination replicates on MIMIC discharge summaries is itself a reportable secondary result.

**Lessons from Stage 0** (recorded in the decision log):
- **An exhaustive must-retain list was too subjective and too slow for one rater.** The first pilot note produced 28 items and 5 open questions. Actionable-delta key facts fixed this.
- **Consistency matters more than per-note accuracy.** Both systems are scored against the same reference, so systematic error largely cancels while inconsistency adds variance. The spec is therefore written as general tests and mechanical procedures, not lists of examples.
- **MIMIC-specific findings:**
  - Follow-up Instructions are fully redacted.
  - 12% of notes lose the Brief Hospital Course header to de-identification.
  - Notes map one-to-one to admissions.

---

## Stage 1 — Eval harness (pilot scale)

Goal: enough infrastructure to measure quality, not the full production version.

1. ✅ **Sample pilot and eval sets:**
   - patient-level split (pilot / eval / train);
   - 30 pilot notes, equal allocation across 12 length × service strata;
   - 500 eval notes, proportional allocation; representativeness checked with SMDs.
2. ✅ **Clinician labels key facts on the 30 pilot notes**, blind to LLM suggestions. Result: 280 facts, median 8.5 per note (range 1–19), 56% medication changes. The pilot is split into **tune** and **test** halves of 15 each.
3. ✅ **Freeze the spec** after checking the four-question test against 10 tune notes (the spec agreed with 92% of calls after label fixes) and validating the word limit.
4. ◐ **Fresh validation set:** 10 notes drawn (pilot partition, excluding pilot patients, proportional allocation, seed 2026). They await clinician labeling under the frozen spec and are never used to write rules. Because the spec's rules were shaped partly by test-half notes, this is the primary generalization check.
5. **Bedrock setup:** Claude for System A, plus at least one non-Claude model family for extraction and judging (to avoid favoring the teacher's model family).
6. **Key-fact extractor:**
   - LLM transcription of the medication lists, then comparison in code;
   - LLM extraction of the other key facts via the four-question test, with `uncertain` flags when a silence default is applied.

   Tune it on the tune half. Report recall and precision against the clinician's facts on the test half and the fresh set, plus stability across runs.
7. **Generate System A summaries** for the pilot notes.
8. **Clinician presence labels:** for each summary, mark each key fact present or absent. That's ~300 yes/no judgments: all test notes plus ~5 tune notes.
9. **Presence judge**, a mixed-family LLM jury in the style of MedFactEval: tune on the tune half, then report Cohen's κ against the clinician on the test half with bootstrap CIs. Include the contradiction check and the hallucination judge.

**Output of this stage:** a frozen spec, 30 (+10 fresh) clinician-labeled notes, and an extractor and judge whose agreement with the clinician is measured, not assumed.

**Stopping point if short on time:** this stage alone is already a defensible portfolio artifact — "I built and validated an LLM-as-judge for clinical summary faithfulness" — even without Stages 2–4.

---

## Stage 2 — Baseline: closed-API summarizer

1. **Extract key facts once** for all eval notes with the frozen Stage 1 extractor, and store them. Every system is scored against these identical facts.
2. **Fix the analysis size:** run the power calculation using σ_d from the pilot, before any System A vs. B results exist. If fewer than 500 notes suffice, use a stratified subsample.
3. **Summarize the eval notes** with Claude via AWS Bedrock (the only route MIMIC text may leave the machine), using the frozen prompt. The format example comes from a tune note.
4. Score all outputs with the Stage 1 judge.
5. Report: per-note key-fact omission rate (primary), secondary endpoints, latency, and cost per summary. This is your reference point — call it **System A**.

**Output of this stage:** a numeric baseline (error rate + cost/latency) that Stage 4 has to beat or match.

---

## Stage 3 — Fine-tune / distill an open-source model

1. **Pick a small open model** you can run locally or on modest cloud GPU — e.g., a 7–8B instruction-tuned model (Llama, Qwen, Mistral class). Use LoRA/QLoRA, not full fine-tuning.
2. **Build training data via distillation**: take notes from the **train** patient partition (disjoint by patient from pilot and eval, so no evaluation patient is ever seen in training, even through another admission). Generate target summaries with System A's prompt via Bedrock, and use the (note, summary) pairs as supervised fine-tuning targets. This avoids needing hand-written gold summaries at scale. *Before starting:* check the Bedrock model's terms on using outputs to train other models. Also, the longest eligible notes are ~6–7k tokens, so the student needs ≥8k context.
3. Fine-tune the open model on this distilled data.
4. Run the fine-tuned model on the **same held-out eval set** used in Stage 2 (never seen during training) — call it **System B**.
5. Score System B with the same judge from Stage 1.

**Supporting evidence for this stage's premise.** Lehman et al. ("Do We Still Need Clinical Language Models?", 2023) found that small clinical-pretrained models (220M–345M params) match or outperform GPT-3 (175B) and Flan-T5-XXL (11B) used via in-context learning, on three clinical NLP tasks (MedNLI, RadQA, CLIP) — fine-tuned specialized models beat ICL with a much larger general model even in low-data settings. Their finding that pretraining-domain match matters more than raw parameter count or total FLOPs is direct precedent for this stage's hypothesis, that a smaller model trained on clinical text can match a larger general-purpose API model's quality. They also give a compute breakeven formula (their Eq. 7) for when pretraining/fine-tuning a small specialized model pays off versus running inference on a larger general model — useful if Stage 4 wants a quantitative framing of the cost tradeoff, not just an empirical one.

**Precedent for the judge/verifier pattern.** Chaturvedi et al. ("Early Risk Prediction with Temporally and Contextually Grounded Clinical Language Processing", 2026) introduce REVEAL, a framework structurally close to Stage 1 + Stage 3 combined: a large reasoner LLM generates predictions with explanations, and a much smaller fine-tuned verifier LLM (1B params, LoRA) scores the credibility of each reasoning path against human-labeled correctness — the same "small model validates/distills a larger model's output" structure as this project's judge-validation and distillation steps, applied to a different clinical task (T2D risk prediction rather than summarization). Worth citing as precedent, and worth reading their verifier fine-tuning setup (LoRA rank 8, alpha 16, dropout 0.1) as a starting hyperparameter reference for Stage 3's LoRA fine-tune.

**Output of this stage:** a fine-tuned model and its judge-scored outputs on the frozen eval set.

---

## Stage 4 — Compare and decide

1. **Paired comparison**: System A and System B scored on the identical set of notes, against the identical stored key facts. Compute the per-note difference in key-fact omission rate (the primary endpoint frozen in Stage 0). Also report the difference by fact type.
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

**Keep MIMIC as the headline.** Do not let Synthetic Hospital become the primary evaluation set — the paper already benchmarked ten frontier models on it, so "I ran the same benchmark" carries no signal on its own. Its value here is entirely as a validation aid for the judge you built for MIMIC.

**Done when.** Judge agreement (false-negative/false-positive rate on omission) reported on both eval sets side by side, with an explicit statement of whether they agree.

**Lowest priority, optional third source — ProbSum.** The BioNLP 2023 ProbSum shared task (Gao et al.) offers a third possible judge-validation source: 768 train / 237 test MIMIC-III daily progress notes with human-annotated active-problem lists (ground truth extracted from each note's own Plan section), released via PhysioNet — real data, same DUA family as the rest of this project. If pursued, use it narrowly: prompt for "the active problem list" (matching ProbSum's actual task, not a discharge-style summary), score only the diagnosis-omission slice against their annotations, and report it as a third, separate generalization check — never pooled with the discharge-summary or Synthetic Hospital numbers. Real caveats that keep this bottom-of-list: different note type (SOAP progress notes, not discharge summaries), different MIMIC version (III vs. your IV data), and it only covers diagnoses — no meds, follow-up, negation, or temporal errors. Skip unless Extension B's other two sources leave time and the judge-generalization question still feels open.

---

## What "done" looks like

**Core plan:**
- A frozen task spec ✅ and clinician-labeled key facts on the pilot ✅ plus a fresh validation set.
- A key-fact extractor and a presence judge, each validated against your own labels (recall/precision, κ with CIs).
- Two systems (closed-API baseline, fine-tuned open model) scored on the same frozen MIMIC held-out set.
- A statistically grounded comparison (paired test, CI) covering both quality and cost/latency.
- A short write-up: question, data, method, result, limitations — the same structure as the BrainLM paper.

**If extensions are completed (either is independently optional):**
- Extension A: a second comparison, on the same frozen MIMIC eval set, of models fine-tuned on real versus synthetic training substrates.
- Extension B: judge agreement reported on both the hand-labeled MIMIC set and the Synthetic Hospital public split, side by side.

## Open questions to resolve early

**Core plan:**
- Compute budget and access for LoRA fine-tuning (local GPU vs. cloud — decide before Stage 3).
- ~~Whether "Brief Hospital Course" alone or the full discharge summary is the right scope.~~ **Resolved:** full discharge summary.
- How large the final eval set needs to be. **Partly resolved:** 500 notes are drawn and frozen. The final n comes from a power calculation with the pilot's σ_d and a pre-registered equivalence margin δ, before any A vs. B results.
- Which non-Claude model families are enabled on Bedrock for the extractor and judge jury.
- Whether a second clinician can double-label key-fact presence on 10–15 notes, to give a human–human κ ceiling. Otherwise, report the single rater as a limitation.

**Extensions:**
- Extension A: how much work it actually is to render Synthetic Hospital records into your single-note task format — inspect a few released patients before committing.
- Extension A: whether to run the combined-corpus Arm D at all, given it doubles training size and therefore confounds substrate with data volume unless you subsample to match.
- Extension B: whether to run it before or after Stage 1 — running it first could inform your taxonomy design, but delays Stage 1's own completion.

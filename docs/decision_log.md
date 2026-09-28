# Decision log

Dated record of design decisions, their rationale, and dead ends. Newest at the bottom. Aggregate statistics only: no note text (MIMIC DUA). Note IDs appear only where needed to document a decision; they cannot be resolved without credentialed MIMIC access. Paper-ready prose goes in [methods.md](methods.md).

---

## 2026-09-26 — LLM access via AWS Bedrock only
**Decision:** All note text sent to third-party models goes through AWS Bedrock.
**Why:** PhysioNet's credentialed-data guidance permits LLM use only through services that don't retain or train on the data (Bedrock, Azure OpenAI, Vertex). Stage 2 in the plan ("Claude or GPT API") therefore means Claude via Bedrock.
**Open:** check the Bedrock model's terms on using outputs as distillation training data before Stage 3.

## 2026-09-26 — Repo hygiene for DUA-covered data
**Decision:** `data/` and `outputs/` are git-ignored; nbstripout strips notebook outputs on commit.
**Why:** samples, summaries, labels, and notebook outputs are all MIMIC-derived and cannot be shared.

## 2026-09-27 — Unit of analysis = note (= admission)
**Finding:** 331,793 notes map one-to-one to 331,793 `hadm_id`s (145,914 patients). No admission has more than one discharge summary.
**Decision:** sample notes, with at most one note per patient per set.
**Why:** the task, endpoint, and paired test are all per note. Multiple admissions from one patient would give correlated observations.

## 2026-09-27 — Patient-level split (pilot 5% / eval 15% / train 80%)
**Decision:** assign every patient once (seed 42) to a disjoint partition. Pilot and eval notes are drawn only from their own partitions.
**Why:** guarantees distillation training (Stage 3) never sees an evaluation patient, even through a different admission. The pilot is kept separate from eval because the judge prompt is tuned on it.

## 2026-09-27 — Stratify on length quartile × service group
**Decision:** 4 length quartiles × 3 service groups (medical / surgical / other) = 12 strata. Pilot uses equal allocation (diversity), eval uses proportional allocation (representativeness).
**Why:** length drives difficulty (more must-retain items, more chance of omission), and service shapes content. With n = 30, more than two stratification variables would leave empty cells. Other covariates are checked for balance (Table 1, SMDs) rather than stratified on.
**Service source:** `services.curr_service`, last entry per admission (discharge service). Grouping is a judgment call. GYN and GU were put in *surgical*; OBS and PSYCH in *other*.

## 2026-09-27 — Eligibility: require section headers
**Finding:** 12% of notes (39,885) lack a "Brief Hospital Course:" header. Inspection showed the narrative is usually still present, but de-identification replaced a span of text that included the header. In one case, the lab results run straight into the hospital course mid-word. Only ~0.3% had the header without a colon, and ~1.8% used an alternative header.
**Decision:** exclude these notes, plus notes missing discharge meds/diagnosis/follow-up headers, in-hospital deaths, and notes outside the 1st–99th length percentile. Counts are logged per step.
**Trade-off:** excluded notes skew medical (~82% vs. 62%). Noted as a limitation.

## 2026-09-27 — Dead end: patient-first sampling biased the eval set
**What happened:** the first sampler picked one random note per patient, then stratified. The eval set came out with too few ICD diagnoses (SMD −0.17 at n = 500, well beyond the ~±0.05 expected from noise).
**Why:** patient-first sampling weights patients equally. Frequent admitters (sicker, more diagnoses) contribute many notes to the population but only one chance of selection.
**Fix:** sample notes within strata and skip notes whose patient is already used. After the fix, all eval SMDs were below 0.1.

## 2026-09-27 — Eval set: 500 notes, not 150
**Decision:** freeze 500 eval notes. The final analysis n is set by a power calculation using the pilot's σ_d, before any A vs. B results are examined.
**Why:** the headline claim is equivalence, which needs a narrow CI. With placeholder σ_d = 0.15 and δ = 0.03, n ≈ 210. Eval notes are LLM-judged, not hand-labeled, so extra notes are cheap.

## 2026-09-27 — Follow-up Instructions section is fully redacted
**Finding:** the "Followup Instructions" section contains only `___` in 100% of eval notes (500/500).
**Consequence:** "follow-up instructions" on the must-retain list cannot be scored from that section. It needs redefining, e.g. follow-up content in the hospital course "Transitional Issues" or in Discharge Instructions, or dropping.
**Status:** open, to be resolved in the task spec.

## 2026-09-27 — Pilot section lengths (input for the scope decision)
**Finding (pilot, n = 30):** the Brief Hospital Course is present in all 30 notes, median ~1,900 chars (range 521–8,564), ~22% of the note. The Brief Hospital Course plus the discharge sections make up ~45%.
**Status:** scope decision (BHC only vs. BHC + discharge sections) pending pilot review.

## 2026-09-27 — Task spec drafted (full-note input, PCP handoff)
**Decision:** input = full discharge summary. Output = PCP handoff with fixed headings (Diagnoses / Hospital course / Med changes / Pending), ≤250 words. Details in [task_spec.md](task_spec.md).
**Key choices and why:**
- Medication changes only (admission list vs. discharge list, plus changes stated in the text). The full list is a copy job, and changes are what the PCP needs to act on.
- Follow-up is redefined as "pending items / actions for the PCP", sourced from anywhere in the note, because the Followup Instructions section is redacted.
- Ruled-out diagnoses are on the must-retain list, so omitting them is scored as an omission.
- Certainty must match the source. Forcing all hedges to "suspected" was rejected because it flattens real distinctions.
- Counting unit = one clinical entity. A wrong qualifier is a faithfulness error, not an omission, which keeps the two endpoints separate.
- Severity is tagged per item when the must-retain list is built, so "≥1 major omission" follows mechanically.
- Strict hallucination definition: any statement the note doesn't support, including reasonable clinical inferences.
**Open:** validate the 250-word limit on pilot must-retain lists (all items should fit in ≥90% of notes) before freezing.

## 2026-09-27 — "Active diagnosis" sharpened after first pilot note
**Trigger:** a pilot note (GI bleed, suspected from a known malignancy, in a patient with diabetes, hypertension, and prior MI) raised the question of whether all chronic conditions belong on the must-retain list.
**Decision:** a chronic condition is must-retain if anything changed or was acted on for it during the admission (treatment started, stopped, modified, or held; monitored; post-discharge management), or if it influenced a management decision. Chronic conditions that played no part in the admission remain excluded.
**Why:** the PCP needs to know about every change, including changes for chronic conditions. Including all stable history would pad the denominator with easy copy-from-history items, hide clinically important omissions, and compete for the word budget.

## 2026-09-27 — Medication changes must apply at discharge; scoring redacted entities
**Trigger:** a pilot note states "Started on ___ for DVT ppx" with the drug name redacted.
**Decision 1:** medication changes stated in the text count only if they still apply at discharge, including time-limited courses that continue after discharge. Inpatient-only medications started and stopped during the stay are not medication changes.
**Why:** the previous wording ("any change explicitly stated in the text") technically covered inpatient-only medications like DVT prophylaxis. The PCP needs what the patient leaves on.
**Decision 2:** redacted entities are scored by their identifiable clinical meaning. The item is written with the placeholder. The summary retains it if it conveys that meaning. Filling in the name is a hallucination. Items with no identifiable meaning are excluded.
**Why:** consistent with the counting unit (the drug name is a qualifier, the clinical fact is the item). Redaction should not remove clinically meaningful items from the denominator.

## 2026-09-27 — One item per drug; class-level retention; antiplatelets are high-risk
**Trigger:** a pilot note holds both aspirin and clopidogrel (on the admission list, absent at discharge, hold stated in the text) in a GI-bleed patient with prior MI.
**Decisions:**
- A change affecting several drugs is one item per drug, so partial retention (only one drug mentioned) is scored.
- A class-level summary statement ("antiplatelets held") retains every item in that class if it clearly covers them.
- The high-risk medication list now says "antithrombotics (anticoagulants and antiplatelets)" instead of "anticoagulants". Holding antiplatelets after MI (possible stent) is a major safety issue for the PCP.
**Open (spec_questions):** if the note gives no restart plan for held drugs, should the missing plan itself be flagged as a pending item?

## 2026-09-27 — Ruled-out vs. negative findings about a present condition
**Trigger:** a pilot note's GI-bleed workup found no active source, with the known duodenal mass the suspected source.
**Decision:** `ruled_out` is only for diagnoses that were considered and excluded. A negative result about a condition that is present ("no active source found") is a qualifier on that condition's diagnosis item. It becomes a separate `finding` item only if the note explicitly links it to a management decision.
**Why:** the bleed itself was not ruled out (the hemoglobin drop is real). Labeling "active bleeding ruled out" would misrepresent the clinical picture and could double-count one entity.

## 2026-09-27 — Primary endpoint switched to "actionable delta" key facts (MedFactEval-inspired)
**Trigger:** the first pilot note produced 28 must-retain items and 5 open spec questions. The exhaustive atomic list was too subjective and too slow for a single rater.
**Decision:** the reference is a list of key facts. It always includes the principal diagnosis (the reason for *this* admission). Every other fact must be an *actionable delta*: as a result of this admission, the PCP must do something, know something that changes management, or follow up on something. Conditions established before admission are included only if their status, treatment, or severity changed. There is no cap on the number of facts. Types: principal_diagnosis / diagnosis / management_change / follow_up.
**Primary endpoint:** per-note key-fact omission rate, averaged across notes. The exhaustive atomic must-retain list is dropped.
**Why:** grounded in the PCP's needs, and closer to MedFactEval (Grolleau et al. 2025), where clinician-defined key facts plus an LLM jury reached κ = 0.81 against a 7-physician panel. No cap, because deciding whether a fact meets a definition is more reproducible than ranking the top N, especially for an LLM extractor.
**Rejected:** a cap of 5 (it would need a subjective ranking step). MedFactEval's fixed 3 facts per note (misses PCP-relevant facts in complex notes; see the first pilot note).

## 2026-09-27 — Key facts on the eval set are extracted automatically (option B)
**Decision:** the GP labels key facts only on the 30 pilot notes, blind to LLM suggestions. On the eval set, a frozen LLM extractor produces them, once per note, and they are stored so every system is scored against identical facts.
**Why:** the GP doesn't have time to verify 150–250 notes. This departs from MedFactEval (clinician-defined facts) and addresses the future work they name ("standardize or automate this selection process").
**Safeguards:**
- The pilot is split once into tune and test halves of 15 each (stratified, seeded; `data/derived/pilot_folds.csv`). Prompts are iterated only on tune. Reported agreement comes from one run on test.
- The extractor and judge should not rely solely on the model family used for System A and as the distillation teacher.
- Extraction stability is checked with repeated runs.
**Contamination:** key facts for note `10291942-DS-10` were discussed with an LLM before blind labeling, so that note is forced into the tune fold.
**Limitation:** single rater, and 15 test notes means wide confidence intervals.
**Housekeeping:** all 30 pilot label files were regenerated under the new schema (`key_facts`). The GP chose to discard the earlier 28-item labels for `10291942-DS-10` and start from scratch.

## 2026-09-27 — Medication delta is mechanical and always complete; omissions reported by type
**Decision:** every medication that differs between the admission and discharge lists is a key fact (type `medication_change`, one per drug; substitutions count per drug; PRN and minor medications included, tagged minor). No importance filter is applied: importance lives in the severity tag. The summary's Med changes heading must list the complete delta. Group statements ("antiplatelets stopped", "all meds switched to liquid") retain every fact they cover.
**Why:** judging which medication changes "matter" was subjective (e.g. deciding what counts as high-risk). The list difference is reproducible for both raters and an LLM extractor, and medication reconciliation is what PCPs most need.
**Also decided:**
- Discharge disposition is not a key fact.
- Plans are separate `follow_up` facts (e.g. "drain exchanged" vs. "drain to be internalized").
- The principal-diagnosis fact is lean: the reason for admission plus suspected cause only; treatments are separate facts.
- `medication_change` is split out of `management_change`, so omission rates can be reported by type (secondary endpoint).
**Effect on the first pilot note:** 18 facts (9 of them medication changes), up from 14. The count rose, but each inclusion is now a mechanical or rule-based decision.

## 2026-09-28 — Pilot labels complete; spec questions resolved into general rules
**State:** 30 pilot notes labeled by the GP. 464 key facts, median ~15 per note (range 4–27). Medication changes are 44% of facts. The 107 spec questions were grouped into five themes and settled by rules: which medication lists count; facts per drug; choosing the principal diagnosis; which findings, tests and treatments count; redacted or missing information. Some label inconsistencies were corrected in the process.

## 2026-09-28 — Spec restructured as a decision procedure (consistency over per-note accuracy)
**Concern (GP):** several rules were lists of examples (drug names, test types, instruction types) tailored to the pilot, which may not generalize to thousands of notes.
**Reasoning:** both systems are scored against the same key facts, so systematic reference error largely cancels in the paired comparison, while inconsistent reference error adds variance. Consistency matters more than per-note perfection.
**Decision:** the spec is reorganized into three steps:
1. The principal diagnosis (always one).
2. Mechanical medication changes: LLM transcription of both lists, then a deterministic comparison that can run in code, then text-stated changes and conflicts.
3. A four-question test for every other candidate: new or changed this admission? matters after discharge? for a clinician? distinct fact?

Lists of examples are demoted to illustrations. The homemade high-risk medication list is replaced by the ISMP high-alert medication list (edition to be verified). Candidates the procedure doesn't settle are flagged `uncertain`, and the flag rate is reported.
**Generalization check:** the rules were written after seeing all 30 notes, test half included, so test-half agreement may be optimistic. A fresh set of 8–10 notes, labeled after the spec is frozen, becomes the primary generalization measure.
**Next:** the GP checks that the decision procedure reproduces the calls made in the 30 labeled notes, then the spec is frozen.

## 2026-09-28 — Decision procedure checked against 10 tune notes; wording fixes and silence defaults
**Check:** the GP applied the four-question test to 10 tune notes (the ones with the most non-medication facts): 48 included facts and 30 deliberately excluded candidates. The spec agreed with the original call on 67/78 rows (86%). Of the 11 mismatches, 5 were label errors (since fixed; after fixing, 72/78 = 92%), 2 were question wording, and 4 were ambiguous. Q1 (new or changed?) accounted for the most mismatches (5).
**Changes:**
- Q2: the discharge diagnosis list counts *unless the note concludes it needs no action*.
- Q2: device changes cover placed, exchanged, **or removed**.
- Q3: follow-up visits for routine post-procedure care only (wound check, routine imaging, activity clearance) are not for the clinician.
- New "When the note is silent" defaults:
  - Q1: a condition is new unless the note marks it pre-existing.
  - Q2: an open differential without a plan fails, unless the note explicitly calls it unresolved.
  
  The extractor applies the default and flags the candidate `uncertain`.
**Why defaults:** the ambiguous cases were ones where the note is silent. A fixed default gives the same answer every time, in line with the consistency-over-accuracy principle. The default directions are clinical calls made by the GP.
**Note:** these checks used tune notes only. The test half was not re-examined.

## 2026-09-28 — Two more silence defaults from the scan of the remaining 20 notes
**Trigger:** the GP's scan of the other 20 pilot notes for the situations affected by the previous changes found two cases the spec didn't settle.
**Decision 1 (rule precedence):** a hedged diagnosis (possible, probable, cannot be excluded, rule out, X vs. Y) with no plan fails Q2 even if it's on the discharge diagnosis list. The silence default takes precedence over the discharge-list bullet. A hedged diagnosis with a plan still passes. The principal diagnosis is unaffected. Cases: "possible viral illness" and "borderline traits, cannot be excluded" were on the discharge list with no plan.
**Decision 2 (new default):** a device placed this admission counts as in place at discharge only if the note says so, or a discharge treatment requires it (home IV therapy or TPN via PICC, drain care instructions). Otherwise it's treated as not in place. Case: a PICC placed mid-stay and not mentioned at discharge. This mirrors the medication rule that absence from the discharge list means stopped.
**Caveat:** the scan covered test-half notes, so these rules are again partly shaped by the test half. The fresh post-freeze validation set remains the primary generalization measure.

## 2026-09-28 — High-alert medication definition verified; medication severity made mechanical
**Finding:** the actual ISMP *List of High-Alert Medications in Community/Ambulatory Care Settings* (2021) differs from the spec's earlier paraphrase. It has no oral antiplatelets and no antiarrhythmics, and among hypoglycemics it lists only insulins and sulfonylureas. It also lists specific drugs such as methotrexate, carbamazepine, lamotrigine, phenytoin, and valproic acid.
**Decision (GP):** high-alert = ISMP 2021 plus two named project additions: oral antiplatelets (stopping them after MI or stenting is a major PCP safety issue) and class I/III antiarrhythmics (narrow margin, monitoring). A `medication_change` is major **if and only if** its drug is on this definition. The general "would change management" test applies only to non-medication facts.
**Why:** a check by drug-name matching found 40 of 78 major medication facts were not high-alert. They had been graded by case-by-case judgment, which an extractor cannot reproduce. The GP chose the strict list over adding more drug classes, to keep the spec small.
**Applied:** 40 medication facts changed from major to minor, and 1 antiplatelet fact from minor to major, by ID via script. Backup: `outputs/labels/pilot_backup_2026-09-28_pre_severity/`. Medication facts are now 38 major / 118 minor.
**Trade-off:** some clinically risky drugs not on the list (possibly lithium or antipsychotics) count as minor. This affects only the secondary endpoint "≥1 major omission"; the primary omission rate weights all facts equally.

## 2026-09-28 — Task spec frozen (v1.0)
**Word limit validated:** the GP wrote reference summaries for the 5 pilot notes with the most key facts (15–19; 19 is the pilot maximum; up to 13 medication changes) and checked every key fact for coverage. All fit in ≤216 words, so the 250-word limit stands. The original "≥90% of notes" criterion was replaced by this worst-case check: if the densest notes fit, lighter notes fit too.
**Freeze:** `docs/task_spec.md` is v1.0. Any later change needs a new version number and an entry here, and must not be informed by System A vs. B results.
**Next:** draw the fresh post-freeze validation set (8–10 notes), then set up Bedrock and build the extractor and judge.

## 2026-09-28 — Final pilot label statistics (post-freeze)
After the GP's corrections, rule changes, and mechanical severity: **280 key facts** (down from 464 at first completion), median 8.5 per note (IQR 6–13, range 1–19). By type: medication_change 156 (56%; 38 major / 118 minor), follow_up 51, principal_diagnosis 30, diagnosis 26, management_change 17. Overall 148 major / 132 minor. All 30 notes have `status: done` and a labeler. The drop from 464 facts mostly reflects the four-question test and the exclusion rules removing non-actionable candidates.
The project plan and methods draft were updated to reflect Stages 0–1 as actually done.

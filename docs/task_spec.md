# Task spec (Stage 0) — FROZEN v1.0 (2026-09-28)

*Frozen after labeling the 30 pilot notes. Any change after this point needs a new version number and a decision-log entry explaining it, and must not be informed by System A vs. System B results.*

**Purpose:** a handoff summary for the primary care physician (PCP) who sees the patient after discharge. The PCP is assumed to already know the patient's history. The summary's job is to convey what is **new or changed and actionable** as a result of this admission.

**Design principle:** the key-fact reference must be *consistent* above all. Both systems are scored against the same facts, so a stable reference matters more than per-note perfection. Rules are therefore written as general tests or mechanical procedures. Examples illustrate a test; they are never the complete list.

## Input

- **Scope:** the full discharge summary (all sections).
- **De-identification placeholders (`___`):** never filled in or guessed. The summary may keep `___` or omit the detail. An invented name, date, or value counts as a hallucination.

## Output format

- **Fixed headings, in this order:** Diagnoses / Hospital course / Med changes / Pending.
- **Med changes lists the complete medication delta:** every medication fact, not a selection.
- **Length:** ≤250 words total. Bullets are allowed under each heading. Identical for every system compared.
  - *Validated:* the clinician wrote reference summaries for the 5 pilot notes with the most key facts (15–19 facts, up to 13 medication changes; 19 is the pilot maximum). Every key fact was checked for coverage, and all five fit in ≤216 words. The limit is therefore sufficient, and omissions are the model's choice rather than forced by the budget.
- **Chronology:** the Hospital course is chronological, using relative timing (e.g. "hospital day 3", "post-op day 1"). MIMIC dates are shifted or redacted and are not used.

## Key facts: overview

Each note gets a list of **key facts**: the reference that summaries are scored against. There is **no cap** on the number per note. Facts come from three steps:

1. **The principal diagnosis:** always exactly one (Step 1).
2. **Medication changes:** mechanical, one per changed drug (Step 2).
3. **Every other fact:** a candidate is included only if it passes the four-question test (Step 3).

Facts must be grounded in the note. If the rules do not clearly settle a candidate, the extractor marks it `uncertain: true` instead of guessing (see "Who produces the key facts").

## Step 1: Principal diagnosis

Exactly one per note: **the problem that required this admission, according to the hospital course.** The order of the discharge diagnosis list does not decide it.

- Write it as **presenting problem + (suspected) cause**, keeping the note's hedge. E.g. "acute GI bleed with blood loss anemia, suspected from known duodenal adenocarcinoma", not just the underlying cancer.
- A presenting event (e.g. an overdose, fall, or seizure) belongs in this fact, in the note's own words. Do not escalate the wording beyond the note's (e.g. do not call an overingestion a suicide attempt unless the note does).
- For a scheduled or elective admission, it is the condition being treated (e.g. "AF with RVR refractory to medical management, admitted for AVJ ablation").
- Keep it lean. Treatments, other new diagnoses, and plans are separate facts.

## Step 2: Medication changes (mechanical)

One fact per drug that differs between the admission and discharge medication lists. No judgment about clinical importance is applied; importance goes in the severity tag. The procedure has three parts. **2a** is transcription, **2b** is a deterministic comparison that can be done in code, and **2c** covers the few cases that need reading the text.

**2a. Transcribe the two lists at face value** (one row per drug: name, dose, frequency, route/formulation, held yes/no).
- The *admission list* is "Medications on Admission". Add drugs the patient arrived on that are named in the text but missing from that list (e.g. "on coumadin" in the HPI, or started at an outside hospital before transfer). Drugs stopped on an earlier admission are not added.
- The *discharge list* is "Discharge Medications", including the prescription (Rx) lines. An Rx line fills a value redacted in the order line (e.g. "acetaminophen ___ mg" + "RX acetaminophen 500 mg").
- A missing or "None" admission list is an empty list. Do not reinterpret lists because the note says they "may be inaccurate" or says to "resume home medications". The allergy list is not a medication list.

**2b. Compare, drug by drug.**
- **Drug identity:** a brand and its generic are the same drug (Zestril = lisinopril). Immediate-release and extended-release forms are different drugs (oxycodone IR vs OxyContin). So are different drugs for the same indication.
- **Only on discharge = started. Only on admission = stopped. Marked "HELD" on discharge = stopped (held).** Absence from the discharge list is sufficient evidence of stopping.
- **On both lists:** it is a fact if the dose, frequency, or route/formulation differs, after dose arithmetic ("simvastatin 10 mg, 2 tablets" = "simvastatin 20 mg"). It is not a fact if everything is identical, even if the drug was held and restarted during the stay.
- **One fact per drug, however many orders.** A taper, split doses, several tablet strengths, a loading dose then maintenance, or duplicate entries are one fact.
- A substitution is one fact per drug ("omeprazole → lansoprazole ODT" = omeprazole stopped + lansoprazole started).
- As-needed and minor drugs count, tagged minor.

**2c. Text-stated changes and conflicts.**
- A change stated in the text that still applies at discharge counts even if the lists miss it. This includes time-limited courses to be completed after discharge, and an inpatient drug continuing in another form (IV antibiotics → an oral course).
- Inpatient-only drugs started and stopped during the stay (e.g. DVT prophylaxis, IV fluids) are not facts.
- **Conflicts:** if the text states a change the discharge list does not reflect, or the discharge list contradicts itself (e.g. two beta-blockers, or a sig that disagrees with the order), write one fact that follows the discharge list and states the conflict ("…needs reconciliation"). Do not silently pick one side.
- A change that cannot be established because a comparison value is redacted (e.g. admission dose `___`) is not a fact.

## Step 3: Every other candidate: the four-question test

Candidates are diagnoses, findings, test results, treatments, procedures, devices, plans, and restrictions. **Include a candidate only if all four answers are yes.**

**Q1. Is it new or changed during this admission?**
- Yes: a new diagnosis; a pre-existing condition whose status, treatment, or severity changed (e.g. cancer progression on imaging); a treatment, procedure, or device done this admission; a plan made this admission.
- No: pre-existing history that did not change (e.g. prior workups, prior events, risk-factor lists).
- *Default when the note is silent:* a condition is **pre-existing only if the note marks it so**: in the past medical history, described as "history of", "known", or "chronic", or listed as a home problem. Otherwise it is **new**.

**Q2. Does it still matter after discharge?**
- Yes if at least one applies:
  - it is carried into discharge: on the discharge diagnosis list (**unless the note concludes it needs no action**, e.g. "physiologic bradycardia, no workup needed"), or a problem with a stated plan
  - it is unresolved or pending at discharge (a pending result, "pt refused further lab draws")
  - the note attaches a recommendation to it
  - it is a lasting treatment or anatomy change (surgery, radiation, a new chemotherapy regimen, a course of ECT, antenatal steroids)
  - it changes which devices are in place at discharge: a device **placed, exchanged, or removed**
  - it is a restriction in force after discharge
- No: it resolved or was ruled out before discharge; it was purely inpatient (e.g. consults, protocols, observation level, lines placed and removed, supportive treatment such as transfusion or in-hospital antibiotics); it is a result the note does not act on.
- **Incidental findings** unrelated to the reason for admission (e.g. a pulmonary nodule) pass Q2 only through a recommendation or an unresolved status, not merely by being listed.
- *Default when the note is silent:* an open differential or uncertain finding (e.g. "hematoma versus abscess") counts as unresolved **only if the note explicitly says so or attaches a plan**. Otherwise it fails Q2.
- **Exception to the discharge-list bullet:** a *hedged* diagnosis with no plan fails Q2 **even if it is on the discharge diagnosis list**. The silence default takes precedence.
  - *Hedged* means the note's own uncertainty language: possible, probable, cannot be excluded, rule out, X vs. Y.
  - A hedged diagnosis *with* a plan still passes (e.g. "presumed UTI, complete 5 days of antibiotics").
  - The principal diagnosis is unaffected: it is always included, with its hedge.
- *Default when the note is silent:* a device placed this admission counts as **in place at discharge only if the note says so, or a discharge treatment requires it** (e.g. home IV antibiotics or TPN via PICC, drain care instructions). Otherwise it is treated as not in place.

**Q3. Is it for a clinician?**
- Yes: something a clinician must know or act on, or a restriction a clinician could unknowingly violate (e.g. "no antithrombotics until cleared by neurosurgery", "no driving after seizure").
- No: self-care instructions to the patient (e.g. wound care, activity or diet limits, return precautions, generic "follow up with your appointments"); discharge disposition (home, rehab, facility, or who the patient lives with); a follow-up visit whose only purpose is routine post-procedure care (e.g. wound check, routine imaging, activity clearance), or that has no stated purpose at all.

**Q4. Is it a distinct fact, not already covered?**
- A test or diagnostic procedure (e.g. CT, TTE, angiogram) is not its own fact. Its result goes into the diagnosis fact it supports.
- A plan that only repeats a medication fact is not separate (e.g. "continue enoxaparin for 30 days" next to "enoxaparin started, 30-day course").
- A course of repeated sessions (e.g. 3 ECT treatments) is one fact.
- A ruled-out diagnosis is a fact only if ruling it out changes what the PCP does. A negative result about a condition that *is* present (e.g. "no active bleeding source found") is a qualifier on that condition's fact.
- **Plans are their own facts:** an action someone must carry out after discharge is a separate `follow_up` fact even when it relates to another fact ("drain exchanged" and "drain to be internalized" are two facts).

### When the note is silent: defaults

When the note does not provide the information a question needs, apply the fixed default below instead of judging case by case. The extractor applies the default **and** marks the candidate `uncertain: true`, so the frequency of defaulted decisions can be reported.

| Question | Situation | Default |
|---|---|---|
| Q1 | Unclear whether a condition existed before this admission | **New**, unless the note marks it pre-existing (past medical history, "history of", "known", "chronic", or listed as a home problem). |
| Q2 | Open differential or uncertain finding at discharge, with no plan | **Fails Q2**, unless the note explicitly calls it unresolved or attaches a plan. Takes precedence over the discharge-list bullet for hedged diagnoses. |
| Q2 | Device placed this admission, not mentioned at discharge | **Not in place**, unless a discharge treatment requires it (e.g. home IV therapy via PICC, drain care instructions). |

New defaults are added here, not decided ad hoc.

## Fact types

Assigned after a fact is included.

| Type | Content |
|---|---|
| `principal_diagnosis` | Step 1. Exactly one per note. |
| `diagnosis` | A new diagnosis, or a pre-existing condition whose status or severity changed. |
| `medication_change` | Step 2. One per changed drug. |
| `management_change` | A non-medication treatment, procedure, or device that passes Step 3. |
| `follow_up` | A pending result, an action someone must take after discharge, or a restriction in force. |

## Counting unit and scoring

- **One key fact = one actionable fact.** It can include the context needed to act on it (e.g. "discharged on enoxaparin 80 mg BID for history of cardioembolic stroke").
- **Retained** = the fact's core meaning is present in the summary. Paraphrases, synonyms, and standard abbreviations count.
- **Group statements** retain every fact they clearly cover.
  - "Antiplatelets stopped" retains the aspirin and clopidogrel facts.
  - "Omeprazole switched to lansoprazole" retains both substitution facts.
  - "All medications switched to liquid/ODT forms" retains every formulation-change fact.
- **Qualifiers belong to the fact:** certainty, cause, dose, and timing. A wrong qualifier is a faithfulness error (e.g. a certainty or negation error), not an omission.
- **Redacted entities (`___`):**
  - A fact is included if its clinical meaning can still be identified from context. Write it with the placeholder (e.g. `started ___ for DVT prophylaxis`).
  - A redacted count or date does not remove a fact (e.g. "received ___ radiation treatments").
  - A fact with nothing identifiable left, or a fully redacted result, is not a fact.
  - Blank or fully redacted follow-up instructions produce no `follow_up` fact.
  - It counts as retained if the summary conveys the meaning. Filling in the redacted value is a hallucination.

## Negation and uncertainty

- **Preserve the certainty stated in the source.** Hedged findings stay hedged ("possible", "likely", "concerning for"). Turning a hedge into a definite statement, or the reverse, is an error.
- Negated findings keep their negation. Dropping a negation ("no evidence of PE" becoming "PE") is a major error.

## Severity

Each key fact is tagged **major** or **minor**.

- **Major:** would plausibly change the PCP's management or patient safety if missed or wrong. This always includes:
  - the principal diagnosis
  - changes to a **high-alert medication**, defined as:
    - **the *ISMP List of High-Alert Medications in Community/Ambulatory Care Settings* (ISMP, 2021)**. Its classes: antithrombotic anticoagulants (warfarin, LMWH, heparin, DOACs/factor Xa inhibitors, direct thrombin inhibitors); chemotherapy, including oral targeted therapy and immunotherapy (excluding hormonal therapy); immunosuppressants; all insulins; opioids (all routes and formulations); sulfonylureas; drugs contraindicated in pregnancy; oral pediatric sedation agents; pediatric liquids that require measurement. Its specific drugs: carbamazepine, IM/SC epinephrine, lamotrigine, methotrexate (non-oncologic), phenytoin, valproic acid.
    - **plus two project additions**, which are not on the ISMP community list:
      - **oral antiplatelets** (e.g. aspirin, clopidogrel, prasugrel, ticagrelor), because stopping them after MI or stenting is a major safety issue for the PCP;
      - **class I and III antiarrhythmics** (e.g. amiodarone, dronedarone, sotalol, dofetilide, flecainide, propafenone), because of their narrow margin and monitoring needs.
  - follow-up actions with a deadline or safety risk, and restrictions in force
  - procedures or devices with lasting consequences
- **Minor:** every other key fact.
- **Medication changes are graded mechanically:** a `medication_change` is major **if and only if** the drug is on the high-alert definition above (ISMP 2021 plus the two project additions). Otherwise it is minor. The general "would change management" test applies only to non-medication facts.
- **Hallucinations:** major if they could change management (wrong drug or dose, fabricated diagnosis), minor otherwise.

## Endpoints

- **Primary:** key-fact omission rate, computed per note (omitted key facts ÷ key facts in that note), then **averaged across notes**, so each note counts equally. The paired comparison of systems is per note.
- **Secondary:**
  - hallucination (unsupported statement) rate
  - key-fact omission rate **by type**, each averaged across notes that have facts of that type
  - ≥1 major key-fact omission (binary)
  - ≥1 unsupported statement (binary)
  - contradiction of a key fact (as in MedFactEval's contradiction check)
- **Hallucination (unsupported statement):** any statement not supported by the source note. This includes clinically reasonable inferences that the note does not state.

## Who produces the key facts

- **Pilot (30 notes):** labeled by the clinician (GP), blind to LLM suggestions. Split once into **tune** and **test** halves (stratified, seeded; `data/derived/pilot_folds.csv`).
  - Extractor and judge prompts are iterated only against the tune half.
  - Few-shot examples in the prompts come only from the tune half.
  - *Caveat:* the spec's rules were written after labeling all 30 notes, so they encode edge cases from the test half too. Test-half agreement may therefore be optimistic.
- **Fresh validation set (8–10 notes):** new notes from the pilot patient pool, labeled after the spec is frozen and never used to write rules. Agreement here is the primary measure of how well the spec and extractor generalize.
- **Eval set:** key facts come from the frozen extractor, once per note, and are stored so every system is scored against identical facts.
  - Step 2 runs as transcription by LLM plus comparison in code.
  - Candidates the procedure does not clearly settle are flagged `uncertain`. The flag rate is reported as a measure of spec coverage.
  - To limit bias toward one model family, the extractor and judge should not rely solely on the model family used for System A and as the distillation teacher (use a different family, or a mixed-family jury).

## Data handling

MIMIC text only leaves this machine via AWS Bedrock (per PhysioNet's responsible-LLM-use guidance). No derived data in git.

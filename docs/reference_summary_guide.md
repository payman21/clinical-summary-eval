# Writing reference summaries (word-limit check)

## What they are for

Reference summaries test one thing: **can every key fact of a note fit within the 250-word limit** in the task spec's output format? They are a budget test, not gold summaries. Model summaries are never scored against them, so write them to be complete and realistic, not polished.

They are needed only for the notes most likely to exceed the budget: the notes with the most key facts, especially the most medication changes. Two or three notes in addition to `10291942-DS-10` are enough.

## Before you start

- Finish and check the note's key facts first. The summary is written **from the key-fact list**, with the note open for context.
- Have [task_spec.md](task_spec.md) at hand for the output format and the group-statement rule.

## Format

Use the four headings from the task spec, in this order:

1. **Diagnoses**: the principal diagnosis first, then other `diagnosis` facts.
2. **Hospital course**: chronological and brief, with relative timing ("HD 3", "POD 1"), never dates. Include only what's needed to understand the diagnoses, management changes, and plans.
3. **Med changes**: the complete medication delta. Every `medication_change` fact must be covered.
4. **Pending**: every `follow_up` fact (pending results, actions, restrictions).

**Style:**
- Short telegraphic bullets, the way you would write them for a colleague. No full sentences needed.
- Semicolons join related points. Parentheses hold values (e.g. "(Hgb 6.8)").
- Use arrows for changes: `metoprolol 25 -> 50 mg BID`, `omeprazole -> lansoprazole ODT`.
- **Group medication changes** where the spec's group-statement rule allows. One bullet can cover several facts:
  - `aspirin, clopidogrel stopped (bleeding)` covers two facts.
  - `insulin 70/30 -> glargine 14 u qPM + regular SSI` covers three facts.
  - `all meds switched to liquid/ODT` covers every formulation-change fact.
- Keep the note's hedges ("suspected", "possible", "concerning for"). Keep `___` placeholders or leave the detail out; never fill them in.

## Steps

1. **Draft the summary** under the four headings, working through the key-fact list.
2. **Check coverage fact by fact.** Go through the YAML key facts one at a time and confirm each is covered by some bullet, directly or through a group statement. Add anything missing. If a fact is missing, the word count understates what's needed, and the check is meaningless.
3. **Count the words** by running `load_labels()` in the notebook. The `reference_summary_words` column gives the total.
4. **If it's over 250 words, trim in this order:**
   1. Hospital course: it carries few key facts. Cut to the minimum chronology.
   2. Redundant wording in any section (repeated context, full sentences).
   3. More medication grouping.

   Never trim by dropping a key fact. If the summary is still over 250 words with every fact present, stop and record it. That is the finding: the limit is too tight for this note.
5. **Record the result** in the note's YAML as described below.

## How to store it in the YAML

Write it as plain text under a block marker (`|`). The model summaries will be plain text too, so the two are easy to compare, and the block marker avoids YAML quoting problems.

```yaml
reference_summary: |
  Diagnoses:
  - Acute decompensated heart failure, likely precipitated by dietary indiscretion (EF 30%).
  - New AKI on CKD 3 (Cr 1.4 -> 2.1), improving at discharge.
  Hospital course:
  - IV diuresis HD 1-4, ~5 kg net negative; transitioned to oral diuretic HD 5.
  Med changes:
  - Furosemide 40 mg daily -> torsemide 20 mg daily.
  - Lisinopril held (AKI).
  - Metoprolol succinate 25 -> 50 mg daily.
  Pending:
  - BMP in 1 week; restart lisinopril if Cr back to baseline.
  - Daily weights; cardiology follow-up re: ICD evaluation.
```

(This example is fictional, for format only.)

## Done when

- Every key fact in the YAML is covered by the summary.
- The word count is recorded via `load_labels()`.
- If the summary exceeds 250 words with every fact present, this is noted in the decision log. The spec's limit is then revisited before freezing: either raise it, or allow a more compact medication format.

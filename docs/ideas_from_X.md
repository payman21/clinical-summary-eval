If I had 6 months to become an AI Evals Engineer.

I’d do this.

Stage 1: Testing Foundations and Statistics for AI
- Learn: pytest (fixtures, parametrize), JSONL pipelines, precision/recall/F1, confidence intervals, Cohen's kappa.

- Practice:  Build a pytest plugin that loads a JSONL eval dataset and emits a metric report on every run.

- Why:  Evals are tests and tests are math. If you cannot quantify agreement, you cannot prove improvement.

Stage 2: LLM Failure Modes and Behavior
- Learn:  temperature and top-p sampling, seed control, tokenization edge cases, instruction drift, hallucination taxonomies.

- Practice:  Fuzz one model with 500 adversarial inputs and classify every failure into a taxonomy with reproduction steps.

- Why:  Every eval suite is a map of known failure modes. You cannot evaluate what you do not understand.

Stage 3: Golden Dataset Engineering
- Learn:  annotation guidelines, stratified sampling, inter-annotator agreement, dataset versioning, contamination detection.

- Practice:  Build a 300-case golden dataset with 2 annotators, measure kappa, and version it in git with a changelog.

- Why:  Your evals are only as good as your dataset. Garbage labels produce garbage confidence.

Stage 4: Scoring Methods and LLM-as-a-Judge
- Learn:  exact and fuzzy match, embedding similarity, rubric design, judge model selection, judge biases (verbosity, position, self-preference).

- Practice:  Build an LLM-as-a-judge with a rubric, calibrate it against 100 human labels and publish the agreement score.

- Why:  Judges drift and lie. Calibrated judges are instruments; uncalibrated ones are vibes.

Stage 5: RAG Evaluation
- Learn:  hit rate, MRR, NDCG, recall@k, faithfulness vs relevance, citation grounding, abstention quality.

- Practice:  Build a RAG eval harness with separate retrieval and generation gates, plus adversarial queries that must return "no answer".

- Why:  RAG fails in two places. A single score hides which one is broken.

Stage 6: Agent and Trajectory Evaluation
- Learn:  tool-call correctness, step-level grading, trajectory distance metrics, counterfactual replay, sandboxed execution scoring.

- Practice:  Build a trajectory grader that scores each tool call against a golden path and blocks dangerous action sequences.

- Why:  Final-answer evals hide where agents actually break. The trajectory is the unit of accountability.

Stage 7: Eval Frameworks and Custom Harnesses
- Learn:  DeepEval, promptfoo, RAGAS, Braintrust, OpenAI Evals; dataset-driven pipelines, parameterized configs.

- Practice:  Write a custom harness that runs 3 frameworks behind one CLI and outputs a unified metric report.

- Why:  Frameworks give you scaffolding. A custom harness gives you control when the scaffolding lies.

Stage 8: Statistical Rigor for Eval Deltas
- Learn:  bootstrap confidence intervals, paired significance tests, effect size, sample-size math, seed variance.

- Practice:  Build a comparison report that says "Model B wins by 3.2% ± 1.1% (p<0.05)" instead of "Model B seems better".

- Why:  A 2-point difference on 50 samples is noise. Executives make million-dollar decisions on your numbers.

Stage 9: CI/CD Eval Gates and Regression Control
- Learn:  GitHub Actions eval jobs, thresholds with hysteresis, eval caching, cost budgets, flaky-eval detection.

- Practice:  Wire a gate that blocks merges when task success drops >2% vs main and auto-posts failing cases to the PR.

- Why:  Evals that do not block deploys are reports not gates.

Stage 10: Production Monitoring and Drift Detection
- Learn:  Langfuse, LangSmith, Phoenix, traffic sampling strategies, drift metrics, hallucination spike alerts, feedback-trace correlation.

- Practice:  Build a pipeline that samples 5% of prod traffic nightly, runs offline evals and alerts on quality decay.

- Why:  Golden datasets go stale. Production is the eval suite that never stops updating.

Stage 11: Data Flywheels and Eval-Driven Optimization
- Learn:  feedback-to-dataset loops, DPO preference pairs, eval-driven prompt optimization (DSPy), A/B testing with guardrail metrics.

- Practice:  Automate the loop: thumbs-down → labeled case → golden set addition → nightly eval run → diff report.

- Why:  The compounding advantage in AI is not the model. It is the flywheel that converts failures into tests.

Stage 12: Red-Teaming, Public Benchmarks and Portfolio
- Learn:  adversarial suites (injection, jailbreaks, data exfiltration), benchmark methodology, contamination-aware reporting.

- Practice:  Publish a public eval teardown of your agent vs a naive baseline with full methodology and reproducible seeds.

- Why:  Senior evals engineers are hired for their methodology not their dashboards.

Vibe-checking is dead. If you cannot measure it, you cannot ship it.
The modern AI Evals Engineer builds the quality gates for every autonomous system.

Bookmark and Repost!
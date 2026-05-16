# EDA Iteration Plan

## Objective

Execute EDA in small iterations so each pass reduces uncertainty and produces something usable for the next step in anomaly detection and XAI.

Primary datasets:

- `host_logs.parquet`
- `ground_truth.parquet`

Reference detail:

- `docs/eda.md`

## Working Principles

- Start with schema validation before interpretation
- Prefer DuckDB queries that can run directly on parquet
- Use aggregation first, then selective row sampling
- Do not assume semantic column names until they are verified
- Record every unresolved assumption explicitly

## Iteration 1: Dataset Orientation

Goal:

Confirm what is in each parquet file and establish the minimum trustworthy schema.

Tasks:

- Count rows in both parquet files
- Run `DESCRIBE` on both datasets
- Inspect representative samples from both files
- Confirm date and time ranges
- List candidate meanings for each host log column
- Identify which columns are still ambiguous

Deliverables:

- Verified schema summary
- Short ambiguity list
- Updated notebook cells for schema inspection

Exit criteria:

- Both datasets can be queried reliably
- Each column has either a likely meaning or is explicitly marked unknown

## Iteration 2: Data Quality Baseline

Goal:

Measure whether the data is clean enough for feature engineering.

Tasks:

- Count nulls and blanks by column
- Measure duplicate rows
- Compute cardinality per column
- Detect constant or near-constant columns
- Flag malformed values and suspicious outliers
- Identify columns that are noisy or low value

Deliverables:

- Data quality report
- Cleanup candidates list
- Exclusion candidates list

Exit criteria:

- Major quality risks are documented
- Low-signal columns are identified for later exclusion

## Iteration 3: Label And Ground Truth Mapping

Goal:

Understand how anomalies are labeled and how `ground_truth.parquet` should be used.

Tasks:

- Inspect `ground_truth.parquet` schema and samples
- Determine whether `host_logs.parquet` contains direct labels
- Measure class balance if labels exist in host logs
- Document how ground truth relates to host logs
- Identify any leakage risk from label-like fields
- Record unresolved join or alignment assumptions

Deliverables:

- Label strategy note
- Ground truth mapping note
- Leakage risk list

Exit criteria:

- Label source for modeling is clear
- Relationship between datasets is either defined or narrowed to a short list of possibilities

## Iteration 4: Temporal And Behavioral Profiling

Goal:

Understand how activity changes over time and across entities.

Tasks:

- Plot event volume by day and hour
- Plot anomaly counts and anomaly rate over time if labels are available
- Profile common processes, parent processes, and paths
- Inspect rare entities and rare combinations
- Compare normal versus anomalous activity where possible
- Look for burst windows, drift, and repeated suspicious patterns

Deliverables:

- Temporal summary
- Entity distribution summary
- Initial anomaly behavior observations

Exit criteria:

- Time-driven and entity-driven patterns are documented
- Candidate behavioral signals are identified

## Iteration 5: Feature Candidate Design

Goal:

Translate EDA results into a practical modeling input plan.

Tasks:

- Confirm which columns are usable as raw inputs
- Propose derived time-based features
- Propose rarity and frequency features
- Propose process-path and parent-child interaction features
- Identify leakage-prone columns to exclude
- Separate modeling features from metadata-only fields

Deliverables:

- Feature shortlist
- Exclusion list with reasons
- Draft modeling-ready schema

Exit criteria:

- There is a defensible first-pass feature set for anomaly detection
- Leakage risks are clearly excluded or quarantined

## Iteration 6: EDA Consolidation

Goal:

Package findings into reusable project artifacts.

Tasks:

- Clean up the notebook into clear EDA sections
- Save key plots and tables
- Write a findings summary
- Update assumptions and open questions
- Link outputs back to modeling next steps

Deliverables:

- Updated `notebook/Anomaly_Detection.ipynb`
- `docs/eda-findings.md`
- Final EDA summary for handoff into modeling

Exit criteria:

- Another person can understand the data and continue into modeling without redoing the exploration

## Suggested Execution Order

1. Iteration 1
2. Iteration 2
3. Iteration 3
4. Iteration 4
5. Iteration 5
6. Iteration 6

## Risks To Watch

- Generic host log column names may hide incorrect assumptions
- `ground_truth.parquet` may not align directly with host log rows
- Some host log columns may already encode labels and create leakage
- Dataset size may require aggregate-first analysis instead of full materialization

## Definition Of Done

EDA is complete when:

- Schema and column meanings are documented
- Data quality risks are quantified
- Labeling strategy is clear
- Temporal and behavioral patterns are summarized
- Feature candidates and exclusion decisions are written down
- Findings are captured in reusable docs and notebook outputs

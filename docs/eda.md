# EDA Plan

## Goal

Build a clear understanding of the two parquet datasets before feature engineering or modeling:

- `host_logs.parquet`
- `ground_truth.parquet`

The EDA should answer three questions:

1. What is actually in each file?
2. How trustworthy and usable is the data?
3. What structure can be turned into anomaly-detection features and later explained with XAI?

## Important Constraint

The parquet files now use the official NGIDS field names, but semantic assumptions still need validation against row content. In particular, `ground_truth.parquet` contains dirty embedded header rows, so field names alone do not mean the data is clean.

## Phase 1: Schema And Sanity Checks

Objective: confirm dataset shape and basic semantics.

Tasks:

- Count rows in `host_logs.parquet` and `ground_truth.parquet`
- Run `DESCRIBE` on both files
- Inspect 20 to 50 sample rows from each file
- Record column types, likely meanings, and obvious ambiguities
- Check date and time ranges
- Check whether rows are unique or duplicated

Outputs:

- A schema table for both datasets
- A short note listing columns that are still uncertain

## Phase 2: Data Quality Assessment

Objective: measure whether the data is clean enough for downstream analysis.

Tasks:

- Count nulls, blanks, and placeholder values per column
- Check cardinality for each column
- Identify columns that are constant or nearly constant
- Check for malformed timestamps, negative ids, or impossible values
- Measure duplicate row count
- Flag columns with extreme skew or noisy free-text values

Outputs:

- Data quality summary
- List of columns needing cleanup, recoding, or exclusion

## Phase 3: Label And Ground Truth Audit

Objective: understand how anomalies are represented and how ground truth should be used.

Tasks:

- Check class balance in `host_logs.parquet` if a label column exists there
- Inspect the schema of `ground_truth.parquet`
- Identify what each ground-truth row represents: attack family, network flow, time window, category, etc.
- Determine how `ground_truth.parquet` relates to `host_logs.parquet`
- Document whether the relationship is direct, indirect, or still unknown
- Flag leakage risks if any host log column already contains label-like information

Outputs:

- Class balance summary
- Clear statement of how labels should be sourced for modeling
- List of unresolved alignment assumptions

## Phase 4: Host Log Temporal And Entity Profiling

Objective: understand when anomalies occur and how they concentrate across host-log entities.

Tasks:

- Check class balance in `host_logs.parquet`
- Plot event counts by day and hour
- Plot anomaly counts and anomaly rate over time
- Check whether certain dates or hours dominate the anomalies
- Profile top values for `path`, `sys_call`, and `pro_id`
- Compare anomaly concentration by executable path
- Inspect `path x sys_call` combinations
- Identify rare or unseen entities
- Flag shortcuts that could dominate a random-split evaluation

Outputs:

- Time-series summaries
- Top-k entity distributions
- Notes on burstiness, shortcut risk, and behavioral signals

## Phase 5: Feature Readiness

Objective: turn EDA findings into a modeling plan.

Tasks:

- Propose a cleaned schema with confirmed column meanings
- Decide which columns are raw inputs, derived features, or metadata only
- Define candidate features such as:
  - timestamp features
  - event frequency features
  - path rarity features
  - process/path interaction features
  - path/syscall interaction features
  - rolling or windowed count features
  - per-process aggregate features
- Mark columns to exclude because of leakage or low value
- Recommend a train/validation/test split strategy that respects temporal structure

Outputs:

- Modeling-ready feature shortlist
- Exclusion list with reasons

## Phase 6: Visualization Pack

Objective: produce a compact set of visuals that summarize the dataset.

Recommended visuals:

- Schema summary table
- Null-rate table
- Class balance chart
- Event volume over time
- Top processes and top paths
- Anomaly rate by process/path
- Distinct-count summary for high-cardinality columns

## Recommended Order Of Execution

1. Confirm schema and types
2. Validate data quality
3. Audit labels and ground truth relationship
4. Analyze temporal and entity-level host behavior
5. Produce the feature shortlist and split strategy

## Suggested Deliverables

- This plan in `docs/eda.md`
- EDA notebook sections added to `notebook/Anomaly_Detection.ipynb`
- A follow-up findings document such as `docs/eda-findings.md`

## Done Criteria

The EDA is complete when:

- Both parquet schemas are documented
- Data quality issues are quantified
- Label sourcing is clear
- Temporal and entity-level behavior is summarized
- Candidate modeling features and leakage risks are explicitly listed

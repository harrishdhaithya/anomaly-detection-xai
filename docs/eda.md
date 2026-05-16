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

## Phase 3: Host Log Structure

Objective: understand how activity is distributed across processes, paths, and identifiers.

Tasks:

- Profile top values for each categorical column
- Measure distinct counts for pid-like, ppid-like, path-like, and label-like columns
- Inspect the most common processes and paths
- Identify rare processes and rare paths
- Check whether the same process/path combinations recur over time
- Look for columns that may directly encode normal vs anomalous behavior

Outputs:

- Top-k distributions for key columns
- Notes on which columns are likely useful for behavioral modeling

## Phase 4: Label And Ground Truth Audit

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

## Phase 5: Temporal Analysis

Objective: understand event volume and anomaly behavior over time.

Tasks:

- Plot event counts by day and hour
- Plot anomaly counts and anomaly rate over time
- Look for burst periods, outages, or drift
- Check whether certain dates or hours dominate the anomalies
- Compare normal and anomalous periods if labels are available

Outputs:

- Time-series summaries
- Notes on drift, burstiness, and temporal segmentation needs

## Phase 6: Entity And Behavioral Analysis

Objective: identify behavior patterns that can separate normal from anomalous activity.

Tasks:

- Compare anomaly rate by process, parent process, and path
- Inspect process-path and parent-child combinations
- Measure event frequency per pid and per ppid
- Identify rare or unseen entities
- Look for suspicious concentrations around specific executables or paths
- Examine local sequence context around anomalous rows if feasible

Outputs:

- Candidate behavioral signals
- Shortlist of entities and combinations worth modeling

## Phase 7: Feature Readiness

Objective: turn EDA findings into a modeling plan.

Tasks:

- Propose a cleaned schema with confirmed column meanings
- Decide which columns are raw inputs, derived features, or metadata only
- Define candidate features such as:
  - timestamp features
  - event frequency features
  - path rarity features
  - process/path interaction features
  - parent-child relationship features
  - rolling or windowed count features
- Mark columns to exclude because of leakage or low value

Outputs:

- Modeling-ready feature shortlist
- Exclusion list with reasons

## Phase 8: Visualization Pack

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
4. Analyze temporal behavior
5. Analyze entities and interactions
6. Produce feature shortlist

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

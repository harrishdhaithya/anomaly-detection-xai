# EDA Findings

## Phase 1

Date: 2026-05-16

Scope:

- Verify row counts
- Inspect parquet schemas
- Review representative sample rows
- Confirm basic date coverage
- Record early assumptions and unresolved ambiguities

## Dataset Summary

### `host_logs.parquet`

- Row count: `90,054,239`
- Distinct full rows: `89,709,941`
- Duplicate full rows: `344,298`
- Columns: `9`
- Date range: `2016-03-11` to `2016-03-16`
- Time range: `00:00:00` to `23:59:59`

Schema:

| Column | Type | Interpretation |
| --- | --- | --- |
| `date` | `DATE` | event date |
| `time` | `TIME` | event time |
| `pro_id` | `BIGINT` | process identifier |
| `path` | `VARCHAR` | executable path |
| `sys_call` | `BIGINT` | system call identifier |
| `event_id` | `BIGINT` | event identifier |
| `attack_cat` | `VARCHAR` | high-level attack category |
| `attack_subcat` | `VARCHAR` | attack subtype or scenario |
| `label` | `BIGINT` | binary anomaly label |

Evidence:

- `path` contains values such as `/usr/sbin/apache2`, `/usr/bin/python3.4`, `/sbin/auditd`
- `attack_cat` contains values such as `normal`, `Exploits`, `Denial of Service`, `Backdoors`
- `attack_subcat` contains values such as `normal`, `Office Document Batch`, `Browser`, `All Batch`
- `label` contains only `0` and `1`

Selected distinct counts:

- `pro_id`: `5,576`
- `path`: `100`
- `sys_call`: `122`
- `event_id`: `89,709,941`
- `attack_cat`: `8`
- `attack_subcat`: `53`
- `label`: `2`

Label-like distribution:

- `label = 0`: `88,791,812`
- `label = 1`: `1,262,427`

Preliminary interpretation:

- `label` is the final binary anomaly label
- `attack_cat` and `attack_subcat` hold richer attack-category annotations
- This creates an immediate leakage risk for downstream supervised modeling if `attack_cat` or `attack_subcat` are used as features

### `ground_truth.parquet`

- Row count: `313,926`
- Distinct full rows: `311,621`
- Duplicate full rows: `2,305`
- Columns: `7`
- Date range: `2016-03-11` to `2016-03-16`

Schema:

| Column | Type | Interpretation |
| --- | --- | --- |
| `date` | `DATE` | event date |
| `time` | `VARCHAR` | expected time field, but dirty |
| `attack_cat` | `VARCHAR` | attack family / class |
| `attack_subcat` | `VARCHAR` | attack subtype / batch / protocol family |
| `attack_name` | `VARCHAR` | strike name / attack description |
| `attack_refrence` | `VARCHAR` | reference / CVE / metadata text |
| `ips` | `VARCHAR` | network tuple or tuple list |

Representative values:

- `attack_cat`: `Backdoors`, `Exploits`, `Malware`, `Denial of Service`
- `attack_name`: long strike descriptions with vulnerability names
- `ips`: strings that look like IP and port tuples such as `175.45.176.0:13177->10.40.85.32:514`

## Important Data Issue In `ground_truth.parquet`

`ground_truth.parquet` contains repeated header-like rows inside the dataset.

Confirmed signal:

- Rows with `time = 'Time'`: `26`

Example embedded header row:

- `2016-03-11`, `Time`, `Malware`, `Mobile Batch`, `Strike Name`, `Strike Reference`, `Strike Tuples`

Impact:

- `time` cannot yet be treated as a clean time column
- Categorical counts in `ground_truth.parquet` are currently inflated by repeated header rows
- Phase 2 needs to explicitly remove or isolate these rows before quality profiling

## Cross-Dataset Observations

- `host_logs.parquet` already contains attack family and scenario labels inside the table
- `ground_truth.parquet` appears to contain attack metadata and network tuple annotations
- The exact relationship between host-log rows and ground-truth rows is still unresolved
- That mapping should be treated as a Phase 3 question, not assumed now

## Ambiguities Still Open

### `host_logs.parquet`

- The parquet file now uses the official NGIDS field names
- `sys_call` and `event_id` align with the public feature description, but they should still be validated against downstream usage
- `attack_cat` and `attack_subcat` are labels, not safe default features

### `ground_truth.parquet`

- `time` is not a clean time field because of embedded header rows
- Some category values include leading spaces such as ` Exploits` and ` Denial of Service`
- The intended join key or alignment rule between `ground_truth.parquet` and `host_logs.parquet` is not yet known

## Phase 1 Conclusion

What is now verified:

- Both parquet files are queryable with DuckDB
- `host_logs.parquet` is the main large event table with `90M+` rows
- `ground_truth.parquet` is a smaller attack-metadata table with `313k+` rows
- Both parquet files now use the official NGIDS column names
- `host_logs.parquet` includes direct binary and categorical label-like fields
- `ground_truth.parquet` has a real quality issue due to repeated header rows

What should happen next:

- Phase 2 should focus on data quality profiling
- The first quality fix to validate is the removal or filtering of header-like rows in `ground_truth.parquet`
- Leakage-prone host log columns should already be flagged before any feature design starts

## Phase 2

Date: 2026-05-17

Scope:

- Build a data quality baseline for both parquet files
- Quantify nulls, blanks, duplicates, and whitespace issues
- Validate cleaning rules for `ground_truth.parquet`

## `host_logs.parquet` Quality Baseline

### Structural Quality

- No nulls in any column
- No blank strings in `path`, `attack_cat`, or `attack_subcat`
- No negative values in `pro_id`, `sys_call`, or `event_id`
- No invalid values in `label`

### Minor Quality Issues

- `sys_call = 0` appears in `573` rows
- `attack_subcat` has outer whitespace in `495,005` rows
- `attack_subcat` distinct count drops from `53` raw values to `45` trimmed values
- `attack_cat` distinct count stays at `8` after trimming

Examples of host subcategory normalization issues:

- ` Clientside` -> `Clientside`
- `Browser FTP Batch ` -> `Browser FTP Batch`
- ` NetBIOS/SMB Batch ` -> `NetBIOS/SMB Batch`
- `All Batch ` -> `All Batch`

### Host Log Conclusion

`host_logs.parquet` is structurally clean and usable for EDA. The main cleanup need is category normalization on `attack_subcat`. The label and attack columns remain leakage-sensitive and should not be treated as default model features.

## `ground_truth.parquet` Quality Baseline

### Raw Structural Quality

- No nulls in any column
- No blank strings in any column
- `26` embedded header-like rows where `time = 'Time'`
- `177,418` rows where `attack_cat` has outer whitespace
- `122,806` rows where `attack_subcat` has outer whitespace
- `attack_cat` distinct count drops from `357` raw values to `355` trimmed values
- `attack_subcat` distinct count drops from `130` raw values to `118` trimmed values

### Row Corruption Patterns

Beyond the repeated header rows, `ground_truth.parquet` contains two row-shift patterns.

#### Shift Pattern A

Rows: `300`

Observed pattern:

- `time` contains the attack reference text
- `attack_cat` contains the IP tuple
- `attack_subcat` contains the actual time value
- `attack_name` contains the true attack category
- `attack_refrence` contains the true attack subcategory
- `ips` contains the true attack name

#### Shift Pattern B

Rows: `201`

Observed pattern:

- `time` contains the IP tuple
- `attack_cat` contains the actual time value
- `attack_subcat` contains the true attack category
- `attack_name` contains the true attack subcategory
- `attack_refrence` contains the true attack name
- `ips` contains the true attack reference

### Decision Note

After comparing [ground_truth.csv](/Users/harrish/Desktop/practicum/anomaly-detection-xai/dataset/ground_truth.csv:1) and [ground_truth.parquet](/Users/harrish/Desktop/practicum/anomaly-detection-xai/dataset/ground_truth.parquet:1), the corruption is confirmed to exist in the source CSV as well.

Project decision:

- Remove embedded header rows instead of treating them as valid data
- Remove both row-shift corruption patterns instead of repairing them for downstream EDA and modeling
- Treat these rows as source-data corruption, not missing-value cases

Rows to exclude under this decision:

- `26` embedded header rows
- `300` shift pattern A rows
- `201` shift pattern B rows
- total removal set: `527` rows

### Cleaned Ground Truth View

After:

- filtering header rows
- removing both row-shift corruption patterns
- trimming category fields

the cleaned baseline becomes:

- usable rows: `313,399`
- distinct full rows: `311,107`
- duplicate full rows: `2,292`
- `9` canonical attack categories remain:
  - `Exploits`
  - `Malware`
  - `Denial of Service`
  - `Generic`
  - `Shellcode`
  - `Reconnaissance`
  - `Worms`
  - `Backdoors`
  - `Fuzzers`

Category counts after cleaning:

- `Exploits`: `231,600`
- `Malware`: `35,900`
- `Denial of Service`: `24,799`
- `Generic`: `11,300`
- `Shellcode`: `5,300`
- `Reconnaissance`: `1,900`
- `Worms`: `1,300`
- `Backdoors`: `1,200`
- `Fuzzers`: `100`

## Phase 2 Conclusion

What is now verified:

- `host_logs.parquet` is largely clean and stable for analysis
- `ground_truth.parquet` cannot be used raw without cleaning
- `ground_truth.parquet` requires three fixes:
  - remove embedded header rows
  - trim categorical whitespace
  - remove both row-shift corruption patterns

What should happen next:

- Use a filtered `ground_truth` subset with header rows and corrupted rows removed for all further EDA
- Start Phase 3 by determining how the cleaned ground truth aligns with host log rows
- Keep `attack_cat`, `attack_subcat`, and `label` out of default feature candidates until the modeling strategy is explicit

## Phase 3

Date: 2026-05-17

Scope:

- Test whether filtered `ground_truth` aligns directly with anomalous `host_logs`
- Check overlap on `date`, `time`, `attack_cat`, and `attack_subcat`
- Decide whether `ground_truth` is a join table or supporting metadata

## Initial Alignment Check

Filtered `ground_truth` baseline:

- rows: `313,399`
- distinct `(date, time, attack_cat, attack_subcat)` keys: `4,921`

Anomalous `host_logs` baseline:

- rows with `label = 1`: `1,262,427`
- distinct `(date, time, attack_cat, attack_subcat)` keys: `5,081`

Exact overlap on `(date, time, attack_cat, attack_subcat)`:

- `ground_truth` rows with an exact host-log match: `587`
- anomalous host-log rows with an exact ground-truth match: `55,989`
- distinct shared exact keys: `308`

Broader overlap on `(date, time)` only:

- `ground_truth` rows with an anomalous host-log timestamp match: `79,182`
- anomalous host-log rows with a filtered ground-truth timestamp match: `55,989`

Interpretation:

- `ground_truth` is not behaving like a clean one-to-one event label table for `host_logs`
- the overlap is real, but it is limited and concentrated in a small shared key space
- `ground_truth` looks more like attack metadata plus network tuple annotations with partial temporal overlap
- `host_logs.label` remains the primary supervised target for modeling

Current working decision:

- treat filtered `ground_truth` as supporting metadata, not a required training join table
- continue host-log EDA and feature design without depending on a strict row-level `ground_truth` join

## Phase 4

Date: 2026-05-18

Scope:

- Profile temporal concentration of anomalies in `host_logs.parquet`
- Measure anomaly concentration by path, syscall, and process id
- Translate those distributions into leakage-safe feature guidance

## Temporal Concentration

Daily anomaly rate:

- `2016-03-11`: `1.1810%`
- `2016-03-12`: `1.3722%`
- `2016-03-13`: `1.3287%`
- `2016-03-14`: `1.5796%`
- `2016-03-15`: `1.3941%`
- `2016-03-16`: `1.6737%`

Hourly anomaly behavior:

- anomalies occur only during `01:00` to `12:59`
- `00:00` and `13:00` to `23:59` contain `0` anomalous rows
- the highest hourly anomaly rate is at `10:00` with `3.6122%`
- the full `01-12` hour block contains all `1,262,427` anomalous rows

Implication:

- time-of-day is a strong behavioral signal in this dataset
- a random row split would let the model exploit this shortcut too easily
- evaluation should prefer date-based or time-block-aware splits

## Path-Level Concentration

Path concentration summary:

- total distinct paths: `100`
- paths with zero anomalous rows: `56`
- paths with `100%` anomaly rate: `1`
- paths with at least `95%` anomaly rate: `2`

Most important path findings:

- `/usr/lib/firefox/firefox`: `245,658` events, `245,658` anomalies, `100.0%` anomaly rate
- `/usr/lib/libreoffice/program/soffice.bin`: `389,492` events, `387,730` anomalies, `99.5476%` anomaly rate
- these two paths together account for `50.1722%` of all anomalous host-log rows

High-volume mostly-normal paths:

- `/usr/bin/compiz`: `37,932,630` events, `0.6961%` anomaly rate
- `/usr/sbin/apache2`: `28,553,107` events, `0.6679%` anomaly rate
- `/usr/bin/Xorg`: `16,018,854` events, `0.6931%` anomaly rate

Implication:

- `path` is one of the strongest behavioral signals in the dataset
- path rarity and path-specific anomaly propensity are likely useful derived features
- raw path identity is still valid as an input, but results should be interpreted carefully because a few executables are near-deterministic anomaly carriers

## Syscall And Interaction Signals

High-volume syscall findings:

- highest anomaly rates among syscalls with at least `100,000` events:
  - `sys_call = 191`: `2.9598%`
  - `sys_call = 221`: `2.8715%`
  - `sys_call = 4`: `2.3570%`
- the largest-volume syscalls are much closer to the global anomaly rate:
  - `265`: `1.3825%`
  - `78`: `1.3727%`
  - `102`: `1.4194%`

Path and syscall interaction findings:

- several `firefox` and `soffice.bin` path-syscall combinations are effectively deterministic anomalies
- examples:
  - `/usr/lib/firefox/firefox` with `sys_call` `265`, `78`, or `102`: `100.0%` anomaly rate
  - `/usr/lib/libreoffice/program/soffice.bin` with `sys_call` `256` or `54`: `100.0%` anomaly rate
  - `/usr/lib/libreoffice/program/soffice.bin` with `sys_call` `265`: `99.9151%` anomaly rate

Implication:

- `path x sys_call` interactions are likely more informative than `sys_call` alone
- frequency and rarity features should be built at both the single-column and interaction level

## Process Id Notes

- `pro_id` is high-cardinality and concentrated: the top process ids each span only a few paths
- high-anomaly `pro_id` values exist, but their meaning is likely instance-level rather than semantic
- raw `pro_id` should not be treated as a stable categorical identity without additional context

Implication:

- prefer `pro_id`-based aggregate features such as event counts, active duration, syscall diversity, and path diversity over raw id memorization

## Phase 4 Conclusion

What is now verified:

- anomalies are strongly concentrated in a limited time window
- anomaly behavior is highly uneven across executable paths
- a small number of paths and path-syscall pairs account for a disproportionate share of anomalies
- `sys_call` alone has signal, but interaction features are stronger

Feature guidance:

- keep as candidate raw inputs:
  - `path`
  - `sys_call`
  - timestamp-derived fields from `date` and `time`
- prioritize derived features:
  - hour-of-day and coarse time-block features
  - path frequency and path rarity
  - syscall frequency and syscall rarity
  - `path x sys_call` frequency and rarity
  - per-`pro_id` event count, syscall diversity, and path diversity
- continue to exclude:
  - `attack_cat`
  - `attack_subcat`
  - `label`

What should happen next:

- formalize a leakage-safe feature shortlist
- decide the train/validation/test split strategy with time awareness
- build the first modeling table from `host_logs.parquet` only

## Phase 5

Date: 2026-05-18

Scope:

- choose a time-aware train/validation/test split
- convert EDA results into a leakage-safe feature shortlist
- define which columns are inputs, derived features, metadata, or exclusions

## Recommended Split Strategy

Recommended chronological split:

- train: `2016-03-11` to `2016-03-14`
- validation: `2016-03-15`
- test: `2016-03-16`

Recommended split summary:

- train: `67,912,243` rows, `926,830` anomalies, `1.3647%` anomaly rate
- validation: `12,515,902` rows, `174,488` anomalies, `1.3941%` anomaly rate
- test: `9,626,094` rows, `161,109` anomalies, `1.6737%` anomaly rate

Why this split is preferred:

- it is fully chronological
- every split contains a substantial number of anomalies
- it gives the model the longest possible history before validation and test
- it reduces entity drift compared with earlier train cutoffs

## Holdout Coverage Relative To Training

Validation and test coverage against the recommended training window:

- anomalous rows on unseen `path`: `0` in validation, `0` in test
- anomalous rows on unseen `sys_call`: `0` in validation, `0` in test
- anomalous rows on unseen `path x sys_call`: `4` in validation (`0.0023%`), `0` in test
- anomalous rows on unseen `pro_id`: `4,377` in validation (`2.5085%`), `4,689` in test (`2.9105%`)

Interpretation:

- `path`, `sys_call`, and `path x sys_call` generalize cleanly across the chronological split
- `pro_id` changes more across dates and should be treated as an unstable execution-instance identifier
- this supports a baseline that uses raw `path` and `sys_call`, but not raw `pro_id` as a categorical identity

## Modeling-Ready Column Roles

Use as baseline raw inputs:

- `path`
- `sys_call`
- `time` only through derived features

Use for derived features only:

- `pro_id`
- `date`

Keep as metadata only:

- `date`
- `time`

Exclude from baseline modeling:

- `attack_cat`
- `attack_subcat`
- `label` as a target only, never a feature
- `event_id`
- `ground_truth` fields from `ground_truth.parquet`
- raw `pro_id` as a categorical feature
- raw `date` as a default feature in the first baseline

Exclusion reasoning:

- `attack_cat` and `attack_subcat` are direct leakage channels
- `event_id` is near-unique and behaves like an identifier
- raw `pro_id` has poor temporal stability across splits
- raw `date` would let the model exploit campaign progression instead of behavior

## Baseline Feature Shortlist

Safe first-pass temporal features:

- `hour`
- `minute`
- `seconds_since_midnight`
- `hour_block` such as `01-12` vs other hours

Safe first-pass frequency features learned on the training split only:

- `path_train_count`
- `path_train_relative_freq`
- `sys_call_train_count`
- `sys_call_train_relative_freq`
- `path_sys_call_train_count`
- `path_sys_call_train_relative_freq`
- `pro_id_train_count`
- `pro_id_train_distinct_path_count`
- `pro_id_train_distinct_sys_call_count`

Useful binary rarity flags:

- `is_rare_path`
- `is_rare_sys_call`
- `is_rare_path_sys_call`
- `is_low_history_pro_id`

Implementation rule:

- fit all count, frequency, and rarity lookups on the training split only
- join those learned statistics into validation and test
- map unseen holdout values to a neutral default such as `0` or `unknown`

## Baseline Modeling Direction

Recommended first baseline:

- build the modeling table from `host_logs.parquet` only
- predict `label`
- start with row-level features plus train-derived frequency statistics
- keep the baseline chronological and avoid random row splits

Suggested first comparison:

- a simple tree baseline on train-derived numeric features
- a categorical-aware baseline that can use `path` and `sys_call` directly

## Phase 5 Conclusion

What is now decided:

- the default evaluation split should be chronological: train `2016-03-11` to `2016-03-14`, validation `2016-03-15`, test `2016-03-16`
- `host_logs.parquet` is sufficient to build the first modeling table
- the first baseline should depend on `path`, `sys_call`, time-derived features, and train-derived frequency statistics

What should happen next:

- build the first modeling table from `host_logs.parquet`
- materialize train-derived feature statistics and join them into validation and test
- train a simple baseline before moving to XAI

## Phase 6

Date: 2026-05-18

Scope:

- package the prior EDA results into a compact visualization set
- make the notebook suitable for reporting and review before baseline modeling starts

## Visualization Pack

The visualization pack is now implemented in [Anomaly_Detection.ipynb](/Users/harrish/Desktop/practicum/anomaly-detection-xai/notebook/Anomaly_Detection.ipynb:1).

Included outputs:

- schema summary table for `host_logs.parquet` and `ground_truth.parquet`
- null-rate table for both datasets
- host-log class balance chart
- daily event volume and anomaly volume chart
- hourly anomaly rate chart
- top paths by anomaly count chart
- anomaly rate by high-volume path chart
- anomaly rate by high-volume `pro_id` chart
- distinct-count summary chart for key host-log columns

Purpose:

- give a compact visual summary of the earlier phase results
- make the main data-quality and behavioral patterns easy to review without reading every query table
- provide a notebook-ready reporting layer before model training begins

## Phase 6 Conclusion

What is now true:

- the EDA plan in [eda.md](/Users/harrish/Desktop/practicum/anomaly-detection-xai/docs/eda.md:1) is complete through Phase 6
- the notebook now contains both the analytical sections and the reporting visuals
- the repo is ready to move from EDA into baseline model training

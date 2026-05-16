# EDA Findings

## Iteration 1

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

- Rows with `time = 'Time'`: `35,926`

Example embedded header row:

- `2016-03-11`, `Time`, `Malware`, `Mobile Batch`, `Strike Name`, `Strike Reference`, `Strike Tuples`

Impact:

- `time` cannot yet be treated as a clean time column
- Categorical counts in `ground_truth.parquet` are currently inflated by repeated header rows
- Iteration 2 needs to explicitly remove or isolate these rows before quality profiling

## Cross-Dataset Observations

- `host_logs.parquet` already contains attack family and scenario labels inside the table
- `ground_truth.parquet` appears to contain attack metadata and network tuple annotations
- The exact relationship between host-log rows and ground-truth rows is still unresolved
- That mapping should be treated as an Iteration 3 question, not assumed now

## Ambiguities Still Open

### `host_logs.parquet`

- The parquet file now uses the official NGIDS field names
- `sys_call` and `event_id` align with the public feature description, but they should still be validated against downstream usage
- `attack_cat` and `attack_subcat` are labels, not safe default features

### `ground_truth.parquet`

- `time` is not a clean time field because of embedded header rows
- Some category values include leading spaces such as ` Exploits` and ` Denial of Service`
- The intended join key or alignment rule between `ground_truth.parquet` and `host_logs.parquet` is not yet known

## Iteration 1 Conclusion

What is now verified:

- Both parquet files are queryable with DuckDB
- `host_logs.parquet` is the main large event table with `90M+` rows
- `ground_truth.parquet` is a smaller attack-metadata table with `313k+` rows
- Both parquet files now use the official NGIDS column names
- `host_logs.parquet` includes direct binary and categorical label-like fields
- `ground_truth.parquet` has a real quality issue due to repeated header rows

What should happen next:

- Iteration 2 should focus on data quality profiling
- The first quality fix to validate is the removal or filtering of header-like rows in `ground_truth.parquet`
- Leakage-prone host log columns should already be flagged before any feature design starts

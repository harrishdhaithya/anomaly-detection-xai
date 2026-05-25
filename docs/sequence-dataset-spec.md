# Sequence Dataset Specification

Date: 2026-05-18

## Purpose

This document freezes the first trainable sequence dataset design for the NGIDS `host_logs.parquet` workflow.

It is based on the completed sequence EDA in:

- [sequential-eda.md](/Users/harrish/Desktop/practicum/anomaly-detection-xai/docs/sequential-eda.md:1)
- [sequential-eda-findings.md](/Users/harrish/Desktop/practicum/anomaly-detection-xai/docs/sequential-eda-findings.md:1)

## Source Table

- primary source: `host_logs.parquet`
- supporting lookup: [syscall-lookup-linux-v3_13.csv](/Users/harrish/Desktop/practicum/anomaly-detection-xai/dataset/syscall-lookup-linux-v3_13.csv:1)

`ground_truth.parquet` is not part of the first sequence dataset build.

## Preprocessing

Apply these steps before window construction:

1. Drop exact duplicate full rows.
2. Map `sys_call` through the `i386`-preferred lookup in `syscall-lookup-linux-v3_13.csv`.
3. Keep the alternative `x86_64` column only for audit, not for the main model input.
4. Do not use `attack_cat`, `attack_subcat`, or `label` as input features.

## Split Rule

Split before sequence fragmentation:

- train: `2016-03-11` to `2016-03-14`
- validation: `2016-03-15`
- test: `2016-03-16`

Do not allow sequence windows to cross split boundaries.

## Sequence Identity

Use:

- `(pro_id, path)`

Do not use raw `pro_id` alone as the sequence key.

Rationale:

- `pro_id` mixes multiple executable contexts too often.
- `(pro_id, path)` preserves local behavioral coherence while keeping `path` out of the feature set itself.

## Event Order

Sort each sequence by:

- `(date, time, event_id)`

`event_id` is used only as an ordering field.

## Windowing Policy

### Baseline window

- window length: `64`
- stride: `32`

### Comparison window

- window length: `32`
- stride: `16`

### Optional low-redundancy comparison

- window length: `64`
- stride: `64`

## Window Support

Empirical support after split truncation:

| Split | Sequence Fragments | Total Rows | Windows `64/32` | Windows `64/64` | Windows `32/16` |
| --- | ---: | ---: | ---: | ---: | ---: |
| train | `5,097` | `67,912,243` | `2,118,140` | `1,059,449` | `4,239,310` |
| validation | `1,753` | `12,515,902` | `389,634` | `194,933` | `780,364` |
| test | `1,548` | `9,626,094` | `299,477` | `149,851` | `599,950` |

Support notes:

- `64/32` is the default baseline.
- `32/16` is a useful ablation, not the primary default.
- Fragments shorter than the window length are dropped for that window configuration.

## Labeling Rule

For the first sequence model:

- window label = `1` if any event in the window has `label = 1`
- window label = `0` otherwise

Also retain per-event labels inside each window for later experiments.

Rationale:

- anomalies are mostly contiguous runs, not isolated single points
- window-level labeling is a cleaner first baseline than full sequence-to-sequence prediction

## Event Representation

### Core categorical token

- `sys_call` mapped through the `i386`-preferred lookup

Recommended stored form:

- integer syscall id
- lookup-backed syscall name in metadata only

### Coarse categorical token

- `preferred_family`

Available families:

- `file_io_fs`
- `memory`
- `network_socket`
- `other`
- `permissions_identity`
- `process_thread`
- `signal_ipc`
- `time_timer`

### Timing feature

Use inter-event delta inside each `(pro_id, path)` split fragment:

- `delta_seconds = datediff(second, previous_event_ts, current_event_ts)`

Encoding rule:

- store raw non-negative `delta_seconds`
- derive `delta_seconds_log1p_clipped = log1p(min(delta_seconds, 300))`

Reason:

- zero-second gaps dominate:
  - train: `97.5644%`
  - validation: `96.4323%`
  - test: `96.1506%`
- 99th percentile gap:
  - train: `1` second
  - validation: `4` seconds
  - test: `4` seconds
- the tail is extremely long, so clipping plus `log1p` is safer than raw scale

## Excluded Features

Do not include these in the first transferable sequence model:

- raw `path`
- raw `pro_id`
- `event_id`
- raw `date`
- raw absolute `time`
- `attack_cat`
- `attack_subcat`

Why:

- `path` and `time-of-day` are strong shortcut signals in this dataset
- the goal is behavior transfer across applications

## Output Format

The first sequence dataset builder should produce one split file per window configuration.

Recommended row format:

- one row per `(window_id, position)`

Required columns:

- `split_name`
- `sequence_id`
- `window_id`
- `window_index_within_sequence`
- `position`
- `window_label`
- `event_label`
- `sys_call`
- `syscall_family`
- `delta_seconds`
- `delta_seconds_log1p_clipped`

Optional metadata columns:

- `sequence_start_date`
- `sequence_end_date`
- `window_start_ts`
- `window_end_ts`
- `path` as an audit-only field in a separate metadata table, not as model input

## Padding And Truncation

For the first baseline:

- use fixed-length windows only
- no sequence padding is needed at dataset-build time
- drop incomplete trailing fragments that cannot form a full window

If a later model consumes full variable-length fragments, use right-padding with an explicit mask.

## Training Policy

Recommended first training setup:

- primary dataset: `64/32`
- comparison dataset: `32/16`
- class-weighted loss or negative-window downsampling

Reason:

- anomaly rows are sparse overall
- positive signal is concentrated in a relatively small number of long fragments

## Evaluation Policy

Keep two evaluation modes:

1. chronological evaluation
   - train / validation / test as defined above
2. held-out application evaluation
   - remove one major anomaly path from training
   - score on its later-day windows

Recommended first held-out paths:

- `/usr/lib/libreoffice/program/soffice.bin`
- `/usr/lib/firefox/firefox`
- `/usr/sbin/apache2`

## Baseline Model Shortlist

Start with:

1. GRU classifier
2. LSTM classifier

Recommended first input variants:

1. exact syscall id only
2. syscall id + family id
3. syscall id + family id + delta-time feature

## Done Definition

The sequence dataset is considered implementation-ready when:

- duplicate removal is frozen
- split logic is frozen
- ordering rule is frozen
- `(pro_id, path)` boundary is frozen
- `64/32` baseline windowing is frozen
- label rule is frozen
- event representation is frozen
- output schema is frozen

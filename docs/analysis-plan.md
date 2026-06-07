# Analysis Plan

Date: June 6, 2026

## Purpose

This document lists the remaining analysis needed before finalizing feature engineering, LSTM training, explainability comparison, and user-centric validation.

The goal is not to keep expanding EDA indefinitely. The goal is to perform only the analysis required to make the modeling and XAI stages defensible.

## Current Position

Completed or mostly completed:

- Host-log schema and row-count checks
- Basic anomaly-label distribution
- Ground-truth quality inspection
- Syscall lookup setup
- Initial sequence-modeling direction
- Initial LSTM feature pipeline

Main dataset for modeling:

- `dataset/host_logs.parquet`

Supporting files:

- `dataset/ground_truth.parquet`
- `dataset/syscall-lookup-linux-v3_13.csv`

## Analysis 1: Single Attack Extraction

Question:

- Can a selected attack from `ground_truth.parquet` be approximately located inside `host_logs.parquet`?

Why this matters:

- This helps create concrete case studies for the paper and later XAI examples.
- XAI outputs are easier to explain when tied to a specific attack instance.

Tasks:

- Select a clean `ground_truth` row with valid `date`, `time`, `attack_cat`, `attack_subcat`, and `attack_name`.
- Extract host-log rows at the exact timestamp.
- Extract host-log rows in time windows around the attack, for example:
  - `±10 seconds`
  - `±30 seconds`
  - `±60 seconds`
- Compare how many rows are anomalous inside each window.
- Map `sys_call` to syscall names/families for the extracted rows.

Deliverable:

- One or two attack case studies with host-log context.

Decision:

- Use these case studies later for XAI demonstration.

## Analysis 2: Ground Truth Alignment Check

Question:

- How reliable is `ground_truth.parquet` for locating attacks in `host_logs.parquet`?

Why this matters:

- The model target comes from `host_logs.label`, not from `ground_truth`.
- The paper should clearly state whether `ground_truth` is used for training or only for interpretation.

Tasks:

- Filter corrupted `ground_truth` rows.
- Count exact matches between ground-truth events and host-log anomalies using:
  - `date`
  - `time`
  - `attack_cat`
  - `attack_subcat`
- Count broader timestamp-only matches.
- Check whether some attack categories align better than others.

Deliverable:

- A small table showing exact-match and timestamp-match coverage.

Decision:

- Keep `ground_truth` as supporting metadata unless alignment is strong enough for direct training use.

## Analysis 3: Sequence Boundary Validation

Question:

- Is `(pro_id, path)` still the best practical sequence boundary for LSTM training?

Why this matters:

- LSTM performance depends heavily on how sequences are constructed.
- A bad sequence boundary can mix unrelated behavior and weaken temporal learning.

Tasks:

- Compare sequence lengths for:
  - `pro_id`
  - `(pro_id, path)`
- Check how often `pro_id` maps to multiple paths.
- Check how many `(pro_id, path)` streams are long enough for window sizes:
  - `32`
  - `64`
  - `128`
- Confirm that windows do not cross date split boundaries.

Deliverable:

- One table comparing candidate sequence boundaries.

Decision:

- Freeze the first LSTM boundary.

## Analysis 4: Window Label Quality

Question:

- Does the window-label rule produce meaningful positive and negative examples?

Current rule:

- A window is anomalous if any event inside the window has `label = 1`.

Why this matters:

- If positive windows contain only one anomalous event and mostly normal events, the label may be noisy.
- If positive windows mostly contain anomaly runs, the label is more reliable.

Tasks:

- For each window size, measure:
  - number of positive windows
  - number of negative windows
  - average anomaly count per positive window
  - percentage of positive windows with only one anomalous event
- Compare:
  - window length `32`
  - window length `64`
  - optional window length `128`

Deliverable:

- A table supporting the selected window size.

Decision:

- Freeze the first LSTM window length and stride.

## Analysis 5: Feature Readiness Check

Question:

- Are the planned LSTM features valid, non-leaky, and available across train, validation, and test?

Planned input features:

- syscall token
- syscall family token
- clipped `log1p(delta_time)`

Excluded from model input:

- raw `path`
- raw `pro_id`
- `event_id`
- raw `date`
- raw `time`
- `attack_cat`
- `attack_subcat`
- `label`

Tasks:

- Check unknown syscall rate in validation and test compared with training vocabulary.
- Check unknown syscall-family rate.
- Check distribution of `delta_time` before and after clipping.
- Confirm that no leakage fields are written into model input arrays.

Deliverable:

- Feature-readiness table.

Decision:

- Freeze the LSTM feature set.

## Analysis 6: Class Distribution At Window Level

Question:

- What is the anomaly distribution after converting event rows into windows?

Why this matters:

- Row-level imbalance and window-level imbalance can be different.
- Training sampling should be based on window-level imbalance.

Tasks:

- Count positive and negative windows before sampling.
- Count positive and negative windows after sampling.
- Compare train, validation, and test distributions.
- Decide whether validation and test should remain closer to natural distribution.

Deliverable:

- Window-level class balance table.

Decision:

- Freeze negative sampling ratio for training.

## Analysis 7: First LSTM Baseline Evaluation

Question:

- Does the first LSTM learn useful sequence patterns from engineered features?

Tasks:

- Train the first LSTM baseline.
- Report:
  - precision
  - recall
  - F1 score
  - ROC-AUC
  - PR-AUC
  - inference time
- Tune threshold on validation data.
- Evaluate once on test data.

Deliverable:

- First model result table.

Decision:

- Decide whether to keep LSTM as the primary model or compare with CNN-LSTM.

## Analysis 8: XAI Candidate Selection

Question:

- Which explainability methods are realistic and relevant for the trained sequence model?

Candidate methods:

- Integrated Gradients
- Occlusion or perturbation attribution
- SHAP
- LIME

Tasks:

- Check which methods can explain sequence windows.
- Check runtime for each method on a small sample.
- Check whether explanations can be shown at:
  - syscall level
  - syscall-family level
  - timestep level
- Choose methods for full comparison.

Deliverable:

- XAI shortlist with feasibility notes.

Decision:

- Freeze the XAI methods for implementation.

## Analysis 9: User-Centric Validation Preparation

Question:

- What should users evaluate, and how should explanation quality be measured?

Tasks:

- Choose representative anomaly windows.
- Generate explanations from the selected XAI methods.
- Prepare a small questionnaire around:
  - clarity
  - usefulness
  - trust
  - actionability
  - preference
- Decide participant profile and target count.

Deliverable:

- User-evaluation material pack.

Decision:

- Freeze validation design before sending questionnaires.

## Minimum Analysis Required Before Training

Before LSTM training, complete:

1. Sequence boundary validation
2. Window label quality
3. Feature readiness check
4. Window-level class distribution

## Minimum Analysis Required Before XAI

Before XAI comparison, complete:

1. First LSTM baseline evaluation
2. Single attack extraction
3. XAI candidate selection

## Minimum Analysis Required Before User Validation

Before user-centric validation, complete:

1. Final model selection
2. Final XAI method selection
3. Representative case-study selection
4. Questionnaire preparation

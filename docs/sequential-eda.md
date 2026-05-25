# Sequential EDA Plan

## Goal

Determine whether `host_logs.parquet` supports a sequence model that learns transferable exploit behavior across applications rather than memorizing executable paths.

This plan starts after the general EDA in [eda.md](/Users/harrish/Desktop/practicum/anomaly-detection-xai/docs/eda.md:1) and focuses on sequence construction, order signal, and path-transfer risk.

## Main Questions

1. What should count as one sequence?
2. Is the event ordering reliable enough for sequence modeling?
3. Are anomalous events isolated points or contiguous behavioral runs?
4. Does syscall order add signal beyond static shortcuts like `path` and hour-of-day?
5. Can the learned behavior plausibly transfer across applications?

## Working Assumptions

- Use `host_logs.parquet` as the primary modeling source.
- Treat `ground_truth.parquet` as supporting metadata unless a stronger event-level alignment is discovered later.
- Keep the chronological split from the general EDA:
  - train: `2016-03-11` to `2016-03-14`
  - validation: `2016-03-15`
  - test: `2016-03-16`
- Treat Linux `x86_64` syscall mapping as the default working assumption unless contradicted by stronger host metadata.
- Avoid designing the sequence model around raw `path` memorization.

## Phase S1: Ordering Reliability

Objective: verify whether the event stream can be ordered consistently enough to justify sequence modeling.

Tasks:

- Check whether `date + time` is sufficient to sort events inside a candidate sequence.
- Test whether `event_id` can serve as a stable tie-breaker within equal timestamps.
- Measure how often multiple rows share the same `date`, `time`, `pro_id`, and `path`.
- Check whether `event_id` is monotonic within likely local process streams.
- Quantify ambiguous ordering cases that would weaken sequence assumptions.

Outputs:

- Recommended event sort key
- Short note on ordering ambiguity and its practical impact

## Phase S2: Sequence Boundary Definition

Objective: choose the sequence unit before training any sequential model.

Candidate boundary options:

- per `pro_id`
- per `(pro_id, path)`
- fixed rolling windows over the global event stream
- fixed rolling windows within `pro_id`

Tasks:

- Compute sequence-length distributions for each boundary choice.
- Measure how many sequences are too short for candidate window sizes such as `16`, `32`, `64`, and `128`.
- Check how often `pro_id` changes path over time.
- Measure how often candidate sequences cross train/validation/test date boundaries.
- Compare how much path identity leakage each boundary choice introduces.

Outputs:

- Recommended sequence boundary definition
- Candidate window lengths with empirical support

## Phase S3: Label Locality And Run Structure

Objective: understand how anomaly labels are distributed inside candidate sequences.

Tasks:

- Measure contiguous run lengths of `label = 1`.
- Measure gap lengths between anomalous events within the same candidate sequence.
- Quantify how often a sequence contains:
  - only normal events
  - only anomalous events
  - mixed normal and anomalous events
- Decide whether a sequence label should mean:
  - any anomalous event in the window
  - majority anomalous events
  - per-event prediction within the window
- Inspect pre-anomaly and post-anomaly context windows.

Outputs:

- Recommended sequence-labeling rule
- Evidence on how much context before and after an anomaly is likely useful

## Phase S4: Syscall Mapping And Transition Analysis

Objective: test whether syscall order contains transferable behavioral signal.

Tasks:

- Map `sys_call` ids to Linux `x86_64` syscall names.
- Optionally group mapped syscalls into coarse families:
  - file I/O
  - process/thread
  - memory
  - network/socket
  - permissions
  - IPC/signals
- Compare normal vs anomalous syscall frequency distributions.
- Measure top syscall transitions:
  - `sys_call_t -> sys_call_t+1`
- Measure short motifs:
  - bigrams
  - trigrams
- Compare transition and motif differences across applications.

Outputs:

- Syscall lookup table
- Transition summary for normal vs anomalous behavior
- Initial evidence for or against cross-application behavioral similarity

## Phase S5: Order Importance And Transfer Risk

Objective: determine whether a sequence model is actually justified.

Tasks:

- Compare ordered sequence statistics against bag-of-events statistics.
- Run a simple order-destruction sanity check:
  - shuffle event order within candidate sequences
  - compare how much sequence-level structure disappears in summary features
- Check whether anomaly-associated transitions repeat across different paths.
- Design a held-out application/path evaluation:
  - remove selected paths from training
  - inspect whether anomalous syscall patterns still appear in holdout paths

Outputs:

- Clear statement on whether order appears to add signal beyond static features
- Evaluation protocol for cross-application transfer

## Phase S6: Modeling-Ready Sequence Specification

Objective: translate the sequence EDA into a trainable sequence dataset design.

Tasks:

- Freeze the event sort key.
- Freeze the sequence boundary choice.
- Freeze candidate window sizes.
- Define the event representation:
  - raw syscall id or mapped syscall name
  - optional syscall family
  - delta-time features
  - optional limited context features
- Define padding, truncation, and overlap policy.
- Define how split boundaries truncate or exclude sequences.
- Decide which non-sequential features, if any, remain acceptable.

Outputs:

- Sequence dataset specification ready for implementation
- Shortlist of baseline sequence models such as GRU or LSTM

## Recommended Order

1. Validate ordering reliability
2. Choose the sequence boundary
3. Analyze label locality and run structure
4. Map syscalls and study transitions
5. Test order importance and transfer risk
6. Freeze the modeling-ready sequence specification

## Suggested Deliverables

- This plan in `docs/sequential-eda.md`
- New notebook section or notebook copy dedicated to sequence analysis
- A follow-up findings document or appended section in `docs/eda-findings.md`
- A syscall lookup artifact if mapping is validated

## Done Criteria

The sequence-specific EDA is complete when:

- a reliable event ordering rule is documented
- a sequence boundary definition is chosen and defended
- a sequence-labeling rule is chosen and defended
- syscall mapping and transition summaries are available
- order importance has been tested against static shortcuts
- a held-out application/path evaluation protocol is defined
- the sequence dataset specification is ready for implementation

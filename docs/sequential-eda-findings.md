# Sequential EDA Findings

## Phase S1

Date: 2026-05-18

Question:

- Can the host-log events be ordered reliably enough to justify sequence modeling?

Key results:

- `date + time` is not a usable standalone sort key.
- Global timestamp collisions are pervasive:
  - distinct `(date, time)` keys: `367,290`
  - collided keys: `364,816` (`99.3264%`)
  - median rows per timestamp: `216`
  - 90th percentile: `397`
  - 99th percentile: `684`
  - maximum rows at one timestamp: `2,257`
- Even after adding process context, timestamp collisions remain pervasive:
  - distinct `(date, time, pro_id)` keys: `2,476,943`
  - collided keys: `2,454,121` (`99.0786%`)
  - median rows per key: `33`
  - 90th percentile: `96`
  - 99th percentile: `198`
  - maximum rows at one key: `1,880`
- Adding `path` does not solve the ordering problem:
  - distinct `(date, time, pro_id, path)` keys: `2,479,314`
  - collided keys: `2,456,410` (`99.0762%`)
  - median rows per key: `33`
  - 90th percentile: `96`
  - 99th percentile: `198`
  - maximum rows at one key: `1,880`
- `event_id` behaves like a strong local tie-breaker inside `pro_id` streams:
  - comparable row transitions: `90,048,663`
  - `event_id` increases: `89,704,363` (`99.6177%`)
  - `event_id` ties: `344,298` (`0.3823%`)
  - `event_id` decreases: `2`
- Repeated `event_id` values are rare and shallow:
  - distinct `event_id` values: `89,709,941`
  - repeated `event_id` values: `344,298`
  - maximum multiplicity per `event_id`: `2`
- The repeated `event_id` count exactly matches the repeated `(date, time, pro_id, event_id)` key count, which is consistent with duplicate rows rather than true ordering ambiguity.
- The only two observed `event_id` reversals are both normal-labeled `/usr/sbin/cron` rows one second apart, so they are negligible edge cases rather than a systemic failure mode.

Recommendation:

- Drop exact duplicate full rows before building sequences.
- Sort each candidate sequence by `(date, time, event_id)`.
- Treat `event_id` as an ordering field only, not as a predictive model feature.

Practical impact:

- Sequence modeling is still viable.
- The dataset does not support sequence construction from second-level timestamps alone.

## Phase S2

Date: 2026-05-18

Question:

- What should count as one sequence?

Boundary comparison:

### `pro_id`

- sequence count: `5,576`
- average sequence length: `16,150.3298`
- median / 90th / 99th percentile length: `47 / 165 / 8,794`
- maximum sequence length: `37,334,049`
- sequences with length `>= 32`: `4,085` (`73.2604%`)
- sequences with length `>= 64`: `1,905` (`34.1643%`)
- sequences with length `>= 128`: `1,064`
- sequences spanning multiple paths: `2,448` (`43.9024%`)
- rows inside multi-path sequences: `89,757,158` (`99.6701%` of all rows)
- 90th percentile distinct paths per `pro_id`: `2`
- 99th percentile distinct paths per `pro_id`: `3`
- sequences crossing train -> validation: `88`
- sequences crossing validation -> test: `66`

Interpretation:

- `pro_id` alone is too coarse as the primary sequence identity.
- The path-switch statistics show that the same `pro_id` often mixes unrelated executable contexts.
- This is likely a combination of PID reuse and multi-day process identity ambiguity.

### `(pro_id, path)`

- sequence count: `8,122`
- average sequence length: `11,087.6926`
- median / 90th / 99th percentile length: `34 / 164 / 5,416`
- maximum sequence length: `37,076,124`
- sequences with length `>= 32`: `4,404` (`54.2231%`)
- sequences with length `>= 64`: `2,002` (`24.6491%`)
- sequences with length `>= 128`: `1,139`
- rows inside sequences with length `>= 64`: `89,929,712` (`99.8617%`)
- rows inside sequences with length `>= 128`: `89,861,845` (`99.7864%`)
- sequences spanning multiple dates: `185`
- sequences crossing train -> validation: `154`
- sequences crossing validation -> test: `124`

Interpretation:

- `(pro_id, path)` is a cleaner baseline sequence identity than `pro_id`.
- It keeps executable context stable without forcing raw `path` to become a model feature.
- The long-tail coverage is still strong enough for rolling windows even though many short sequences remain.

Examples that support the boundary choice:

- Some `pro_id` streams mix up to `5` distinct paths.
- High-volume mixed examples include combinations such as:
  - `/usr/lib/firefox/firefox`
  - `/usr/lib/libreoffice/program/soffice.bin`
  - `/usr/sbin/apache2`
  - `/usr/bin/python3.4`
  - `/usr/bin/update-notifier`

Recommendation:

- Use `(pro_id, path)` as the baseline sequence boundary for the first sequential model.
- Keep the chronological split, but truncate sequences at split boundaries instead of allowing windows to span train, validation, and test.
- Start with candidate window sizes `32` and `64`.
- Treat `128` as a comparison window, not the default baseline.

Practical impact:

- The sequence model can be made more behavior-focused and less dependent on application identity.
- The boundary choice is now concrete enough to proceed to Phase S3 label-locality analysis.

## Phase S3

Date: 2026-05-18

Question:

- Are anomalies isolated points or local behavioral runs inside `(pro_id, path)` sequences?

Sequence composition:

- total `(pro_id, path)` sequences: `8,122`
- normal-only sequences: `7,759` (`95.5307%`)
- anomaly-only sequences: `226` (`2.7826%`)
- mixed sequences: `137` (`1.6868%`)
- rows in normal-only sequences: `722,224` (`0.8020%` of all rows)
- rows in anomaly-only sequences: `634,172` (`0.7042%` of all rows)
- rows in mixed sequences: `88,697,843` (`98.4938%` of all rows)

Interpretation:

- Most sequence instances are normal-only.
- Most rows live inside a small set of very large mixed sequences.
- This means the main sequential task is not detecting isolated anomalous streams, but detecting anomalous stretches inside long-running process streams.

Anomaly-run behavior:

- anomaly run count: `17,035`
- average anomaly run length: `74.1078` rows
- single-event runs: `171` (`1.0038%`)
- multi-event runs: `16,864` (`98.9962%`)
- consecutive anomaly pairs with zero normal-gap rows between them: `1,245,392 / 1,262,064` (`98.6790%`)
- median / 90th / 99th percentile gap between consecutive anomalous rows: `0 / 0 / 308`

Interpretation:

- Anomalies are overwhelmingly contiguous rather than isolated.
- Single anomalous events are rare.
- The dominant pattern is a burst or run of anomalous rows once a sequence enters anomalous behavior.

Mixed-sequence anomaly share:

- mixed sequence count: `137`
- median anomaly share inside mixed sequences: `2.3132%`
- 90th percentile anomaly share: `78.7440%`
- 99th percentile anomaly share: `96.1039%`

Interpretation:

- Mixed sequences split into two regimes:
  - large streams with sparse anomalous bursts
  - shorter streams that become mostly anomalous once the attack starts

Recommendation:

- Use a sequence-labeling rule based on local windows rather than whole-sequence labels.
- For the first sequence model, treat a window as anomalous if it contains any `label = 1` event.
- Keep candidate window lengths `32` and `64`, because anomalies usually arrive in contiguous runs rather than single-event spikes.

Practical impact:

- A sequence model is justified by the label-locality structure.
- Sequence-to-sequence or window-level classification is more defensible than assigning one label to an entire `(pro_id, path)` stream.

## Phase S4

Date: 2026-05-18

Question:

- Do the syscall ids support an interpretable transition analysis, and does syscall order appear to contain transferable behavioral signal?

Lookup decision:

- I compared the observed `sys_call` values against the official Linux `v3.13` `x86_64` and `i386` syscall tables.
- The raw ids fit the `i386` table much better than the `x86_64` table.
- High-volume examples that drove this conclusion:
  - `265`: `x86_64 = linkat`, `i386 = clock_gettime`
  - `256`: `x86_64 = migrate_pages`, `i386 = epoll_wait`
  - `168`: `x86_64 = swapoff`, `i386 = poll`
  - `102`: `x86_64 = getuid`, `i386 = socketcall`
- Under `x86_64`, many of the most common ids map to implausible user-space behavior.
- Under `i386`, the same ids map to common timing, I/O, network, and event-loop syscalls that are much more believable at this scale.
- The working lookup artifact is now [syscall-lookup-linux-v3_13.csv](/Users/harrish/Desktop/practicum/anomaly-detection-xai/dataset/syscall-lookup-linux-v3_13.csv:1).
- That file also keeps the alternative `x86_64` name column for auditability.

Important caveat:

- This does not prove that the host OS itself was 32-bit.
- It does show that the recorded `sys_call` numbers behave like Linux `i386` syscall numbering, at least in the exported dataset.
- The safest interpretation is that sequence analysis should use the `i386`-preferred lookup unless stronger source metadata contradicts it later.

Syscall-level findings under the `i386`-preferred lookup:

- total mapped syscall ids: `122`
- top anomaly-rate syscalls among ids with at least `100,000` events:
  - `ugetrlimit`: `2.9598%`
  - `fcntl64`: `2.8715%`
  - `write`: `2.3570%`
  - `read`: `1.6039%`
  - `close`: `1.4947%`
- largest anomaly contributors:
  - `clock_gettime`: `353,659` anomalous rows (`28.0142%` of all anomalous rows)
  - `gettimeofday`: `297,819` (`23.5910%`)
  - `socketcall`: `160,310` (`12.6986%`)
  - `epoll_wait`: `97,402` (`7.7155%`)
  - `ioctl`: `76,927` (`6.0936%`)

Interpretation:

- Timing, event-loop, socket, and file-I/O behavior dominate the anomaly mass.
- This is a much more coherent behavioral picture than the earlier `x86_64`-name interpretation.

Transition findings:

- highest anomaly-rate transitions with at least `10,000` rows:
  - `ugetrlimit -> fcntl64`: `2.9607%`
  - `fcntl64 -> ugetrlimit`: `2.9579%`
  - `gettimeofday -> getcwd`: `2.6835%`
  - `socketcall -> read`: `2.6220%`
  - `read -> socketcall`: `2.6115%`
  - `clock_gettime -> epoll_wait`: `2.5243%`
  - `epoll_wait -> clock_gettime`: `2.5221%`
- these are not single-path artifacts only.
- recurrent anomalous transitions across many executables include:
  - `clock_gettime -> clock_gettime`: `22` paths
  - `poll -> clock_gettime`: `21` paths
  - `clock_gettime -> poll`: `21` paths
  - `socketcall -> poll`: `16` paths
  - `socketcall -> socketcall`: `14` paths

Interpretation:

- Order signal is present.
- Several anomalous transition motifs repeat across many application paths rather than being confined to one executable.
- That is the first concrete support for the “behavior may transfer across applications” hypothesis.

Family-level findings:

- strongest family-level anomaly-rate transitions with at least `10,000` rows:
  - `file_io_fs -> other`: `2.7325%`
  - `other -> file_io_fs`: `2.7192%`
  - `process_thread -> time_timer`: `2.4582%`
  - `signal_ipc -> network_socket`: `2.2033%`
  - `file_io_fs -> signal_ipc`: `2.1545%`
  - `signal_ipc -> time_timer`: `2.1240%`
- larger-volume recurring transitions are dominated by:
  - `network_socket -> file_io_fs`
  - `file_io_fs -> file_io_fs`
  - `network_socket -> network_socket`
  - `time_timer -> file_io_fs`

Interpretation:

- Exact syscall names are useful, but family-level transitions are likely the more robust transferable signal.
- They reduce the risk that the eventual model memorizes one application’s exact call vocabulary.

Recommendation:

- Use the `i386`-preferred lookup as the working syscall mapping for the rest of the sequence EDA.
- Keep both exact-syscall and family-transition views.
- Favor family-aware sequence features in the first transferable model design.

Practical impact:

- Sequence order now has interpretable content.
- The project can move into Phase S5 with a stronger case that behavior, not just path identity, may generalize across applications.

## Phase S5

Date: 2026-05-18

Question:

- Does order add signal beyond bag-of-events composition, and do anomalous transition motifs survive held-out application paths?

Order-destruction sanity check:

- I compared ordered transitions against deterministic within-sequence shuffles on the validation day `2016-03-15`.
- This preserves the event multiset inside each `(pro_id, path)` sequence but destroys local order.
- At the syscall-family level, several anomaly-associated transitions lose noticeable anomaly rate after shuffling:
  - `signal_ipc -> file_io_fs`: ordered `2.1956%`, shuffled `1.8086%`, lift `+0.3870`
  - `signal_ipc -> signal_ipc`: ordered `1.9033%`, shuffled `1.5485%`, lift `+0.3548`
  - `file_io_fs -> other`: ordered `2.3893%`, shuffled `2.0615%`, lift `+0.3278`
  - `file_io_fs -> network_socket`: ordered `1.7899%`, shuffled `1.5623%`, lift `+0.2276`
  - `memory -> file_io_fs`: ordered `1.8140%`, shuffled `1.6231%`, lift `+0.1909`
- Some larger high-volume families change little after shuffling, for example:
  - `time_timer -> time_timer`: ordered `1.3448%`, shuffled `1.3473%`
  - `file_io_fs -> time_timer`: ordered `1.3755%`, shuffled `1.3755%`

Exact-transition order check:

- Several exact transitions also lose anomaly rate when order is destroyed:
  - `socketcall -> read`: ordered `2.3461%`, shuffled `1.4662%`, lift `+0.8799`
  - `read -> socketcall`: ordered `2.4803%`, shuffled `1.6579%`, lift `+0.8224`
  - `poll -> read`: ordered `2.3335%`, shuffled `1.8107%`, lift `+0.5228`
- Some transitions remain stable under shuffling:
  - `ugetrlimit -> fcntl64`: ordered `2.7943%`, shuffled `2.7710%`
  - `fcntl64 -> ugetrlimit`: ordered `2.7887%`, shuffled `2.7990%`

Interpretation:

- Order matters, but not uniformly.
- Some anomaly signal is genuinely sequential.
- Some anomaly signal can still be explained by event composition and high-frequency co-occurrence inside the same sequences.
- That means the first sequence model should be compared against a strong bag-of-events baseline rather than assumed superior by default.

Held-out application/path transfer check:

- I treated the main anomaly-carrying executables as candidate held-out applications:
  - `/usr/lib/libreoffice/program/soffice.bin`
  - `/usr/lib/firefox/firefox`
  - `/usr/sbin/apache2`
  - `/usr/bin/compiz`
  - `/usr/bin/Xorg`
- For each candidate path:
  - training motif set = anomalous transitions from `2016-03-11` to `2016-03-14` on all other paths
  - holdout set = anomalous transitions from `2016-03-15` to `2016-03-16` on the held-out path
- Exact-transition overlap results:
  - `soffice.bin`: `99.9143%`
  - `firefox`: `99.9985%`
  - `apache2`: `100.0%`
  - `compiz`: `99.9823%`
  - `Xorg`: `100.0%`
- Family-transition overlap results:
  - `soffice.bin`: `99.9990%`
  - `firefox`: `100.0%`
  - `apache2`: `100.0%`
  - `compiz`: `99.9984%`
  - `Xorg`: `100.0%`

Interpretation:

- The anomalous transition vocabulary on these high-impact paths is almost entirely recoverable from other paths in the training period.
- That is strong evidence that the dataset contains cross-application behavioral reuse, not only path-specific anomaly signatures.
- This does not prove open-world generalization, but it is enough to justify a transferable sequence-modeling attempt.

Recommendation:

- Keep a sequence model in scope.
- Benchmark it against a non-sequential baseline because some transition families are composition-driven.
- Define the first held-out application evaluation by excluding one of the major anomaly paths from training and scoring on its later-day windows.
- Prefer exact syscall transitions plus family transitions as the core sequence representation.

Practical impact:

- Sequence modeling is now justified by both label locality and partial order dependence.
- The dataset also shows unusually strong path-transfer overlap, which supports the user’s goal of learning behavior rather than memorizing applications.

## Phase S6

Date: 2026-05-18

Question:

- What exact dataset specification should be implemented for the first sequence model?

Final sequence design:

- source table: `host_logs.parquet`
- syscall lookup: [syscall-lookup-linux-v3_13.csv](/Users/harrish/Desktop/practicum/anomaly-detection-xai/dataset/syscall-lookup-linux-v3_13.csv:1)
- sequence identity: `(pro_id, path)`
- event order: `(date, time, event_id)`
- split rule:
  - train: `2016-03-11` to `2016-03-14`
  - validation: `2016-03-15`
  - test: `2016-03-16`
- split before windowing
- do not allow windows to cross split boundaries

Window policy:

- baseline window: length `64`, stride `32`
- comparison window: length `32`, stride `16`
- optional low-redundancy comparison: length `64`, stride `64`

Empirical support:

- split-truncated `(pro_id, path)` fragments:
  - train: `5,097`
  - validation: `1,753`
  - test: `1,548`
- baseline `64/32` windows:
  - train: `2,118,140`
  - validation: `389,634`
  - test: `299,477`
- comparison `32/16` windows:
  - train: `4,239,310`
  - validation: `780,364`
  - test: `599,950`

Interpretation:

- The default `64/32` setup has ample support in every split.
- `32/16` is useful as an ablation, but it is not needed as the main default.

Label rule:

- window label = `1` if any event in the window has `label = 1`
- keep per-event labels inside each window for later experiments

Interpretation:

- This matches the observed bursty anomaly structure from Phase S3.
- Whole-sequence labels are too coarse for this dataset.

Event representation:

- exact syscall id using the `i386`-preferred mapping
- syscall family using the `8` coarse categories:
  - `file_io_fs`
  - `memory`
  - `network_socket`
  - `other`
  - `permissions_identity`
  - `process_thread`
  - `signal_ipc`
  - `time_timer`
- inter-event timing using:
  - raw `delta_seconds`
  - `delta_seconds_log1p_clipped = log1p(min(delta_seconds, 300))`

Timing evidence:

- zero-second inter-event gaps dominate:
  - train: `97.5644%`
  - validation: `96.4323%`
  - test: `96.1506%`
- 99th percentile gap:
  - train: `1` second
  - validation: `4` seconds
  - test: `4` seconds

Interpretation:

- Timing is highly informative but extremely skewed.
- A clipped log transform is safer than feeding raw gaps.

Excluded features:

- raw `path`
- raw `pro_id`
- `event_id`
- raw `date`
- raw absolute `time`
- `attack_cat`
- `attack_subcat`

Interpretation:

- These exclusions are necessary if the goal is transferable exploit behavior rather than path memorization or label leakage.

Recommended output schema:

- one row per `(window_id, position)`
- required fields:
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

Training recommendation:

- first model: GRU
- first comparison: LSTM
- first input variants:
  - syscall id only
  - syscall id + family id
  - syscall id + family id + delta-time feature

Final deliverable:

- the full implementation-ready spec is recorded in [sequence-dataset-spec.md](/Users/harrish/Desktop/practicum/anomaly-detection-xai/docs/sequence-dataset-spec.md:1)

Practical impact:

- The sequence-specific EDA is now complete through Phase S6.
- The next step is implementation of the sequence dataset builder, followed by model training.

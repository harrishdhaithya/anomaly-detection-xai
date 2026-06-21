#!/usr/bin/env python3
"""Build corrected per-(date, pro_id, path) sequence features for the LSTM v2 baseline.

Reads the untouched raw host logs from ``dataset/raw_backup`` (which still contain
``pro_id`` and ``path``) and writes split feature parquets into an isolated folder.

Key corrections over the original notebook:
  * Sequence boundary is (date, pro_id, path) -- windows never mix unrelated
    processes and never cross the train/val/test date split.
  * delta_seconds is a lag *within* each sequence, not across the global stream.
  * The syscall token vocabulary is built on the TRAINING split only; syscalls
    unseen in training map to token 0 (OOV/pad).
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

DATASET_ROOT = Path("dataset")
RAW = DATASET_ROOT / "raw_backup" / "host_logs.parquet"
LOOKUP = DATASET_ROOT / "syscall_32.parquet"
OUT = DATASET_ROOT / "lstm_v2"

# Date-based split. Windows are built per (date, pro_id, path) so they never
# straddle these boundaries.
TRAIN_MAX_DATE = "2016-03-14"   # 2016-03-11 .. 2016-03-14
VAL_DATE = "2016-03-15"
TEST_DATE = "2016-03-16"

PARTITION = "date, pro_id, path"
ORDER = "time, event_id"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()

    # 1. Train-only syscall vocabulary (token 0 reserved for OOV / padding).
    con.execute(
        f"""
        CREATE OR REPLACE TABLE syscall_vocab AS
        SELECT sys_call, row_number() OVER (ORDER BY sys_call) AS sys_call_token
        FROM (
            SELECT DISTINCT sys_call
            FROM '{RAW}'
            WHERE date <= DATE '{TRAIN_MAX_DATE}'
        )
        """
    )
    con.execute(f"COPY syscall_vocab TO '{OUT / 'syscall_vocab.parquet'}' (FORMAT PARQUET)")
    vocab_size = con.sql("SELECT max(sys_call_token) + 1 FROM syscall_vocab").fetchone()[0]

    # 2. Per-sequence features for a given date predicate.
    def build_split(name: str, predicate: str) -> dict:
        out_path = OUT / f"features_{name}.parquet"
        con.execute(
            f"""
            COPY (
                WITH ordered AS (
                    SELECT
                        h.date, h.time, h.pro_id, h.path, h.event_id,
                        h.sys_call, h.label, h.attack_cat, h.attack_subcat,
                        row_number() OVER (
                            PARTITION BY {PARTITION} ORDER BY {ORDER}
                        ) AS seq_step,
                        coalesce(
                            datediff(
                                'second',
                                lag(h.date + h.time) OVER (
                                    PARTITION BY {PARTITION} ORDER BY {ORDER}
                                ),
                                h.date + h.time
                            ), 0
                        ) AS delta_seconds
                    FROM '{RAW}' h
                    WHERE {predicate}
                )
                SELECT
                    o.date, o.pro_id, o.path, o.event_id, o.seq_step,
                    o.sys_call,
                    coalesce(v.sys_call_token, 0) AS sys_call_token,
                    s.syscall_name,
                    o.delta_seconds,
                    least(ln(1 + greatest(o.delta_seconds, 0)), 10.0) AS delta_time_log,
                    o.label, o.attack_cat, o.attack_subcat
                FROM ordered o
                LEFT JOIN syscall_vocab v ON o.sys_call = v.sys_call
                LEFT JOIN '{LOOKUP}' s ON o.sys_call = s.sys_call
                ORDER BY o.date, o.pro_id, o.path, o.seq_step
            ) TO '{out_path}' (FORMAT PARQUET)
            """
        )
        stats = con.sql(
            f"""
            SELECT count(*) AS rows,
                   sum(label) AS anomaly_rows,
                   count(DISTINCT (date, pro_id, path)) AS sequences,
                   sum(CASE WHEN sys_call_token = 0 THEN 1 ELSE 0 END) AS oov_rows
            FROM '{out_path}'
            """
        ).fetchone()
        return {
            "path": str(out_path),
            "rows": int(stats[0]),
            "anomaly_rows": int(stats[1] or 0),
            "sequences": int(stats[2]),
            "oov_rows": int(stats[3] or 0),
        }

    splits = {
        "train": build_split("train", f"date <= DATE '{TRAIN_MAX_DATE}'"),
        "validation": build_split("validation", f"date = DATE '{VAL_DATE}'"),
        "test": build_split("test", f"date = DATE '{TEST_DATE}'"),
    }

    metadata = {
        "sequence_boundary": "(date, pro_id, path)",
        "order_within_sequence": ORDER,
        "syscall_vocab_size": int(vocab_size),
        "oov_pad_token": 0,
        "splits": splits,
        "split_dates": {
            "train": f"<= {TRAIN_MAX_DATE}",
            "validation": VAL_DATE,
            "test": TEST_DATE,
        },
    }
    (OUT / "metadata.json").write_text(json.dumps(metadata, indent=2))
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()

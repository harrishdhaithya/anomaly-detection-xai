#!/usr/bin/env python3
"""Build sampled fixed-length sequence arrays for the first LSTM baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create balanced LSTM windows from NGIDS host_logs.parquet."
    )
    parser.add_argument("--dataset-root", type=Path, default=Path("dataset"))
    parser.add_argument("--output-dir", type=Path, default=Path("dataset/lstm_sequences"))
    parser.add_argument("--window-length", type=int, default=64)
    parser.add_argument("--stride", type=int, default=32)
    parser.add_argument("--negative-ratio", type=int, default=2)
    parser.add_argument("--max-positive-windows", type=int, default=20000)
    parser.add_argument("--max-validation-positive-windows", type=int, default=5000)
    parser.add_argument("--max-test-positive-windows", type=int, default=5000)
    parser.add_argument("--max-negative-windows", type=int, default=None)
    parser.add_argument("--delta-clip", type=float, default=10.0)
    parser.add_argument("--row-limit", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def split_positive_limit(args: argparse.Namespace, split_name: str) -> int:
    if split_name == "train":
        return args.max_positive_windows
    if split_name == "validation":
        return args.max_validation_positive_windows
    return args.max_test_positive_windows


def build_events(con: duckdb.DuckDBPyConnection, args: argparse.Namespace) -> None:
    host_logs = sql_path(args.dataset_root / "host_logs.parquet")
    syscall_lookup = sql_path(args.dataset_root / "syscall-lookup-linux-v3_13.csv")
    row_limit_clause = f"LIMIT {args.row_limit}" if args.row_limit else ""

    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE source_rows AS
    SELECT DISTINCT
        date,
        time,
        pro_id,
        path,
        sys_call,
        event_id,
        label
    FROM read_parquet('{host_logs}')
    {row_limit_clause}
    """)

    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE events AS
    WITH mapped AS (
        SELECT
            CASE
                WHEN h.date <= DATE '2016-03-14' THEN 'train'
                WHEN h.date = DATE '2016-03-15' THEN 'validation'
                ELSE 'test'
            END AS split_name,
            h.date,
            h.time,
            h.pro_id,
            h.path,
            h.sys_call,
            coalesce(l.preferred_family, 'unknown') AS syscall_family,
            h.event_id,
            cast(h.label AS INTEGER) AS label,
            h.date + h.time AS event_ts
        FROM source_rows h
        LEFT JOIN read_csv_auto('{syscall_lookup}') l USING (sys_call)
    )
    SELECT
        *,
        row_number() OVER (
            PARTITION BY split_name, pro_id, path
            ORDER BY date, time, event_id
        ) AS seq_pos,
        datediff(
            'second',
            lag(event_ts) OVER (
                PARTITION BY split_name, pro_id, path
                ORDER BY date, time, event_id
            ),
            event_ts
        ) AS delta_seconds
    FROM mapped
    """)


def build_vocabs(con: duckdb.DuckDBPyConnection) -> dict:
    con.execute("""
    CREATE OR REPLACE TEMP TABLE syscall_vocab AS
    SELECT sys_call, row_number() OVER (ORDER BY sys_call) AS syscall_token
    FROM (SELECT DISTINCT sys_call FROM events WHERE split_name = 'train')
    """)
    con.execute("""
    CREATE OR REPLACE TEMP TABLE family_vocab AS
    SELECT syscall_family, row_number() OVER (ORDER BY syscall_family) AS family_token
    FROM (SELECT DISTINCT syscall_family FROM events WHERE split_name = 'train')
    """)

    syscall_vocab = {
        str(sys_call): int(token)
        for sys_call, token in con.execute(
            "SELECT sys_call, syscall_token FROM syscall_vocab ORDER BY syscall_token"
        ).fetchall()
    }
    family_vocab = {
        family: int(token)
        for family, token in con.execute(
            "SELECT syscall_family, family_token FROM family_vocab ORDER BY family_token"
        ).fetchall()
    }
    return {
        "syscall_vocab": syscall_vocab,
        "family_vocab": family_vocab,
        "syscall_vocab_size": len(syscall_vocab) + 1,
        "family_vocab_size": len(family_vocab) + 1,
    }


def build_windows(con: duckdb.DuckDBPyConnection, args: argparse.Namespace) -> None:
    window_length = args.window_length
    stride = args.stride

    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE window_candidates AS
    WITH starts AS (
        SELECT
            split_name,
            pro_id,
            path,
            seq_pos AS start_pos
        FROM events
        WHERE ((seq_pos - 1) % {stride}) = 0
    )
    SELECT
        s.split_name,
        s.pro_id,
        s.path,
        s.start_pos,
        max(e.label) AS window_label,
        count(*) AS window_rows
    FROM starts s
    JOIN events e
      ON e.split_name = s.split_name
     AND e.pro_id = s.pro_id
     AND e.path = s.path
     AND e.seq_pos BETWEEN s.start_pos AND s.start_pos + {window_length - 1}
    GROUP BY s.split_name, s.pro_id, s.path, s.start_pos
    HAVING count(*) = {window_length}
    """)

    union_parts: list[str] = []
    for split_name in ("train", "validation", "test"):
        pos_limit = split_positive_limit(args, split_name)
        neg_limit = args.max_negative_windows or pos_limit * args.negative_ratio
        union_parts.append(f"""
        SELECT * FROM (
            SELECT *
            FROM window_candidates
            WHERE split_name = '{split_name}' AND window_label = 1
            ORDER BY hash(split_name, pro_id, path, start_pos)
            LIMIT {pos_limit}
        )
        UNION ALL
        SELECT * FROM (
            SELECT *
            FROM window_candidates
            WHERE split_name = '{split_name}' AND window_label = 0
            ORDER BY hash(split_name, pro_id, path, start_pos)
            LIMIT {neg_limit}
        )
        """)

    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE selected_windows AS
    SELECT
        row_number() OVER (ORDER BY split_name, pro_id, path, start_pos) AS window_id,
        *
    FROM ({' UNION ALL '.join(union_parts)})
    """)


def export_split(
    con: duckdb.DuckDBPyConnection,
    output_dir: Path,
    split_name: str,
    window_length: int,
    delta_clip: float,
) -> dict:
    rows = con.execute(f"""
    SELECT
        w.window_id,
        e.seq_pos - w.start_pos AS step_index,
        coalesce(v.syscall_token, 0)::INTEGER AS syscall_token,
        coalesce(f.family_token, 0)::INTEGER AS family_token,
        least(
            log(1 + greatest(coalesce(e.delta_seconds, 0), 0)),
            {delta_clip}
        )::DOUBLE AS delta_time,
        w.window_label::INTEGER AS window_label
    FROM selected_windows w
    JOIN events e
      ON e.split_name = w.split_name
     AND e.pro_id = w.pro_id
     AND e.path = w.path
     AND e.seq_pos BETWEEN w.start_pos AND w.start_pos + {window_length - 1}
    LEFT JOIN syscall_vocab v ON e.sys_call = v.sys_call
    LEFT JOIN family_vocab f ON e.syscall_family = f.syscall_family
    WHERE w.split_name = '{split_name}'
    ORDER BY w.window_id, step_index
    """).fetchall()

    window_ids = sorted({int(row[0]) for row in rows})
    n_windows = len(window_ids)
    id_to_index = {window_id: idx for idx, window_id in enumerate(window_ids)}

    syscall_tokens = np.zeros((n_windows, window_length), dtype=np.int32)
    family_tokens = np.zeros((n_windows, window_length), dtype=np.int32)
    delta_time = np.zeros((n_windows, window_length, 1), dtype=np.float32)
    labels = np.zeros((n_windows,), dtype=np.int32)

    for window_id, step, syscall_token, family_token, gap, label in rows:
        i = id_to_index[int(window_id)]
        j = int(step)
        syscall_tokens[i, j] = int(syscall_token)
        family_tokens[i, j] = int(family_token)
        delta_time[i, j, 0] = float(gap)
        labels[i] = int(label)

    output_path = output_dir / f"{split_name}.npz"
    np.savez_compressed(
        output_path,
        syscall_tokens=syscall_tokens,
        family_tokens=family_tokens,
        delta_time=delta_time,
        labels=labels,
    )

    return {
        "split": split_name,
        "path": str(output_path),
        "windows": int(n_windows),
        "positive_windows": int(labels.sum()),
        "negative_windows": int(n_windows - labels.sum()),
    }


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = args.output_dir / "metadata.json"

    if metadata_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"{metadata_path} already exists. Pass --overwrite to rebuild the dataset."
        )

    con = duckdb.connect()
    con.execute(f"PRAGMA temp_directory='{sql_path(args.output_dir)}'")

    build_events(con, args)
    vocab_metadata = build_vocabs(con)
    build_windows(con, args)

    split_metadata = [
        export_split(con, args.output_dir, split_name, args.window_length, args.delta_clip)
        for split_name in ("train", "validation", "test")
    ]

    metadata = {
        "dataset_root": str(args.dataset_root),
        "window_length": args.window_length,
        "stride": args.stride,
        "negative_ratio": args.negative_ratio,
        "delta_clip": args.delta_clip,
        "row_limit": args.row_limit,
        "features": ["syscall_tokens", "family_tokens", "delta_time"],
        "target": "window label is 1 when any event in the window has label = 1",
        "excluded_inputs": [
            "path",
            "pro_id",
            "event_id",
            "date",
            "time",
            "attack_cat",
            "attack_subcat",
            "label",
        ],
        **vocab_metadata,
        "splits": split_metadata,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2))
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()

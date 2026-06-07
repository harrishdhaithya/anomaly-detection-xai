#!/usr/bin/env python3
"""Recover shifted NGIDS ground-truth rows into a derived parquet file.

This script does not modify the raw ground_truth.parquet file. It writes a
derived parquet with normal and recovered rows, while dropping embedded header
rows.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recover shifted ground-truth rows.")
    parser.add_argument("--input", type=Path, default=Path("dataset/ground_truth.parquet"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dataset/ground_truth_recovered.parquet"),
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("dataset/ground_truth_recovered_summary.json"),
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists() and not args.overwrite:
        raise FileExistsError(f"{args.output} exists. Pass --overwrite to rebuild it.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()

    input_path = sql_path(args.input)
    output_path = sql_path(args.output)

    summary_before = con.execute(f"""
    SELECT
        count(*) AS total_rows,
        count(*) FILTER (WHERE time = 'Time') AS header_rows,
        count(*) FILTER (WHERE instr(trim(attack_cat), '->') > 0) AS shift_pattern_a_rows,
        count(*) FILTER (WHERE instr(trim(time), '->') > 0) AS shift_pattern_b_rows,
        count(*) FILTER (
            WHERE time != 'Time'
              AND instr(trim(attack_cat), '->') = 0
              AND instr(trim(time), '->') = 0
        ) AS normal_rows
    FROM read_parquet('{input_path}')
    """).fetchone()

    con.execute(f"""
    COPY (
        WITH classified AS (
            SELECT
                *,
                CASE
                    WHEN time = 'Time' THEN 'header_row'
                    WHEN instr(trim(attack_cat), '->') > 0 THEN 'shift_pattern_a'
                    WHEN instr(trim(time), '->') > 0 THEN 'shift_pattern_b'
                    ELSE 'normal'
                END AS row_status
            FROM read_parquet('{input_path}')
        ),
        recovered AS (
            SELECT
                date,
                CASE
                    WHEN row_status = 'shift_pattern_a' THEN trim(attack_subcat)
                    WHEN row_status = 'shift_pattern_b' THEN trim(attack_cat)
                    ELSE trim(time)
                END AS time,
                CASE
                    WHEN row_status = 'shift_pattern_a' THEN trim(attack_name)
                    WHEN row_status = 'shift_pattern_b' THEN trim(attack_subcat)
                    ELSE trim(attack_cat)
                END AS attack_cat,
                CASE
                    WHEN row_status = 'shift_pattern_a' THEN trim(attack_refrence)
                    WHEN row_status = 'shift_pattern_b' THEN trim(attack_name)
                    ELSE trim(attack_subcat)
                END AS attack_subcat,
                CASE
                    WHEN row_status = 'shift_pattern_a' THEN trim(ips)
                    WHEN row_status = 'shift_pattern_b' THEN trim(attack_refrence)
                    ELSE trim(attack_name)
                END AS attack_name,
                CASE
                    WHEN row_status = 'shift_pattern_a' THEN trim(time)
                    WHEN row_status = 'shift_pattern_b' THEN trim(ips)
                    ELSE trim(attack_refrence)
                END AS attack_refrence,
                CASE
                    WHEN row_status = 'shift_pattern_a' THEN trim(attack_cat)
                    WHEN row_status = 'shift_pattern_b' THEN trim(time)
                    ELSE trim(ips)
                END AS ips,
                row_status
            FROM classified
            WHERE row_status != 'header_row'
        )
        SELECT *
        FROM recovered
    ) TO '{output_path}' (FORMAT PARQUET)
    """)

    summary_after = con.execute(f"""
    SELECT
        count(*) AS output_rows,
        count(*) FILTER (WHERE row_status = 'normal') AS normal_rows,
        count(*) FILTER (WHERE row_status = 'shift_pattern_a') AS recovered_shift_pattern_a_rows,
        count(*) FILTER (WHERE row_status = 'shift_pattern_b') AS recovered_shift_pattern_b_rows,
        count(*) FILTER (WHERE time = 'Time') AS remaining_header_rows,
        count(*) FILTER (WHERE instr(trim(attack_cat), '->') > 0) AS remaining_attack_cat_ip_rows,
        count(*) FILTER (WHERE instr(trim(time), '->') > 0) AS remaining_time_ip_rows
    FROM read_parquet('{output_path}')
    """).fetchone()

    summary = {
        "input": str(args.input),
        "output": str(args.output),
        "before": {
            "total_rows": summary_before[0],
            "header_rows": summary_before[1],
            "shift_pattern_a_rows": summary_before[2],
            "shift_pattern_b_rows": summary_before[3],
            "normal_rows": summary_before[4],
        },
        "after": {
            "output_rows": summary_after[0],
            "normal_rows": summary_after[1],
            "recovered_shift_pattern_a_rows": summary_after[2],
            "recovered_shift_pattern_b_rows": summary_after[3],
            "remaining_header_rows": summary_after[4],
            "remaining_attack_cat_ip_rows": summary_after[5],
            "remaining_time_ip_rows": summary_after[6],
        },
    }

    args.summary_output.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

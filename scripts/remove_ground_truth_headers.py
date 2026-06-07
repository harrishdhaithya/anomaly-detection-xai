#!/usr/bin/env python3
"""Remove embedded header rows from ground_truth.parquet into a derived file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove ground-truth header rows.")
    parser.add_argument("--input", type=Path, default=Path("dataset/ground_truth.parquet"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dataset/ground_truth_no_headers.parquet"),
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("dataset/ground_truth_no_headers_summary.json"),
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

    before = con.execute(f"""
    SELECT
        count(*) AS total_rows,
        count(*) FILTER (WHERE time = 'Time') AS header_rows
    FROM read_parquet('{input_path}')
    """).fetchone()

    con.execute(f"""
    COPY (
        SELECT *
        FROM read_parquet('{input_path}')
        WHERE time != 'Time'
    ) TO '{output_path}' (FORMAT PARQUET)
    """)

    after = con.execute(f"""
    SELECT
        count(*) AS output_rows,
        count(*) FILTER (WHERE time = 'Time') AS remaining_header_rows
    FROM read_parquet('{output_path}')
    """).fetchone()

    summary = {
        "input": str(args.input),
        "output": str(args.output),
        "before": {
            "total_rows": before[0],
            "header_rows": before[1],
        },
        "after": {
            "output_rows": after[0],
            "remaining_header_rows": after[1],
        },
    }
    args.summary_output.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

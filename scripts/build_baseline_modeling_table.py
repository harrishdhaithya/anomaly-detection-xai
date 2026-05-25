#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build split-aware baseline modeling tables from host_logs.parquet "
            "using train-derived frequency features."
        )
    )
    parser.add_argument(
        "--input",
        default="dataset/host_logs.parquet",
        help="Path to host_logs.parquet",
    )
    parser.add_argument(
        "--output-dir",
        default="dataset/modeling_baseline",
        help="Directory for generated train/validation/test parquet files",
    )
    parser.add_argument(
        "--train-end-date",
        default="2016-03-14",
        help="Last date included in the training split (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--validation-date",
        default="2016-03-15",
        help="Validation split date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--test-date",
        default="2016-03-16",
        help="Test split date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--rare-quantile",
        type=float,
        default=0.25,
        help="Training quantile used to derive rarity thresholds",
    )
    parser.add_argument(
        "--compression",
        default="zstd",
        help="Parquet compression codec for generated files",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=4,
        help="DuckDB thread count",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow writing into a non-empty output directory",
    )
    return parser.parse_args()


def sql_path(path: Path) -> str:
    return path.resolve().as_posix()


def prepare_output_dir(output_dir: Path, overwrite: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = [path for path in output_dir.iterdir() if path.is_file()]
    if existing and not overwrite:
        raise FileExistsError(
            f"{output_dir} is not empty. Use --overwrite to reuse it."
        )
    if existing and overwrite:
        for path in existing:
            path.unlink()


def fetch_threshold(con: duckdb.DuckDBPyConnection, view_name: str, column_name: str, quantile: float) -> int:
    value = con.sql(
        f"SELECT approx_quantile({column_name}, {quantile}) FROM {view_name}"
    ).fetchone()[0]
    if value is None:
        return 0
    return int(value)


def create_views(con: duckdb.DuckDBPyConnection, input_path: Path, train_end_date: str, validation_date: str, test_date: str) -> None:
    host_logs = sql_path(input_path)
    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW host_logs_base AS
        SELECT
            date AS event_date,
            CAST(time AS VARCHAR) AS event_time,
            path,
            sys_call,
            pro_id,
            label,
            CAST(EXTRACT('hour' FROM time) AS INTEGER) AS hour,
            CAST(EXTRACT('minute' FROM time) AS INTEGER) AS minute,
            CAST(EXTRACT('second' FROM time) AS INTEGER) AS second,
            CASE
                WHEN date <= DATE '{train_end_date}' THEN 'train'
                WHEN date = DATE '{validation_date}' THEN 'validation'
                WHEN date = DATE '{test_date}' THEN 'test'
                ELSE NULL
            END AS split_part
        FROM '{host_logs}'
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TEMP VIEW host_logs_features AS
        SELECT
            *,
            hour * 3600 + minute * 60 + second AS seconds_since_midnight,
            CASE
                WHEN hour BETWEEN 1 AND 12 THEN 1
                ELSE 0
            END AS is_01_12_hour_block
        FROM host_logs_base
        WHERE split_part IS NOT NULL
        """
    )
    train_row_count = con.sql(
        """
        SELECT count(*)
        FROM host_logs_features
        WHERE split_part = 'train'
        """
    ).fetchone()[0]
    if not train_row_count:
        raise ValueError("Training split is empty. Check the split dates.")

    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW path_stats AS
        SELECT
            path,
            count(*) AS path_train_count,
            CAST(count(*) AS DOUBLE) / {train_row_count} AS path_train_relative_freq
        FROM host_logs_features
        WHERE split_part = 'train'
        GROUP BY 1
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW sys_call_stats AS
        SELECT
            sys_call,
            count(*) AS sys_call_train_count,
            CAST(count(*) AS DOUBLE) / {train_row_count} AS sys_call_train_relative_freq
        FROM host_logs_features
        WHERE split_part = 'train'
        GROUP BY 1
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW path_sys_call_stats AS
        SELECT
            path,
            sys_call,
            count(*) AS path_sys_call_train_count,
            CAST(count(*) AS DOUBLE) / {train_row_count} AS path_sys_call_train_relative_freq
        FROM host_logs_features
        WHERE split_part = 'train'
        GROUP BY 1, 2
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TEMP VIEW pro_id_stats AS
        SELECT
            pro_id,
            count(*) AS pro_id_train_count,
            count(DISTINCT path) AS pro_id_train_distinct_path_count,
            count(DISTINCT sys_call) AS pro_id_train_distinct_sys_call_count
        FROM host_logs_features
        WHERE split_part = 'train'
        GROUP BY 1
        """
    )


def build_feature_query(split_part: str, thresholds: dict[str, int]) -> str:
    return f"""
        SELECT
            split_part,
            event_date,
            event_time,
            label,
            path,
            sys_call,
            hour,
            minute,
            second,
            seconds_since_midnight,
            is_01_12_hour_block,
            COALESCE(path_train_count, 0) AS path_train_count,
            COALESCE(path_train_relative_freq, 0.0) AS path_train_relative_freq,
            CASE
                WHEN path_train_count IS NULL THEN 1
                ELSE 0
            END AS is_unseen_path,
            CASE
                WHEN COALESCE(path_train_count, 0) <= {thresholds["path"]} THEN 1
                ELSE 0
            END AS is_rare_path,
            COALESCE(sys_call_train_count, 0) AS sys_call_train_count,
            COALESCE(sys_call_train_relative_freq, 0.0) AS sys_call_train_relative_freq,
            CASE
                WHEN sys_call_train_count IS NULL THEN 1
                ELSE 0
            END AS is_unseen_sys_call,
            CASE
                WHEN COALESCE(sys_call_train_count, 0) <= {thresholds["sys_call"]} THEN 1
                ELSE 0
            END AS is_rare_sys_call,
            COALESCE(path_sys_call_train_count, 0) AS path_sys_call_train_count,
            COALESCE(path_sys_call_train_relative_freq, 0.0) AS path_sys_call_train_relative_freq,
            CASE
                WHEN path_sys_call_train_count IS NULL THEN 1
                ELSE 0
            END AS is_unseen_path_sys_call,
            CASE
                WHEN COALESCE(path_sys_call_train_count, 0) <= {thresholds["path_sys_call"]} THEN 1
                ELSE 0
            END AS is_rare_path_sys_call,
            COALESCE(pro_id_train_count, 0) AS pro_id_train_count,
            COALESCE(pro_id_train_distinct_path_count, 0) AS pro_id_train_distinct_path_count,
            COALESCE(pro_id_train_distinct_sys_call_count, 0) AS pro_id_train_distinct_sys_call_count,
            CASE
                WHEN pro_id_train_count IS NULL THEN 1
                ELSE 0
            END AS is_unseen_pro_id,
            CASE
                WHEN COALESCE(pro_id_train_count, 0) <= {thresholds["pro_id"]} THEN 1
                ELSE 0
            END AS is_low_history_pro_id
        FROM host_logs_features
        LEFT JOIN path_stats USING (path)
        LEFT JOIN sys_call_stats USING (sys_call)
        LEFT JOIN path_sys_call_stats USING (path, sys_call)
        LEFT JOIN pro_id_stats USING (pro_id)
        WHERE split_part = '{split_part}'
    """


def split_summary(con: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    rows = con.sql(
        """
        SELECT
            split_part,
            count(*) AS rows,
            count(*) FILTER (WHERE label = 1) AS anomalies,
            round(100.0 * count(*) FILTER (WHERE label = 1) / count(*), 4) AS anomaly_rate_pct,
            count(DISTINCT path) AS distinct_paths,
            count(DISTINCT sys_call) AS distinct_sys_calls,
            count(DISTINCT pro_id) AS distinct_pro_ids,
            count(DISTINCT row(path, sys_call)) AS distinct_path_sys_calls
        FROM host_logs_features
        GROUP BY 1
        ORDER BY CASE split_part WHEN 'train' THEN 1 WHEN 'validation' THEN 2 ELSE 3 END
        """
    ).fetchall()
    columns = [
        "split_part",
        "rows",
        "anomalies",
        "anomaly_rate_pct",
        "distinct_paths",
        "distinct_sys_calls",
        "distinct_pro_ids",
        "distinct_path_sys_calls",
    ]
    return [dict(zip(columns, row)) for row in rows]


def write_outputs(
    con: duckdb.DuckDBPyConnection,
    output_dir: Path,
    compression: str,
    thresholds: dict[str, int],
) -> None:
    for split_part in ("train", "validation", "test"):
        target = sql_path(output_dir / f"{split_part}.parquet")
        con.execute(
            f"""
            COPY (
                {build_feature_query(split_part, thresholds)}
            ) TO '{target}' (
                FORMAT PARQUET,
                COMPRESSION {compression}
            )
            """
        )


def write_metadata(
    output_dir: Path,
    input_path: Path,
    args: argparse.Namespace,
    thresholds: dict[str, int],
    summaries: list[dict[str, object]],
) -> None:
    metadata = {
        "input_path": str(input_path.resolve()),
        "output_dir": str(output_dir.resolve()),
        "split": {
            "train_end_date": args.train_end_date,
            "validation_date": args.validation_date,
            "test_date": args.test_date,
        },
        "rare_quantile": args.rare_quantile,
        "rare_thresholds": thresholds,
        "feature_columns": [
            "split_part",
            "event_date",
            "event_time",
            "label",
            "path",
            "sys_call",
            "hour",
            "minute",
            "second",
            "seconds_since_midnight",
            "is_01_12_hour_block",
            "path_train_count",
            "path_train_relative_freq",
            "is_unseen_path",
            "is_rare_path",
            "sys_call_train_count",
            "sys_call_train_relative_freq",
            "is_unseen_sys_call",
            "is_rare_sys_call",
            "path_sys_call_train_count",
            "path_sys_call_train_relative_freq",
            "is_unseen_path_sys_call",
            "is_rare_path_sys_call",
            "pro_id_train_count",
            "pro_id_train_distinct_path_count",
            "pro_id_train_distinct_sys_call_count",
            "is_unseen_pro_id",
            "is_low_history_pro_id",
        ],
        "split_summaries": summaries,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"Input parquet was not found at {input_path}")
    if not 0.0 < args.rare_quantile < 1.0:
        raise ValueError("--rare-quantile must be between 0 and 1")

    prepare_output_dir(output_dir, args.overwrite)

    con = duckdb.connect()
    con.execute(f"PRAGMA threads={args.threads}")

    create_views(
        con,
        input_path=input_path,
        train_end_date=args.train_end_date,
        validation_date=args.validation_date,
        test_date=args.test_date,
    )

    thresholds = {
        "path": fetch_threshold(con, "path_stats", "path_train_count", args.rare_quantile),
        "sys_call": fetch_threshold(con, "sys_call_stats", "sys_call_train_count", args.rare_quantile),
        "path_sys_call": fetch_threshold(
            con,
            "path_sys_call_stats",
            "path_sys_call_train_count",
            args.rare_quantile,
        ),
        "pro_id": fetch_threshold(con, "pro_id_stats", "pro_id_train_count", args.rare_quantile),
    }
    summaries = split_summary(con)
    write_outputs(con, output_dir=output_dir, compression=args.compression, thresholds=thresholds)
    write_metadata(
        output_dir=output_dir,
        input_path=input_path,
        args=args,
        thresholds=thresholds,
        summaries=summaries,
    )

    print("Wrote baseline modeling tables:")
    for split_part in ("train", "validation", "test"):
        print(f"- {output_dir / f'{split_part}.parquet'}")
    print(f"- {output_dir / 'metadata.json'}")
    print("Rarity thresholds:")
    for name, value in thresholds.items():
        print(f"- {name}: {value}")


if __name__ == "__main__":
    main()

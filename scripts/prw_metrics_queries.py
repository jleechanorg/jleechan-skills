#!/usr/bin/env python3
"""Query canonical PRW event exports and cached PR metadata with DuckDB."""

import argparse
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from scripts.prw_metrics import format_iso_utc, parse_iso_utc


def _load_jsonl_table(connection, table_name, path):
    if path is None:
        connection.execute(
            f"CREATE TEMP TABLE {table_name} AS "
            "SELECT NULL::JSON AS json WHERE FALSE"
        )
        return
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"input JSONL does not exist: {source}")
    connection.execute(
        f"CREATE TEMP TABLE {table_name} AS "
        "SELECT json FROM read_ndjson_objects(?)",
        [str(source)],
    )


def _load_human_summary(connection, path):
    if path is None:
        connection.execute(
            "CREATE TEMP TABLE prw_input_human_summary AS "
            "SELECT '{}'::JSON AS json"
        )
        return
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    connection.execute(
        "CREATE TEMP TABLE prw_input_human_summary AS "
        "SELECT CAST(? AS JSON) AS json",
        [json.dumps(payload, separators=(",", ":"))],
    )


def _native_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str) and value[:1] in ("{", "["):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _query_rows(connection, sql):
    cursor = connection.execute(sql)
    columns = [column[0] for column in cursor.description]
    return [
        {column: _native_value(value) for column, value in zip(columns, row)}
        for row in cursor.fetchall()
    ]


def run_query(
    *,
    events_path,
    pr_snapshots_path,
    snapshot_at_utc,
    human_summary_path=None,
    attempt_observations_path=None,
    time_metrics_path=None,
    sql_path=None,
    duckdb_module=None,
):
    """Run the read-only query; event identities are deduplicated upstream."""
    if duckdb_module is None:
        try:
            import duckdb as duckdb_module
        except ImportError as exc:
            raise RuntimeError(
                "DuckDB is required for PRW queries; install it in a "
                "task-scoped environment."
            ) from exc

    cutoff = parse_iso_utc(snapshot_at_utc)
    if cutoff is None or not snapshot_at_utc.endswith("Z"):
        raise ValueError("snapshot_at_utc must be an explicit UTC instant ending in Z")

    connection = duckdb_module.connect(database=":memory:")
    try:
        _load_jsonl_table(connection, "prw_input_events", events_path)
        _load_jsonl_table(connection, "prw_input_pr_snapshots", pr_snapshots_path)
        _load_jsonl_table(connection, "prw_input_attempts", attempt_observations_path)
        _load_jsonl_table(connection, "prw_input_time_metrics", time_metrics_path)
        _load_human_summary(connection, human_summary_path)
        connection.execute(
            "CREATE TEMP TABLE prw_query_parameters AS "
            "SELECT CAST(? AS TIMESTAMPTZ) AS snapshot_at_utc, "
            "CAST(? AS TIMESTAMPTZ) AS window_start_utc",
            [format_iso_utc(cutoff), format_iso_utc(cutoff - timedelta(days=14))],
        )
        query_file = Path(sql_path) if sql_path else Path(__file__).with_name(
            "prw_metrics_queries.sql"
        )
        connection.execute(query_file.read_text(encoding="utf-8"))
        return {
            "snapshot_at_utc": format_iso_utc(cutoff),
            "window_start_utc": format_iso_utc(cutoff - timedelta(days=14)),
            "query_method": (
                "DuckDB quantile_disc; canonical events deduplicated upstream"
            ),
            "query_coverage": _query_rows(
                connection,
                "SELECT * FROM prw_query_coverage",
            )[0],
            "pr_metrics": _query_rows(
                connection,
                "SELECT * FROM prw_per_pr_metrics_export "
                "ORDER BY repository, pr_number",
            ),
            "metric_cohorts": _query_rows(
                connection,
                "SELECT * FROM prw_metric_cohorts_export "
                "ORDER BY repository, cohort_definition, metric_family, measure",
            ),
        }
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--events", required=True, help="Canonical deduplicated event JSONL"
    )
    parser.add_argument("--prs", required=True, help="Cached PR snapshot JSONL")
    parser.add_argument("--snapshot-at-utc", required=True)
    parser.add_argument(
        "--human-summary", help="Source-reviewed per-PR human summary JSON"
    )
    parser.add_argument("--attempts", help="Canonical review-attempt observation JSONL")
    parser.add_argument("--time-metrics", help="Explicit per-PR measured time JSONL")
    parser.add_argument("--sql", help="Optional SQL file override")
    parser.add_argument(
        "--output", help="Optional JSON result path; otherwise print to stdout"
    )
    args = parser.parse_args()
    result = run_query(
        events_path=args.events,
        pr_snapshots_path=args.prs,
        snapshot_at_utc=args.snapshot_at_utc,
        human_summary_path=args.human_summary,
        attempt_observations_path=args.attempts,
        time_metrics_path=args.time_metrics,
        sql_path=args.sql,
    )
    output = json.dumps(result, default=_native_value, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()

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


def _valid_count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _catalog_scenario_summary(catalog_path, connection):
    """Build exact-model public-list scenarios without changing observed costs."""
    if catalog_path is None:
        return [], []
    catalog_file = Path(catalog_path)
    catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
    rates = {
        (row.get("model_id"), row.get("source_protocol")): row
        for row in catalog.get("rates", [])
        if row.get("model_id") and row.get("source_protocol")
    }
    version = catalog.get("retrieved_at_utc") or catalog.get("schema_version")
    basis = catalog.get("basis")
    grouped = {}

    def tier_rate(rate_row, protocol, buckets):
        short = rate_row.get("standard_short")
        long = rate_row.get("long_context_over_272k")
        tiers = rate_row.get("tiers")
        prompt_parts = (
            ("input_uncached", "cache_read")
            if protocol == "openai"
            else ("input_uncached", "cache_read", "cache_write_5m", "cache_write_1h")
        )
        if short is not None and long is not None:
            if not all(_valid_count(buckets.get(key)) for key in prompt_parts):
                return None, "UNKNOWN_NATIVE_PROMPT_TOTAL"
            prompt_total = sum(buckets[key] for key in prompt_parts)
            return (
                (long, "prompt_input_tokens > 272000")
                if prompt_total > 272000
                else (short, "prompt_input_tokens <= 272000")
            )
        if tiers:
            if not all(_valid_count(buckets.get(key)) for key in prompt_parts):
                return None, "UNKNOWN_NATIVE_PROMPT_TOTAL"
            prompt_total = sum(buckets[key] for key in prompt_parts)
            for tier in tiers:
                condition = tier.get("condition", "")
                threshold = int(condition.rsplit(" ", 1)[-1])
                if "<=" in condition and prompt_total <= threshold:
                    return tier, condition
                if ">" in condition and prompt_total > threshold:
                    return tier, condition
            return None, "UNKNOWN_NATIVE_TIER"
        return rate_row, "flat"

    def add_event(event, attribution, method, confidence=None):
        model = event.get("model")
        protocol = event.get("provider")
        try:
            weight = Decimal(str(attribution.get("weight")))
        except Exception:
            return
        if not weight.is_finite() or weight < 0:
            return
        rate_row = rates.get((model, protocol))
        if not rate_row or rate_row.get("status") == "unpriced":
            key = (
                attribution.get("pr", ""), model, None, protocol, method,
                confidence, "UNKNOWN",
            )
            item = grouped.setdefault(key, {
                "event_n": 0, "unknown_event_n": 0,
                "known_component_subtotal_usd": None,
                "scenario_cost_usd": Decimal(0), "unknown_buckets": set(),
                "token_totals_by_bucket": {}, "unknown_token_buckets": set(),
                "unknown_status": (
                    "UNKNOWN_UNPRICED_MODEL" if rate_row
                    else "UNKNOWN_NO_EXACT_MODEL_PROTOCOL_RATE"
                ),
            })
            item["event_n"] += 1
            item["unknown_event_n"] += 1
            item["unknown_buckets"].add("exact_model_protocol_rate")
            for token_bucket, count in (event.get("tokens_by_bucket") or {}).items():
                if _valid_count(count):
                    item["token_totals_by_bucket"][token_bucket] = (
                        item["token_totals_by_bucket"].get(token_bucket, Decimal(0))
                        + Decimal(count) * weight
                    )
                else:
                    item["unknown_token_buckets"].add(token_bucket)
            return
        buckets = event.get("tokens_by_bucket") or {}
        selected, tier = tier_rate(rate_row, protocol, buckets)
        known = Decimal(0)
        unknown = []
        if selected is not None:
            for bucket, rate in selected.items():
                if bucket not in {
                    "input_uncached", "cache_read", "cache_write_5m",
                    "cache_write_1h", "cache_write_30m", "cache_write_12h", "output",
                }:
                    continue
                count = buckets.get(bucket)
                if rate is None:
                    if _valid_count(count) and count == 0:
                        continue
                    unknown.append(bucket)
                    continue
                if not _valid_count(count):
                    unknown.append(bucket)
                    continue
                known += Decimal(count) * Decimal(str(rate)) / Decimal(1000000)
        else:
            unknown.append("native_prompt_total")
        key = (
            attribution.get("pr", ""), model, rate_row.get("model_vendor"),
            protocol, method, confidence, tier,
        )
        item = grouped.setdefault(key, {
            "event_n": 0,
            "unknown_event_n": 0,
            "known_component_subtotal_usd": Decimal(0),
            "scenario_cost_usd": Decimal(0), "unknown_buckets": set(),
            "token_totals_by_bucket": {},
            "unknown_token_buckets": set(),
        })
        item["event_n"] += 1
        for token_bucket in (
            "input_uncached", "cache_read", "cache_write_5m", "cache_write_1h",
            "cache_write_30m", "cache_write_12h", "output",
        ):
            count = buckets.get(token_bucket)
            if _valid_count(count):
                item["token_totals_by_bucket"][token_bucket] = (
                    item["token_totals_by_bucket"].get(token_bucket, Decimal(0))
                    + Decimal(count) * weight
                )
            else:
                item["unknown_token_buckets"].add(token_bucket)
        item["known_component_subtotal_usd"] += known * weight
        if unknown:
            item["unknown_event_n"] += 1
            item["unknown_buckets"].update(unknown)
        else:
            item["scenario_cost_usd"] += known * weight

    event_cursor = connection.execute(
        "SELECT json FROM prw_input_events WHERE "
        "json_array_length(json_extract(json, '$.validated_attributions')) > 0 "
        "OR json_array_length(json_extract(json, '$.branch_attributions')) > 0"
    )
    while True:
        batch = event_cursor.fetchmany(1000)
        if not batch:
            break
        for (payload,) in batch:
            event = json.loads(payload) if isinstance(payload, str) else payload
            for attribution in event.get("validated_attributions") or []:
                method = attribution.get("method")
                if method in ("direct", "convention"):
                    add_event(event, attribution, method)
            for attribution in event.get("branch_attributions") or []:
                add_event(
                    event, attribution, "branch_associated",
                    attribution.get("confidence"),
                )

    rows = []
    for key, values in grouped.items():
        pr, model, vendor, protocol, method, confidence, tier = key
        fully_known = values["unknown_event_n"] == 0
        rows.append({
            "pr": pr, "model_id": model, "model_vendor": vendor,
            "source_protocol": protocol, "attribution_method": method,
            "association_confidence": confidence, "price_tier": tier,
            "catalog_version": version, "scenario_basis": basis,
            "scenario_status": values.get("unknown_status") or (
                "COMPLETE" if fully_known else "PARTIAL_UNKNOWN_COMPONENTS"
            ),
            "event_n": values["event_n"],
            "fully_priced_event_n": values["event_n"] - values["unknown_event_n"],
            "unknown_event_n": values["unknown_event_n"],
            "known_component_subtotal_usd": (
                str(values["known_component_subtotal_usd"])
                if values["known_component_subtotal_usd"] is not None else None
            ),
            "token_totals_by_bucket": {
                name: str(value)
                for name, value in sorted(
                    values.get("token_totals_by_bucket", {}).items()
                )
            },
            "unknown_token_buckets": sorted(values.get("unknown_token_buckets", set())),
            "scenario_cost_usd": (
                str(values["scenario_cost_usd"]) if fully_known else None
            ),
            "observed_cost_usd": None,
            "unknown_buckets": sorted(values["unknown_buckets"]),
        })
    rows.sort(key=lambda row: (
        row["pr"], row["model_id"], row["attribution_method"], row["price_tier"]
    ))
    connection.execute(
        "CREATE TEMP TABLE prw_catalog_scenario_pr_metrics ("
        "pr VARCHAR, model_id VARCHAR, model_vendor VARCHAR, source_protocol VARCHAR, "
        "attribution_method VARCHAR, association_confidence VARCHAR, "
        "price_tier VARCHAR, "
        "catalog_version VARCHAR, scenario_basis VARCHAR, scenario_cost_usd "
        "DECIMAL(38, 12))"
    )
    connection.executemany(
        "INSERT INTO prw_catalog_scenario_pr_metrics "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                row["pr"], row["model_id"], row["model_vendor"],
                row["source_protocol"], row["attribution_method"],
                row["association_confidence"], row["price_tier"],
                row["catalog_version"], row["scenario_basis"],
                row["scenario_cost_usd"],
            )
            for row in rows
        ],
    )
    cohort_rows = _query_rows(
        connection,
        "SELECT model_id, model_vendor, source_protocol, attribution_method, "
        "association_confidence, price_tier, catalog_version, scenario_basis, "
        "AVG(scenario_cost_usd) AS average, "
        "quantile_disc(scenario_cost_usd, 0.50) AS p50, "
        "quantile_disc(scenario_cost_usd, 0.90) AS p90, "
        "quantile_disc(scenario_cost_usd, 0.99) AS p99, "
        "COUNT(*) AS observation_n "
        "FROM prw_catalog_scenario_pr_metrics "
        "WHERE scenario_cost_usd IS NOT NULL "
        "GROUP BY ALL "
        "ORDER BY model_id, attribution_method, price_tier",
    )
    return rows, cohort_rows


def run_query(
    *,
    events_path,
    pr_snapshots_path,
    snapshot_at_utc,
    human_summary_path=None,
    attempt_observations_path=None,
    time_metrics_path=None,
    sql_path=None,
    rate_catalog_path=None,
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
        catalog_pr_metrics, catalog_cohorts = _catalog_scenario_summary(
            rate_catalog_path, connection
        )
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
            "catalog_scenario_pr_metrics": catalog_pr_metrics,
            "catalog_scenario_cohorts": catalog_cohorts,
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
        "--rate-catalog",
        help="Optional exact-model public rate catalog; outputs labeled scenarios only",
    )
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
        rate_catalog_path=args.rate_catalog,
    )
    output = json.dumps(result, default=_native_value, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()

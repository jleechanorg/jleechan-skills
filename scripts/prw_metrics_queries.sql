-- DuckDB views over pre-deduplicated PRW events and fixed-field snapshots.
-- Input tables are registered by scripts/prw_metrics_queries.py.

CREATE OR REPLACE TEMP VIEW prw_parameters AS
SELECT
    snapshot_at_utc,
    window_start_utc
FROM prw_query_parameters;

CREATE OR REPLACE TEMP VIEW prw_pr_snapshot_parsed AS
SELECT
    COALESCE(
        json_extract_string(json, '$.repo'),
        json_extract_string(json, '$.repository')
    ) AS repository,
    TRY_CAST(json_extract_string(json, '$.number') AS BIGINT) AS pr_number,
    UPPER(CASE WHEN COALESCE(
        json_extract_string(json, '$.mergedAt'),
        json_extract_string(json, '$.merged_at_utc')
    ) IS NOT NULL THEN 'MERGED' ELSE COALESCE(
        json_extract_string(json, '$.state'),
        json_extract_string(json, '$.pr_state')
    ) END) AS pr_state,
    COALESCE(
        json_extract_string(json, '$.headRefName'),
        json_extract_string(json, '$.head_branch')
    ) AS head_branch,
    COALESCE(
        json_extract_string(json, '$.baseRefName'),
        json_extract_string(json, '$.base_branch')
    ) AS base_branch,
    COALESCE(
        json_extract_string(json, '$.headRefOid'),
        json_extract_string(json, '$.head_sha')
    ) AS head_sha,
    TRY_CAST(COALESCE(
        json_extract_string(json, '$.createdAt'),
        json_extract_string(json, '$.created_at_utc')
    ) AS TIMESTAMPTZ) AS created_at_utc,
    TRY_CAST(COALESCE(
        json_extract_string(json, '$.mergedAt'),
        json_extract_string(json, '$.merged_at_utc')
    ) AS TIMESTAMPTZ) AS merged_at_utc,
    TRY_CAST(COALESCE(
        json_extract_string(json, '$.closedAt'),
        json_extract_string(json, '$.closed_at_utc')
    ) AS TIMESTAMPTZ) AS closed_at_utc,
    TRY_CAST(json_extract_string(json, '$.additions') AS BIGINT) AS additions,
    TRY_CAST(json_extract_string(json, '$.deletions') AS BIGINT) AS deletions
FROM prw_input_pr_snapshots;

CREATE OR REPLACE TEMP VIEW prw_pr_snapshot AS
SELECT
    repository,
    pr_number,
    COUNT(*) AS snapshot_record_n,
    COUNT(DISTINCT pr_state) > 1
        OR COUNT(DISTINCT head_branch) > 1
        OR COUNT(DISTINCT base_branch) > 1
        OR COUNT(DISTINCT head_sha) > 1
        OR COUNT(DISTINCT created_at_utc) > 1
        OR COUNT(DISTINCT merged_at_utc) > 1
        OR COUNT(DISTINCT closed_at_utc) > 1 AS snapshot_conflict,
    CASE WHEN COUNT(DISTINCT pr_state) <= 1 THEN MIN(pr_state) END AS pr_state,
    CASE WHEN COUNT(DISTINCT head_branch) <= 1 THEN MIN(head_branch) END AS head_branch,
    CASE WHEN COUNT(DISTINCT base_branch) <= 1 THEN MIN(base_branch) END AS base_branch,
    CASE WHEN COUNT(DISTINCT head_sha) <= 1 THEN MIN(head_sha) END AS head_sha,
    CASE WHEN COUNT(DISTINCT created_at_utc) <= 1 THEN MIN(created_at_utc) END
        AS created_at_utc,
    CASE WHEN COUNT(DISTINCT merged_at_utc) <= 1 THEN MIN(merged_at_utc) END
        AS merged_at_utc,
    CASE WHEN COUNT(DISTINCT closed_at_utc) <= 1 THEN MIN(closed_at_utc) END
        AS closed_at_utc,
    CASE WHEN COUNT(DISTINCT additions) <= 1 THEN MIN(additions) END AS additions,
    CASE WHEN COUNT(DISTINCT deletions) <= 1 THEN MIN(deletions) END AS deletions
FROM prw_pr_snapshot_parsed
WHERE repository IS NOT NULL AND pr_number IS NOT NULL
GROUP BY repository, pr_number;

CREATE OR REPLACE TEMP VIEW prw_in_scope_prs AS
SELECT
    p.*,
    q.snapshot_at_utc,
    q.window_start_utc,
    CASE
        WHEN p.merged_at_utc IS NOT NULL THEN p.merged_at_utc
        WHEN p.pr_state = 'OPEN' THEN q.snapshot_at_utc
        ELSE p.closed_at_utc
    END AS elapsed_end_at_utc,
    CASE
        WHEN p.merged_at_utc IS NOT NULL THEN 'MERGED_AT'
        WHEN p.pr_state = 'OPEN' THEN 'SNAPSHOT_AT_RIGHT_CENSORED'
        WHEN p.closed_at_utc IS NOT NULL THEN 'CLOSED_AT'
        ELSE 'UNKNOWN'
    END AS pr_elapsed_basis
FROM prw_pr_snapshot p
CROSS JOIN prw_parameters q
WHERE p.pr_state = 'OPEN'
   OR (p.merged_at_utc >= q.window_start_utc AND p.merged_at_utc < q.snapshot_at_utc)
   OR (p.closed_at_utc >= q.window_start_utc AND p.closed_at_utc < q.snapshot_at_utc)
   OR (p.created_at_utc >= q.window_start_utc AND p.created_at_utc < q.snapshot_at_utc);

CREATE OR REPLACE TEMP VIEW prw_pr_elapsed AS
SELECT
    *,
    CASE
        WHEN created_at_utc IS NOT NULL AND elapsed_end_at_utc IS NOT NULL
        THEN EPOCH(elapsed_end_at_utc) - EPOCH(created_at_utc)
        ELSE NULL
    END AS pr_elapsed_seconds,
    CASE
        WHEN snapshot_conflict THEN 'CONFLICT'
        WHEN created_at_utc IS NULL OR elapsed_end_at_utc IS NULL THEN 'UNKNOWN'
        ELSE 'OBSERVED'
    END AS pr_elapsed_coverage
FROM prw_in_scope_prs;

CREATE OR REPLACE TEMP VIEW prw_events_parsed AS
SELECT
    json_extract_string(json, '$.event_id') AS event_id,
    json_extract_string(json, '$.source_id') AS source_id,
    json_extract_string(json, '$.provider') AS provider,
    json_extract_string(json, '$.model') AS model,
    TRY_CAST(json_extract_string(json, '$.timestamp') AS TIMESTAMPTZ)
        AS observed_at_utc,
    json_extract_string(json, '$.session_id_hash') AS session_id_hash,
    COALESCE(TRY_CAST(json_extract_string(json, '$.token_complete') AS BOOLEAN), FALSE)
        AS token_complete,
    TRY_CAST(json_extract_string(json, '$.total_tokens') AS DOUBLE) AS total_tokens,
    TRY_CAST(json_extract_string(json, '$.request_duration_seconds') AS DOUBLE)
        AS request_duration_seconds,
    TRY_CAST(json_extract_string(json, '$.reasoning_output_tokens') AS BIGINT)
        AS reasoning_output_tokens,
    TRY_CAST(COALESCE(
        json_extract_string(json, '$.output_tokens'),
        json_extract_string(json, '$.tokens_by_bucket.output')
    ) AS BIGINT) AS output_tokens,
    TRY_CAST(json_extract_string(json, '$.tokens_by_bucket.input_uncached') AS BIGINT)
        AS uncached_input_tokens,
    TRY_CAST(json_extract_string(json, '$.tokens_by_bucket.cache_read') AS BIGINT)
        AS cache_read_input_tokens,
    TRY_CAST(json_extract_string(json, '$.tokens_by_bucket.cache_write_5m') AS BIGINT)
        AS cache_write_5m_input_tokens,
    TRY_CAST(json_extract_string(json, '$.tokens_by_bucket.cache_write_1h') AS BIGINT)
        AS cache_write_1h_input_tokens,
    TRY_CAST(json_extract_string(json, '$.cache_write_input_tokens') AS BIGINT)
        AS cache_write_input_tokens,
    TRY_CAST(json_extract_string(json, '$.list_equivalent_cost_usd') AS DECIMAL(38, 12))
        AS list_equivalent_cost_amount,
    json_extract_string(json, '$.cost_currency') AS list_equivalent_cost_currency,
    json_extract_string(json, '$.cost_basis') AS list_equivalent_cost_basis,
    json_extract_string(json, '$.price_catalog_version') AS price_catalog_version,
    TRY_CAST(json_extract_string(json, '$.observed_cost_usd') AS DECIMAL(38, 12))
        AS observed_cost_amount,
    json_extract_string(json, '$.observed_cost_currency') AS observed_cost_currency,
    json_extract_string(json, '$.observed_cost_basis') AS observed_cost_basis,
    json_extract_string(json, '$.cost_status') AS cost_status,
    json_extract(json, '$.validated_attributions') AS validated_attributions,
    json_extract(json, '$.branch_attributions') AS branch_attributions,
    json
FROM prw_input_events;

CREATE OR REPLACE TEMP VIEW prw_explicit_attributions AS
SELECT
    e.* EXCLUDE (validated_attributions, branch_attributions, json),
    json_extract_string(a.value, '$.pr') AS attributed_pr,
    TRY_CAST(json_extract_string(a.value, '$.weight') AS DOUBLE) AS attribution_weight,
    json_extract_string(a.value, '$.method') AS attribution_method,
    json_extract_string(a.value, '$.basis') AS attribution_basis,
    json_extract_string(a.value, '$.convention_ref') AS convention_ref
FROM prw_events_parsed e
CROSS JOIN LATERAL json_each(
    COALESCE(e.validated_attributions, '[]'::JSON)
) AS a;

CREATE OR REPLACE TEMP VIEW prw_direct_attributions AS
SELECT
    *,
    split_part(attributed_pr, '#', 1) AS repository,
    TRY_CAST(split_part(attributed_pr, '#', 2) AS BIGINT) AS pr_number,
    total_tokens * attribution_weight AS weighted_total_tokens,
    request_duration_seconds * attribution_weight AS weighted_request_duration_seconds
FROM prw_explicit_attributions
WHERE attribution_method = 'direct'
  AND attributed_pr IS NOT NULL
  AND attribution_weight IS NOT NULL;

CREATE OR REPLACE TEMP VIEW prw_convention_attributions AS
SELECT
    *,
    split_part(attributed_pr, '#', 1) AS repository,
    TRY_CAST(split_part(attributed_pr, '#', 2) AS BIGINT) AS pr_number,
    total_tokens * attribution_weight AS weighted_total_tokens,
    request_duration_seconds * attribution_weight AS weighted_request_duration_seconds
FROM prw_explicit_attributions
WHERE attribution_method = 'convention'
  AND attributed_pr IS NOT NULL
  AND attribution_weight IS NOT NULL;

CREATE OR REPLACE TEMP VIEW prw_source_branch_attributions AS
SELECT
    e.* EXCLUDE (validated_attributions, branch_attributions, json),
    json_extract_string(a.value, '$.pr') AS attributed_pr,
    TRY_CAST(json_extract_string(a.value, '$.weight') AS DOUBLE) AS attribution_weight,
    total_tokens * TRY_CAST(json_extract_string(a.value, '$.weight') AS DOUBLE)
        AS weighted_total_tokens,
    json_extract_string(a.value, '$.basis') AS attribution_basis,
    json_extract_string(a.value, '$.confidence') AS association_confidence
FROM prw_events_parsed e
CROSS JOIN LATERAL json_each(
    COALESCE(e.branch_attributions, '[]'::JSON)
) AS a
WHERE json_extract_string(a.value, '$.pr') IS NOT NULL;

CREATE OR REPLACE TEMP VIEW prw_direct_usage_by_pr AS
SELECT
    repository,
    pr_number,
    COUNT(*) AS direct_usage_observation_count,
    COUNT(*) FILTER (WHERE total_tokens IS NOT NULL) AS direct_token_complete_observation_n,
    SUM(uncached_input_tokens * attribution_weight) AS direct_uncached_input_tokens,
    COUNT(uncached_input_tokens) AS direct_uncached_input_observation_n,
    SUM(cache_read_input_tokens * attribution_weight) AS direct_cache_read_input_tokens,
    COUNT(cache_read_input_tokens) AS direct_cache_read_observation_n,
    SUM(cache_write_5m_input_tokens * attribution_weight)
        AS direct_cache_write_5m_input_tokens,
    COUNT(cache_write_5m_input_tokens) AS direct_cache_write_5m_observation_n,
    SUM(cache_write_1h_input_tokens * attribution_weight)
        AS direct_cache_write_1h_input_tokens,
    COUNT(cache_write_1h_input_tokens) AS direct_cache_write_1h_observation_n,
    SUM(cache_write_input_tokens * attribution_weight) AS direct_cache_write_input_tokens,
    COUNT(cache_write_input_tokens) AS direct_cache_write_observation_n,
    SUM(output_tokens * attribution_weight) AS direct_output_tokens,
    COUNT(output_tokens) AS direct_output_observation_n,
    SUM(reasoning_output_tokens * attribution_weight) AS direct_reasoning_output_tokens,
    COUNT(reasoning_output_tokens) AS direct_reasoning_output_observation_n,
    SUM(weighted_total_tokens) AS direct_total_tokens,
    AVG(weighted_total_tokens) FILTER (WHERE weighted_total_tokens IS NOT NULL)
        AS direct_request_total_tokens_average,
    QUANTILE_DISC(weighted_total_tokens, 0.50)
        FILTER (WHERE weighted_total_tokens IS NOT NULL)
        AS direct_request_total_tokens_p50,
    QUANTILE_DISC(weighted_total_tokens, 0.90)
        FILTER (WHERE weighted_total_tokens IS NOT NULL)
        AS direct_request_total_tokens_p90,
    QUANTILE_DISC(weighted_total_tokens, 0.99)
        FILTER (WHERE weighted_total_tokens IS NOT NULL)
        AS direct_request_total_tokens_p99,
    COUNT(weighted_total_tokens) AS direct_request_total_tokens_n,
    AVG(weighted_request_duration_seconds)
        FILTER (WHERE weighted_request_duration_seconds IS NOT NULL)
        AS direct_request_duration_average_seconds,
    QUANTILE_DISC(weighted_request_duration_seconds, 0.50)
        FILTER (WHERE weighted_request_duration_seconds IS NOT NULL)
        AS direct_request_duration_p50_seconds,
    QUANTILE_DISC(weighted_request_duration_seconds, 0.90)
        FILTER (WHERE weighted_request_duration_seconds IS NOT NULL)
        AS direct_request_duration_p90_seconds,
    QUANTILE_DISC(weighted_request_duration_seconds, 0.99)
        FILTER (WHERE weighted_request_duration_seconds IS NOT NULL)
        AS direct_request_duration_p99_seconds,
    COUNT(weighted_request_duration_seconds) AS direct_request_duration_n,
    SUM(list_equivalent_cost_amount * attribution_weight)
        AS direct_list_equivalent_cost_amount,
    COUNT(*) FILTER (WHERE cost_status = 'priced') AS direct_fully_priced_observation_n,
    COUNT(*) FILTER (WHERE cost_status = 'partial') AS direct_partially_priced_observation_n,
    COUNT(*) FILTER (WHERE cost_status = 'UNKNOWN_NO_RATE_CARD')
        AS direct_no_rate_card_observation_n,
    CASE WHEN COUNT(DISTINCT list_equivalent_cost_currency) <= 1
        THEN MIN(list_equivalent_cost_currency) END AS direct_list_equivalent_cost_currency,
    CASE WHEN COUNT(DISTINCT list_equivalent_cost_basis) <= 1
        THEN MIN(list_equivalent_cost_basis) END AS direct_list_equivalent_cost_basis,
    CASE WHEN COUNT(DISTINCT price_catalog_version) <= 1
        THEN MIN(price_catalog_version) END AS direct_price_catalog_version,
    STRING_AGG(DISTINCT attribution_method, ',') AS direct_association_method,
    STRING_AGG(DISTINCT attribution_basis, ',') AS direct_association_basis,
    'DIRECT_VALIDATED' AS direct_association_confidence,
    COUNT(*) FILTER (WHERE observed_cost_amount IS NOT NULL)
        AS direct_observed_cost_observation_n,
    SUM(observed_cost_amount * attribution_weight) AS direct_observed_cost_amount,
    CASE WHEN COUNT(DISTINCT observed_cost_currency) <= 1
        THEN MIN(observed_cost_currency) END AS direct_observed_cost_currency,
    CASE WHEN COUNT(DISTINCT observed_cost_basis) <= 1
        THEN MIN(observed_cost_basis) END AS direct_observed_cost_basis
FROM prw_direct_attributions
GROUP BY repository, pr_number;

CREATE OR REPLACE TEMP VIEW prw_convention_usage_by_pr AS
SELECT
    repository,
    pr_number,
    COUNT(*) AS convention_usage_observation_count,
    SUM(weighted_total_tokens) AS convention_total_tokens,
    SUM(list_equivalent_cost_amount * attribution_weight)
        AS convention_list_equivalent_cost_amount
FROM prw_convention_attributions
GROUP BY repository, pr_number;

CREATE OR REPLACE TEMP VIEW prw_branch_usage_by_pr AS
SELECT
    split_part(attributed_pr, '#', 1) AS repository,
    TRY_CAST(split_part(attributed_pr, '#', 2) AS BIGINT) AS pr_number,
    COUNT(*) AS branch_usage_observation_count,
    SUM(uncached_input_tokens * attribution_weight) AS branch_uncached_input_tokens,
    SUM(cache_read_input_tokens * attribution_weight) AS branch_cache_read_input_tokens,
    SUM(cache_write_5m_input_tokens * attribution_weight)
        AS branch_cache_write_5m_input_tokens,
    SUM(cache_write_1h_input_tokens * attribution_weight)
        AS branch_cache_write_1h_input_tokens,
    SUM(output_tokens * attribution_weight) AS branch_output_tokens,
    SUM(weighted_total_tokens) AS branch_total_tokens,
    SUM(list_equivalent_cost_amount * attribution_weight)
        AS branch_list_equivalent_cost_amount,
    STRING_AGG(DISTINCT attribution_basis, ',') AS branch_association_basis,
    STRING_AGG(DISTINCT association_confidence, ',') AS branch_association_confidence
FROM prw_source_branch_attributions
GROUP BY repository, pr_number;

CREATE OR REPLACE TEMP VIEW prw_query_coverage AS
SELECT
    COUNT(*) AS canonical_event_n,
    COUNT(*) FILTER (
        WHERE COALESCE(TRY_CAST(json_extract_string(json, '$.request_id_present') AS BOOLEAN), FALSE) = FALSE
    ) AS missing_request_id_n,
    COUNT(*) FILTER (
        WHERE COALESCE(TRY_CAST(json_extract_string(json, '$.dedup_conflict') AS BOOLEAN), FALSE)
    ) AS dedup_conflict_event_n,
    COUNT(*) FILTER (
        WHERE COALESCE(TRY_CAST(json_extract_string(json, '$.source_conflict') AS BOOLEAN), FALSE)
    ) AS source_conflict_event_n,
    COUNT(*) FILTER (
        WHERE json_extract_string(json, '$.attribution_status') = 'VALIDATED'
    ) AS validated_direct_attribution_event_n,
    COUNT(*) FILTER (
        WHERE json_extract_string(json, '$.attribution_status') = 'UNBOUND'
    ) AS unbound_event_n,
    COUNT(*) FILTER (
        WHERE json_extract_string(json, '$.attribution_status') = 'INVALID_OR_UNSUPPORTED'
    ) AS invalid_attribution_event_n,
    (SELECT json_extract_string(h.json, '$.coverage.branch_metadata_coverage')
     FROM prw_input_human_summary h LIMIT 1) AS branch_metadata_coverage
FROM prw_events_parsed;

CREATE OR REPLACE TEMP VIEW prw_human_per_pr_rows AS
SELECT
    split_part(json_extract_string(person.value, '$.pr'), '#', 1) AS repository,
    TRY_CAST(split_part(json_extract_string(person.value, '$.pr'), '#', 2) AS BIGINT)
        AS pr_number,
    TRY_CAST(json_extract_string(person.value, '$.raw_verified_messages') AS BIGINT)
        AS raw_verified_human_message_count,
    TRY_CAST(json_extract_string(person.value, '$.direct_verified_messages') AS BIGINT)
        AS direct_verified_human_message_count,
    TRY_CAST(json_extract_string(person.value, '$.branch_associated_verified_messages') AS BIGINT)
        AS branch_associated_verified_human_message_count,
    TRY_CAST(json_extract_string(person.value, '$.direct_candidates') AS BIGINT)
        AS direct_candidates,
    TRY_CAST(json_extract_string(person.value, '$.branch_associated_candidates') AS BIGINT)
        AS branch_associated_candidates,
    TRY_CAST(json_extract_string(person.value, '$.initial_requests') AS BIGINT)
        AS verified_initial_human_message_count,
    TRY_CAST(json_extract_string(person.value, '$.verified_followup_messages') AS BIGINT)
        AS verified_followup_human_message_count,
    TRY_CAST(json_extract_string(person.value, '$.followup_episodes') AS BIGINT)
        AS reviewed_followup_episode_count,
    TRY_CAST(json_extract_string(person.value, '$.episodes_by_quality.good') AS BIGINT)
        AS good_episode_count,
    TRY_CAST(json_extract_string(person.value, '$.episodes_by_quality.bad') AS BIGINT)
        AS bad_episode_count,
    TRY_CAST(json_extract_string(person.value, '$.episodes_by_quality.mixed') AS BIGINT)
        AS mixed_episode_count,
    TRY_CAST(json_extract_string(person.value, '$.episodes_by_quality.unknown') AS BIGINT)
        AS unknown_episode_count,
    TRY_CAST(json_extract_string(person.value, '$.unlabelled_episode_count') AS BIGINT)
        AS unlabelled_episode_count,
    json_extract(person.value, '$.association_basis') AS association_basis,
    json_extract_string(person.value, '$.association_confidence') AS association_confidence,
    json_extract_string(person.value, '$.coverage_status') AS human_coverage_status
FROM prw_input_human_summary h
CROSS JOIN LATERAL json_each(COALESCE(json_extract(h.json, '$.per_pr'), '[]'::JSON)) person
WHERE json_extract_string(person.value, '$.pr') IS NOT NULL;

CREATE OR REPLACE TEMP VIEW prw_human_per_pr AS
SELECT
    repository,
    pr_number,
    COUNT(*) > 1 AND (
        COUNT(DISTINCT raw_verified_human_message_count) > 1
        OR COUNT(DISTINCT direct_verified_human_message_count) > 1
        OR COUNT(DISTINCT branch_associated_verified_human_message_count) > 1
        OR COUNT(DISTINCT direct_candidates) > 1
        OR COUNT(DISTINCT branch_associated_candidates) > 1
        OR COUNT(DISTINCT verified_initial_human_message_count) > 1
        OR COUNT(DISTINCT verified_followup_human_message_count) > 1
        OR COUNT(DISTINCT reviewed_followup_episode_count) > 1
    ) AS human_summary_conflict,
    CASE WHEN COUNT(DISTINCT human_coverage_status) = 1
              AND MIN(human_coverage_status) = 'OBSERVED_SCOPE_ONLY'
              AND COUNT(DISTINCT raw_verified_human_message_count) <= 1
        THEN MIN(raw_verified_human_message_count) END AS raw_verified_human_message_count,
    CASE WHEN COUNT(DISTINCT direct_verified_human_message_count) <= 1
        THEN MIN(direct_verified_human_message_count) END AS direct_verified_human_message_count,
    CASE WHEN COUNT(DISTINCT branch_associated_verified_human_message_count) <= 1
        THEN MIN(branch_associated_verified_human_message_count) END
        AS branch_associated_verified_human_message_count,
    CASE WHEN COUNT(DISTINCT direct_candidates) <= 1
        THEN MIN(direct_candidates) END AS direct_candidates,
    CASE WHEN COUNT(DISTINCT branch_associated_candidates) <= 1
        THEN MIN(branch_associated_candidates) END AS branch_associated_candidates,
    CASE WHEN COUNT(DISTINCT human_coverage_status) = 1
              AND MIN(human_coverage_status) = 'OBSERVED_SCOPE_ONLY'
              AND COUNT(DISTINCT verified_initial_human_message_count) <= 1
        THEN MIN(verified_initial_human_message_count) END
        AS verified_initial_human_message_count,
    CASE WHEN COUNT(DISTINCT human_coverage_status) = 1
              AND MIN(human_coverage_status) = 'OBSERVED_SCOPE_ONLY'
              AND COUNT(DISTINCT verified_followup_human_message_count) <= 1
        THEN MIN(verified_followup_human_message_count) END
        AS verified_followup_human_message_count,
    CASE WHEN COUNT(DISTINCT human_coverage_status) = 1
              AND MIN(human_coverage_status) = 'OBSERVED_SCOPE_ONLY'
              AND COUNT(DISTINCT reviewed_followup_episode_count) <= 1
        THEN MIN(reviewed_followup_episode_count) END AS reviewed_followup_episode_count,
    CASE WHEN COUNT(DISTINCT good_episode_count) <= 1
        THEN MIN(good_episode_count) END AS good_episode_count,
    CASE WHEN COUNT(DISTINCT bad_episode_count) <= 1
        THEN MIN(bad_episode_count) END AS bad_episode_count,
    CASE WHEN COUNT(DISTINCT mixed_episode_count) <= 1
        THEN MIN(mixed_episode_count) END AS mixed_episode_count,
    CASE WHEN COUNT(DISTINCT unknown_episode_count) <= 1
        THEN MIN(unknown_episode_count) END AS unknown_episode_count,
    CASE WHEN COUNT(DISTINCT unlabelled_episode_count) <= 1
        THEN MIN(unlabelled_episode_count) END AS unlabelled_episode_count,
    CASE WHEN COUNT(DISTINCT CAST(association_basis AS VARCHAR)) <= 1
        THEN MIN(CAST(association_basis AS VARCHAR)) END AS association_basis,
    CASE WHEN COUNT(DISTINCT association_confidence) <= 1
        THEN MIN(association_confidence) END AS association_confidence,
    CASE WHEN COUNT(DISTINCT human_coverage_status) <= 1
        THEN MIN(human_coverage_status) END AS human_coverage_status
FROM prw_human_per_pr_rows
GROUP BY repository, pr_number;

CREATE OR REPLACE TEMP VIEW prw_time_metrics AS
SELECT
    COALESCE(json_extract_string(json, '$.repo'),
             json_extract_string(json, '$.repository')) AS repository,
    TRY_CAST(COALESCE(json_extract_string(json, '$.number'),
                      json_extract_string(json, '$.pr_number')) AS BIGINT) AS pr_number,
    TRY_CAST(COALESCE(json_extract_string(json, '$.observed_active_wall_seconds'),
                      json_extract_string(json, '$.observed_active_wall_sec')) AS DOUBLE)
        AS observed_active_wall_seconds,
    json_extract_string(json, '$.observed_active_basis') AS observed_active_basis,
    json_extract_string(json, '$.observed_active_coverage') AS observed_active_coverage,
    TRY_CAST(COALESCE(json_extract_string(json, '$.agent_effort_seconds'),
                      json_extract_string(json, '$.agent_effort_sec')) AS DOUBLE)
        AS agent_effort_seconds,
    json_extract_string(json, '$.agent_effort_basis') AS agent_effort_basis,
    json_extract_string(json, '$.agent_effort_coverage') AS agent_effort_coverage,
    TRY_CAST(COALESCE(json_extract_string(json, '$.eligible_idle_seconds'),
                      json_extract_string(json, '$.eligible_unattended_duration_sec')) AS DOUBLE)
        AS eligible_idle_seconds,
    json_extract_string(json, '$.eligible_idle_basis') AS eligible_idle_basis,
    json_extract_string(json, '$.eligible_idle_coverage') AS eligible_idle_coverage
FROM prw_input_time_metrics
WHERE COALESCE(json_extract_string(json, '$.repo'),
               json_extract_string(json, '$.repository')) IS NOT NULL;

CREATE OR REPLACE TEMP VIEW prw_time_metrics_by_pr AS
SELECT
    repository,
    pr_number,
    COUNT(*) > 1 AND (
        COUNT(DISTINCT observed_active_wall_seconds) > 1
        OR COUNT(DISTINCT agent_effort_seconds) > 1
        OR COUNT(DISTINCT eligible_idle_seconds) > 1
    ) AS time_metrics_conflict,
    CASE WHEN COUNT(DISTINCT observed_active_wall_seconds) <= 1
        THEN MIN(observed_active_wall_seconds) END AS observed_active_wall_seconds,
    CASE WHEN COUNT(DISTINCT observed_active_basis) <= 1
        THEN MIN(observed_active_basis) END AS observed_active_basis,
    CASE WHEN COUNT(DISTINCT observed_active_coverage) <= 1
        THEN MIN(observed_active_coverage) END AS observed_active_coverage,
    CASE WHEN COUNT(DISTINCT agent_effort_seconds) <= 1
        THEN MIN(agent_effort_seconds) END AS agent_effort_seconds,
    CASE WHEN COUNT(DISTINCT agent_effort_basis) <= 1
        THEN MIN(agent_effort_basis) END AS agent_effort_basis,
    CASE WHEN COUNT(DISTINCT agent_effort_coverage) <= 1
        THEN MIN(agent_effort_coverage) END AS agent_effort_coverage,
    CASE WHEN COUNT(DISTINCT eligible_idle_seconds) <= 1
        THEN MIN(eligible_idle_seconds) END AS eligible_idle_seconds,
    CASE WHEN COUNT(DISTINCT eligible_idle_basis) <= 1
        THEN MIN(eligible_idle_basis) END AS eligible_idle_basis,
    CASE WHEN COUNT(DISTINCT eligible_idle_coverage) <= 1
        THEN MIN(eligible_idle_coverage) END AS eligible_idle_coverage
FROM prw_time_metrics
GROUP BY repository, pr_number;

CREATE OR REPLACE TEMP VIEW prw_review_attempts AS
SELECT
    COALESCE(json_extract_string(json, '$.repo'),
             json_extract_string(json, '$.repository')) AS repository,
    TRY_CAST(COALESCE(json_extract_string(json, '$.number'),
                      json_extract_string(json, '$.pr_number')) AS BIGINT) AS pr_number,
    COALESCE(json_extract_string(json, '$.attempt_id'),
             json_extract_string(json, '$.attempt_number'),
             json_extract_string(json, '$.attempt')) AS attempt_id,
    COALESCE(json_extract_string(json, '$.transition'),
             json_extract_string(json, '$.name')) AS transition,
    TRY_CAST(COALESCE(json_extract_string(json, '$.duration_seconds'),
                      json_extract_string(json, '$.duration_sec')) AS DOUBLE)
        AS duration_seconds,
    json_extract_string(json, '$.duration_basis') AS duration_basis,
    json_extract_string(json, '$.duration_coverage') AS duration_coverage
FROM prw_input_attempts
WHERE COALESCE(json_extract_string(json, '$.repo'),
               json_extract_string(json, '$.repository')) IS NOT NULL;

CREATE OR REPLACE TEMP VIEW prw_attempts_by_pr AS
SELECT
    repository,
    pr_number,
    COUNT(*) AS review_attempt_observation_n,
    COUNT(duration_seconds) AS review_attempt_duration_n,
    AVG(duration_seconds) FILTER (WHERE duration_seconds IS NOT NULL)
        AS review_attempt_duration_average_seconds,
    QUANTILE_DISC(duration_seconds, 0.50)
        FILTER (WHERE duration_seconds IS NOT NULL)
        AS review_attempt_duration_p50_seconds,
    QUANTILE_DISC(duration_seconds, 0.90)
        FILTER (WHERE duration_seconds IS NOT NULL)
        AS review_attempt_duration_p90_seconds,
    QUANTILE_DISC(duration_seconds, 0.99)
        FILTER (WHERE duration_seconds IS NOT NULL)
        AS review_attempt_duration_p99_seconds,
    COUNT(DISTINCT attempt_id) AS distinct_review_attempt_n,
    CASE WHEN COUNT(DISTINCT duration_basis) <= 1 THEN MIN(duration_basis) END
        AS review_attempt_duration_basis,
    CASE WHEN COUNT(DISTINCT duration_coverage) <= 1 THEN MIN(duration_coverage) END
        AS review_attempt_duration_coverage
FROM prw_review_attempts
GROUP BY repository, pr_number;

CREATE OR REPLACE TEMP TABLE prw_per_pr_metrics AS
SELECT
    p.snapshot_at_utc,
    p.repository,
    p.pr_number,
    p.pr_state,
    p.head_branch,
    p.base_branch,
    p.head_sha,
    p.created_at_utc,
    p.merged_at_utc,
    p.closed_at_utc,
    CASE WHEN p.snapshot_conflict THEN 'CONFLICT'
         WHEN p.created_at_utc IS NULL OR p.pr_state IS NULL THEN 'PARTIAL'
         ELSE 'OBSERVED' END AS metadata_coverage,
    p.pr_elapsed_seconds,
    p.pr_elapsed_basis,
    p.pr_elapsed_coverage,
    t.observed_active_wall_seconds,
    t.observed_active_basis,
    t.observed_active_coverage,
    t.agent_effort_seconds,
    t.agent_effort_basis,
    t.agent_effort_coverage,
    t.eligible_idle_seconds,
    t.eligible_idle_basis,
    t.eligible_idle_coverage,
    COALESCE(d.direct_usage_observation_count, 0) AS direct_usage_observation_count,
    d.direct_token_complete_observation_n,
    d.direct_uncached_input_tokens,
    d.direct_uncached_input_observation_n,
    d.direct_cache_read_input_tokens,
    d.direct_cache_read_observation_n,
    d.direct_cache_write_5m_input_tokens,
    d.direct_cache_write_5m_observation_n,
    d.direct_cache_write_1h_input_tokens,
    d.direct_cache_write_1h_observation_n,
    d.direct_cache_write_input_tokens,
    d.direct_cache_write_observation_n,
    d.direct_output_tokens,
    d.direct_output_observation_n,
    d.direct_reasoning_output_tokens,
    d.direct_reasoning_output_observation_n,
    d.direct_total_tokens,
    c.convention_usage_observation_count,
    c.convention_total_tokens,
    d.direct_request_total_tokens_average,
    d.direct_request_total_tokens_p50,
    d.direct_request_total_tokens_p90,
    d.direct_request_total_tokens_p99,
    COALESCE(d.direct_request_total_tokens_n, 0) AS direct_request_total_tokens_n,
    d.direct_request_duration_average_seconds,
    d.direct_request_duration_p50_seconds,
    d.direct_request_duration_p90_seconds,
    d.direct_request_duration_p99_seconds,
    COALESCE(d.direct_request_duration_n, 0) AS direct_request_duration_n,
    CASE WHEN COALESCE(d.direct_usage_observation_count, 0) = 0 THEN NULL
         ELSE d.direct_token_complete_observation_n * 1.0 / d.direct_usage_observation_count
    END AS direct_token_coverage,
    CASE WHEN COALESCE(d.direct_usage_observation_count, 0) = 0 THEN NULL
         ELSE d.direct_token_complete_observation_n * 1.0 / d.direct_usage_observation_count
    END AS token_coverage,
    CASE WHEN COALESCE(d.direct_usage_observation_count, 0) = 0
         THEN 'UNKNOWN_NO_DIRECT_USAGE'
         WHEN COALESCE(d.direct_token_complete_observation_n, 0) = 0 THEN 'UNKNOWN'
         WHEN d.direct_token_complete_observation_n < d.direct_usage_observation_count
         THEN 'PARTIAL'
         ELSE 'OBSERVED_SCOPE_ONLY' END AS usage_status,
    d.direct_list_equivalent_cost_amount,
    d.direct_list_equivalent_cost_currency,
    d.direct_list_equivalent_cost_basis,
    d.direct_price_catalog_version,
    d.direct_list_equivalent_cost_amount AS list_equivalent_cost_amount,
    d.direct_list_equivalent_cost_currency AS list_equivalent_cost_currency,
    d.direct_list_equivalent_cost_basis AS list_equivalent_cost_basis,
    d.direct_price_catalog_version AS price_catalog_version,
    d.direct_fully_priced_observation_n,
    d.direct_partially_priced_observation_n,
    d.direct_no_rate_card_observation_n,
    CASE WHEN COALESCE(d.direct_usage_observation_count, 0) = 0 THEN NULL
         ELSE COALESCE(d.direct_fully_priced_observation_n, 0) * 1.0
              / d.direct_usage_observation_count
    END AS direct_cost_coverage,
    CASE WHEN COALESCE(d.direct_usage_observation_count, 0) = 0 THEN NULL
         ELSE COALESCE(d.direct_fully_priced_observation_n, 0) * 1.0
              / d.direct_usage_observation_count
    END AS cost_coverage,
    CASE WHEN COALESCE(d.direct_usage_observation_count, 0) = 0
         THEN 'UNKNOWN_NO_DIRECT_USAGE'
         WHEN COALESCE(d.direct_no_rate_card_observation_n, 0)
              = d.direct_usage_observation_count THEN 'UNKNOWN_NO_RATE_CARD'
         WHEN COALESCE(d.direct_partially_priced_observation_n, 0) > 0 THEN 'PARTIAL'
         WHEN COALESCE(d.direct_fully_priced_observation_n, 0)
              = d.direct_usage_observation_count THEN 'OBSERVED_LIST_EQUIVALENT'
         ELSE 'UNKNOWN' END AS cost_status,
    d.direct_observed_cost_amount,
    d.direct_observed_cost_currency,
    d.direct_observed_cost_basis,
    d.direct_observed_cost_amount AS observed_cost_amount,
    d.direct_observed_cost_currency AS observed_cost_currency,
    d.direct_observed_cost_basis AS observed_cost_basis,
    d.direct_association_method,
    d.direct_association_basis,
    d.direct_association_confidence,
    a.review_attempt_observation_n,
    a.review_attempt_duration_n,
    a.review_attempt_duration_average_seconds,
    a.review_attempt_duration_p50_seconds,
    a.review_attempt_duration_p90_seconds,
    a.review_attempt_duration_p99_seconds,
    a.distinct_review_attempt_n,
    a.review_attempt_duration_basis,
    a.review_attempt_duration_coverage,
    CASE WHEN COALESCE(b.branch_usage_observation_count, 0) = 0 THEN NULL
         ELSE b.branch_usage_observation_count END AS branch_usage_observation_count,
    CASE WHEN COALESCE(b.branch_usage_observation_count, 0) = 0
         THEN 'UNKNOWN_NO_CANONICAL_BRANCH_USAGE_ATTRIBUTION'
         ELSE 'OBSERVED_SOURCE_BRANCH_ATTRIBUTION' END AS branch_usage_status,
    b.branch_uncached_input_tokens,
    b.branch_cache_read_input_tokens,
    b.branch_cache_write_5m_input_tokens,
    b.branch_cache_write_1h_input_tokens,
    b.branch_output_tokens,
    b.branch_total_tokens,
    b.branch_list_equivalent_cost_amount,
    b.branch_association_basis,
    COALESCE(b.branch_association_confidence, h.association_confidence)
        AS branch_association_confidence,
    h.raw_verified_human_message_count,
    h.direct_verified_human_message_count,
    h.branch_associated_verified_human_message_count,
    h.direct_candidates,
    h.branch_associated_candidates,
    h.verified_initial_human_message_count,
    h.verified_followup_human_message_count,
    h.reviewed_followup_episode_count,
    h.good_episode_count,
    h.bad_episode_count,
    h.mixed_episode_count,
    h.unknown_episode_count,
    h.unlabelled_episode_count,
    h.association_basis AS human_association_basis,
    CASE WHEN COALESCE(d.direct_usage_observation_count, 0) > 0 THEN 'direct'
         ELSE h.association_confidence END AS association_confidence,
    h.association_confidence AS human_association_confidence,
    h.human_coverage_status,
    h.human_summary_conflict,
    t.time_metrics_conflict
FROM prw_pr_elapsed p
LEFT JOIN prw_direct_usage_by_pr d USING (repository, pr_number)
LEFT JOIN prw_convention_usage_by_pr c USING (repository, pr_number)
LEFT JOIN prw_branch_usage_by_pr b USING (repository, pr_number)
LEFT JOIN prw_human_per_pr h USING (repository, pr_number)
LEFT JOIN prw_time_metrics_by_pr t USING (repository, pr_number)
LEFT JOIN prw_attempts_by_pr a USING (repository, pr_number);

CREATE OR REPLACE TEMP VIEW prw_per_pr_metrics_export AS
SELECT * REPLACE (
    CAST(snapshot_at_utc AS VARCHAR) AS snapshot_at_utc,
    CAST(created_at_utc AS VARCHAR) AS created_at_utc,
    CAST(merged_at_utc AS VARCHAR) AS merged_at_utc,
    CAST(closed_at_utc AS VARCHAR) AS closed_at_utc
)
FROM prw_per_pr_metrics;

CREATE OR REPLACE TEMP TABLE prw_cohort_prs AS
SELECT
    repository,
    pr_number,
    'all_14d_merges' AS cohort_definition,
    pr_elapsed_seconds
FROM prw_per_pr_metrics p
CROSS JOIN prw_parameters q
WHERE p.merged_at_utc >= q.window_start_utc AND p.merged_at_utc < q.snapshot_at_utc
UNION ALL
SELECT
    repository,
    pr_number,
    'comparable_created_to_merge_le_7d' AS cohort_definition,
    pr_elapsed_seconds
FROM prw_per_pr_metrics p
CROSS JOIN prw_parameters q
WHERE p.merged_at_utc >= q.window_start_utc AND p.merged_at_utc < q.snapshot_at_utc
  AND p.pr_elapsed_seconds <= 604800
UNION ALL
SELECT
    repository,
    pr_number,
    'historical_backlog_gt_7d' AS cohort_definition,
    pr_elapsed_seconds
FROM prw_per_pr_metrics p
CROSS JOIN prw_parameters q
WHERE p.merged_at_utc >= q.window_start_utc AND p.merged_at_utc < q.snapshot_at_utc
  AND p.pr_elapsed_seconds > 604800;

CREATE OR REPLACE TEMP VIEW prw_low_usage_by_pr AS
SELECT
    split_part(attributed_pr, '#', 1) AS repository,
    TRY_CAST(split_part(attributed_pr, '#', 2) AS BIGINT) AS pr_number,
    SUM(weighted_total_tokens) AS low_total_tokens
FROM prw_source_branch_attributions
GROUP BY 1, 2;

CREATE OR REPLACE TEMP TABLE prw_metric_observations AS
SELECT
    repository,
    pr_number,
    cohort_definition,
    'pr_elapsed' AS metric_family,
    'pr_elapsed_seconds' AS measure,
    pr_elapsed_seconds AS value,
    'seconds' AS unit,
    'per_pr_row' AS average_basis
FROM prw_cohort_prs
UNION ALL
SELECT
    c.repository,
    c.pr_number,
    c.cohort_definition,
    'direct_request' AS metric_family,
    'total_tokens' AS measure,
    a.weighted_total_tokens AS value,
    'tokens' AS unit,
    'request_observation' AS average_basis
FROM prw_cohort_prs c
JOIN prw_direct_attributions a USING (repository, pr_number)
UNION ALL
SELECT
    c.repository,
    c.pr_number,
    c.cohort_definition,
    'direct_per_pr' AS metric_family,
    'total_tokens' AS measure,
    d.direct_total_tokens AS value,
    'tokens' AS unit,
    'per_pr_total' AS average_basis
FROM prw_cohort_prs c
JOIN prw_direct_usage_by_pr d USING (repository, pr_number)
UNION ALL
SELECT
    c.repository,
    c.pr_number,
    c.cohort_definition,
    'low_per_pr' AS metric_family,
    'total_tokens' AS measure,
    l.low_total_tokens AS value,
    'tokens' AS unit,
    'per_pr_total' AS average_basis
FROM prw_cohort_prs c
JOIN prw_low_usage_by_pr l USING (repository, pr_number)
UNION ALL
SELECT
    c.repository,
    c.pr_number,
    c.cohort_definition,
    'low_request' AS metric_family,
    'total_tokens' AS measure,
    a.weighted_total_tokens AS value,
    'tokens' AS unit,
    'request_observation' AS average_basis
FROM prw_cohort_prs c
JOIN prw_source_branch_attributions a
  ON split_part(a.attributed_pr, '#', 1) = c.repository
 AND TRY_CAST(split_part(a.attributed_pr, '#', 2) AS BIGINT) = c.pr_number
UNION ALL
SELECT
    c.repository,
    c.pr_number,
    c.cohort_definition,
    'direct_request' AS metric_family,
    'request_duration_seconds' AS measure,
    a.weighted_request_duration_seconds AS value,
    'seconds' AS unit,
    'request_observation' AS average_basis
FROM prw_cohort_prs c
JOIN prw_direct_attributions a USING (repository, pr_number)
UNION ALL
SELECT
    c.repository,
    c.pr_number,
    c.cohort_definition,
    'review_attempt' AS metric_family,
    'attempt_duration_seconds' AS measure,
    a.duration_seconds AS value,
    'seconds' AS unit,
    'review_attempt_observation' AS average_basis
FROM prw_cohort_prs c
JOIN prw_review_attempts a USING (repository, pr_number);

CREATE OR REPLACE TEMP TABLE prw_cohort_metric_grid AS
SELECT
    r.repository,
    q.snapshot_at_utc,
    c.cohort_definition,
    m.metric_family,
    m.measure,
    m.unit,
    m.average_basis
FROM (SELECT DISTINCT repository FROM prw_per_pr_metrics) r
CROSS JOIN prw_parameters q
CROSS JOIN (
    VALUES ('all_14d_merges'),
           ('comparable_created_to_merge_le_7d'),
           ('historical_backlog_gt_7d')
) AS c(cohort_definition)
CROSS JOIN (
    VALUES ('pr_elapsed', 'pr_elapsed_seconds', 'seconds', 'per_pr_row'),
           ('direct_request', 'total_tokens', 'tokens', 'request_observation'),
           ('direct_per_pr', 'total_tokens', 'tokens', 'per_pr_total'),
           ('low_per_pr', 'total_tokens', 'tokens', 'per_pr_total'),
           ('low_request', 'total_tokens', 'tokens', 'request_observation'),
           ('direct_request', 'request_duration_seconds', 'seconds', 'request_observation'),
           ('review_attempt', 'attempt_duration_seconds', 'seconds', 'review_attempt_observation')
) AS m(metric_family, measure, unit, average_basis);

CREATE OR REPLACE TEMP TABLE prw_metric_cohorts AS
SELECT
    g.repository,
    g.snapshot_at_utc,
    g.cohort_definition,
    g.metric_family,
    g.measure,
    g.unit,
    g.average_basis,
    COUNT(o.value) AS observation_n,
    COUNT(o.pr_number) AS observation_record_n,
    COUNT(DISTINCT o.pr_number) FILTER (WHERE o.value IS NOT NULL) AS distinct_pr_n,
    COUNT(DISTINCT c.pr_number) AS cohort_pr_n,
    AVG(o.value) FILTER (WHERE o.value IS NOT NULL) AS average,
    QUANTILE_DISC(o.value, 0.50) FILTER (WHERE o.value IS NOT NULL) AS p50,
    QUANTILE_DISC(o.value, 0.90) FILTER (WHERE o.value IS NOT NULL) AS p90,
    QUANTILE_DISC(o.value, 0.99) FILTER (WHERE o.value IS NOT NULL) AS p99,
    CASE WHEN COUNT(o.pr_number) = 0 THEN NULL
         ELSE COUNT(o.value) * 1.0 / COUNT(o.pr_number) END AS valid_coverage,
    'quantile_disc_type1_nearest_rank' AS quantile_method,
    CASE WHEN COUNT(o.value) = 0 THEN 'UNKNOWN'
         WHEN COUNT(o.value) < COUNT(o.pr_number) THEN 'PARTIAL'
         ELSE 'OBSERVED_SCOPE_ONLY' END AS coverage_status
FROM prw_cohort_metric_grid g
LEFT JOIN prw_cohort_prs c
    ON c.repository = g.repository AND c.cohort_definition = g.cohort_definition
LEFT JOIN prw_metric_observations o
    ON o.repository = g.repository
   AND o.cohort_definition = g.cohort_definition
   AND o.metric_family = g.metric_family
   AND o.measure = g.measure
   AND o.pr_number = c.pr_number
GROUP BY
    g.repository, g.snapshot_at_utc, g.cohort_definition,
    g.metric_family, g.measure, g.unit, g.average_basis;

CREATE OR REPLACE TEMP VIEW prw_metric_cohorts_export AS
SELECT * REPLACE (
    CAST(snapshot_at_utc AS VARCHAR) AS snapshot_at_utc
)
FROM prw_metric_cohorts;

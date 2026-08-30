# /topcampaigns - Query Top Campaigns by Entry Count

Query Firebase for the longest (most entries) campaigns within a date range.

## Usage

```
/topcampaigns [options]
```

## Prerequisites

Uses `~/serviceAccountKey.json` for Firebase credentials. Make sure you have the correct
credentials for the environment you want to query (production vs staging).

## Options

- `--days N` - Number of days to look back (default: 14)
- `--exclude "pattern"` - Glob pattern for emails to exclude (e.g., "$USER*")
- `--email user@example.com` - Only include campaigns from this email
- `--top N` - Number of top results to show (default: 10)
- `-v, --verbose` - Print progress messages
- `--json` - Output as JSON instead of table

## Examples

### Top 10 non-internal campaigns (last 2 weeks)
```bash
python scripts/top_campaigns.py --days 14 --exclude "$USER*" --top 10 -v
```

### All campaigns for a specific user
```bash
python scripts/top_campaigns.py --email user@example.com --top 50
```

### Top 20 from last month (no exclusions)
```bash
python scripts/top_campaigns.py --days 30 --top 20
```

## Implementation

Run the script with the requested options:

```bash
python scripts/top_campaigns.py $ARGUMENTS
```

## Performance Notes

This script uses the pre-computed `entry_count` field on campaign documents for O(N) performance. It does NOT iterate through history subcollections, making it fast even with thousands of campaigns.

**Why this is fast:**
- Uses `entry_count` field directly (no subcollection iteration)
- Caches user email lookups
- Single Firestore query with date filter

**For subcollection counts**, Firestore's native `count()` aggregation is available:
```python
from google.cloud.firestore_v1.aggregation import AggregationQuery
count_query = AggregationQuery(collection_ref).count(alias='total')
result = count_query.get()
count = result[0][0].value  # 1 read per 1000 docs counted
```

# RRA Comparison Caching System

## Overview

RRA (Risk and Resilience Assessment) comparisons are now cached to avoid regenerating expensive LLM calls for the same briefings. Each comparison is linked to specific briefing and RRA metadata, so cache entries automatically invalidate when either source changes.

## How It Works

### Cache Storage

- **Location**: `intermediary_outputs/rra_comparisons/`
- **Entry Format**: Two files per cached comparison:
  - `{country}_{briefing_hash}.metadata.json` — Cache metadata
  - `{country}_{briefing_hash}.result.html` — Cached RRA comparison result

### Cache Key Generation

Cache keys are built from:
1. **Country name** (normalized: lowercase, spaces/commas removed)
2. **Briefing content hash** (SHA256, first 16 chars)

Example: `djibouti_a7f3d2e1c9b45f22` 

This ensures that:
- Different briefings for the same country have different cache entries
- The same briefing for the same country reuses the cache
- Small changes to briefing content invalidate the cache automatically

### Cache Validation

A cached comparison is used only if:

1. ✅ Both metadata and result files exist
2. ✅ The briefing hash in metadata matches the current briefing
3. ✅ The RRA file hasn't been modified since cache creation
4. ✅ The cache is less than 7 days old (configurable)

If any condition fails, the comparison is regenerated and the cache is updated.

## API Integration

### Primary Endpoint: `/api/briefing/compare-to-rra` [POST]

**Request:**
```json
{
  "country": "Djibouti",
  "briefing": "Full briefing text...",
  "bypass_cache": false
}
```

**Response:**
```json
{
  "annotated_briefing": "<html>...",
  "rra_summary": "RRA found: djibouti_rra.txt",
  "from_cache": true,
  "cache_key": "djibouti_a7f3d2e1c9b45f22"
}
```

**Response Fields:**
- `from_cache`: Boolean indicating whether result was cached
- `cache_key`: The cache key used for this comparison
- `bypass_cache`: Set to `true` in request to force regeneration

### Cache Management Endpoints

#### Get Cache Statistics

**Endpoint**: `GET /api/briefing/rra-cache/stats`

**Response:**
```json
{
  "total_entries": 24,
  "total_size_bytes": 15728640,
  "by_country": {
    "djibouti": {
      "entries": 8,
      "size_bytes": 5242880
    },
    "ethiopia": {
      "entries": 16,
      "size_bytes": 10485760
    }
  }
}
```

#### Clear Country Cache

**Endpoint**: `POST /api/briefing/rra-cache/clear`

**Request:**
```json
{
  "country": "Djibouti"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Cleared 8 cache entries for Djibouti",
  "entries_cleared": 8
}
```

Use this to force regeneration of all comparisons for a country (for example, if the RRA file was updated).

## Usage Patterns

### Normal Usage (Caching Enabled)

```python
# Client makes request
POST /api/briefing/compare-to-rra
{
  "country": "Djibouti",
  "briefing": "...content...",
  "bypass_cache": false  # Use cache if available
}

# First request: generates LLM comparison, stores in cache (~10-30 seconds)
# Second request: returns cached result instantly (<100ms)
```

### Force Regeneration

```python
# If you need to regenerate (e.g., RRA file was updated)
POST /api/briefing/compare-to-rra
{
  "country": "Djibouti", 
  "briefing": "...content...",
  "bypass_cache": true  # Skip cache, regenerate
}

# Cache will be updated with new result
```

### Clear All Cached Comparisons for a Country

```python
# If RRA file was significantly updated
POST /api/briefing/rra-cache/clear
{
  "country": "Djibouti"
}

# All Djibouti comparisons cleared; next requests will regenerate
```

## Implementation Details

### Cache Manager Class: `RRAComparisonCache`

Located in `rra_cache.py`, this class handles all caching operations:

```python
from rra_cache import get_rra_cache

cache = get_rra_cache(country="Djibouti")

# Check if cache is valid
is_valid = cache.is_cache_valid(
    country="Djibouti",
    briefing_content="...",
    rra_path="/path/to/rra.txt",
    max_age_hours=168  # 7 days
)

# Retrieve cached comparison
result = cache.get_cached_comparison("Djibouti", briefing_content)

# Save new comparison
cache.save_comparison(
    country="Djibouti",
    briefing_content="...", 
    rra_path="/path/to/rra.txt",
    comparison_result="<html>..."
)

# Clear all cache for country
cache.clear_country_cache("Djibouti")

# Get stats
stats = cache.get_cache_stats()
```

### Metadata Stored per Cache Entry

```json
{
  "country": "Djibouti",
  "briefing_hash": "a7f3d2e1c9b45f22",
  "briefing_length": 45230,
  "rra_path": "/path/to/djibouti_rra.txt",
  "rra_mtime": 1712764800.0,
  "created_timestamp": 1712764920.0,
  "cache_key": "djibouti_a7f3d2e1c9b45f22"
}
```

## Performance Impact

- **Cache Hit**: ~100ms (file read + JSON parsing)
- **Cache Miss**: ~10-30 seconds (full LLM generation + save)
- **Storage**: ~500KB-2MB per comparison

With typical usage patterns (reviewing old briefings, generating comparisons multiple times), expect **50-80% cache hit rate**, reducing API cost and latency significantly.

## Future Enhancements

Potential improvements to consider:

1. **Compression**: Compress cached HTML results (gzip) to reduce storage
2. **LRU Eviction**: Automatically clean up entries older than 30 days or when cache exceeds size limit
3. **Versioning**: Track which RRA version was used, alert if RRA is newer
4. **Export**: Option to export cache statistics to CSV for analysis
5. **Warm Cache**: Batch pre-generate comparisons for newest briefings across countries

# Jobs Search Endpoint

## POST /v1/jobs/search

Multi-signal job search combining text relevance, semantic similarity, skill matching, seniority alignment, salary filtering, geographic proximity, and recency decay. Results are ranked using Reciprocal Rank Fusion (RRF) across all active signals.

### Request Body

```json
{
  "query": "machine learning engineer NLP deep learning",
  "skill_boosts": [
    {"entity_id": "175c2b707caa6eb1", "weight": 10.0}
  ],
  "seniority": "senior",
  "min_salary": 180000,
  "filters": {"workModel": "remote"},
  "location": [37.77, -122.42],
  "location_radius": "100km",
  "recency_decay": "30d",
  "size": 20
}
```

All fields are optional except `query`.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | *required* | Search text — matched via BM25 keyword and k-NN vector similarity |
| `skill_boosts` | array | `[]` | Entity ID + weight pairs. Boost jobs that require specific skills. Resolve names to IDs via `/v1/resolution/entities` first. |
| `seniority` | string | `null` | Target seniority level. Dual-track scoring (IC + management), +/-2 levels filtered. Values: `"entry"`, `"mid"`, `"senior"`, `"staff"`, `"principal"`, `"director"`, `"vp"` |
| `min_salary` | int | `null` | Minimum salary threshold. Boosts jobs with `salaryMax` >= this value. |
| `filters` | object | `{}` | Hard term filters. Supported keys: `workModel` (`"remote"`, `"hybrid"`, `"onsite"`), `company`, etc. |
| `location` | array | `null` | `[latitude, longitude]` for geo-distance ranking |
| `location_radius` | string | `"50km"` | Radius for geo filtering (e.g., `"100km"`, `"50mi"`) |
| `recency_decay` | string | `"30d"` | Exponential decay half-life on `postedAt`. Shorter values favor newer postings. |
| `size` | int | 10 | Number of results to return (max 100) |

### Ranking Signals

All signals are optional. When provided, they're applied symmetrically to both BM25 and k-NN retrieval legs, then fused via RRF:

| Signal | What it does |
|--------|-------------|
| **Text + vector** | BM25 keyword match + k-NN embedding similarity give baseline relevance |
| **Skill boosts** | Nested entity matching with per-skill weights. Higher weight = stronger boost for jobs requiring that skill. |
| **Seniority** | Ordinal scoring on two tracks (IC: entry/mid/senior/staff/principal and management: lead/manager/director/vp). Jobs within +/-2 levels pass; others are filtered. |
| **Salary** | Gaussian boost centered on `min_salary`. Jobs well above threshold score highest. |
| **Recency** | Exponential decay on posting date. `"30d"` means a 30-day-old post scores ~50% of a new one. |
| **Location** | Geo-distance filter removes jobs outside radius, plus Gaussian proximity decay favoring closer jobs. |
| **Filters** | Hard term filters remove non-matching jobs entirely. |

### Examples

**Basic search:**

```bash
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  "$API_URL/v1/jobs/search" \
  -d '{"query": "machine learning engineer NLP deep learning", "size": 20}'
```

**Full-featured search:**

```bash
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  "$API_URL/v1/jobs/search" \
  -d '{
    "query": "AI engineer NLP LLMs RAG Python",
    "seniority": "senior",
    "min_salary": 180000,
    "filters": {"workModel": "remote"},
    "recency_decay": "30d",
    "size": 20
  }'
```

**With skill boosts** (resolve skill names to entity IDs first):

```bash
# Step 1: Resolve skill names
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  "$API_URL/v1/resolution/entities" \
  -d '{"names": [{"name": "Python", "entity_type": "skill"}, {"name": "PyTorch", "entity_type": "skill"}]}'

# Step 2: Use entity IDs in skill_boosts
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  "$API_URL/v1/jobs/search" \
  -d '{
    "query": "AI engineer",
    "skill_boosts": [
      {"entity_id": "175c2b707caa6eb1", "weight": 10.0},
      {"entity_id": "f0109bbf0cbac010", "weight": 7.0}
    ],
    "size": 20
  }'
```

**Geo-filtered search:**

```bash
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  "$API_URL/v1/jobs/search" \
  -d '{
    "query": "software engineer",
    "location": [37.77, -122.42],
    "location_radius": "100km",
    "size": 20
  }'
```

### Response

```json
{
  "total": 342,
  "hits": [
    {
      "job_id": "abc123",
      "title": "Senior ML Engineer",
      "company": "Acme AI",
      "location": "San Francisco, CA",
      "workModel": "remote",
      "salaryMin": 180000,
      "salaryMax": 250000,
      "postedAt": "2026-04-10T00:00:00Z",
      "skills": ["Python", "PyTorch", "Kubernetes"],
      "score": 0.92
    }
  ]
}
```

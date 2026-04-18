# Analytics Endpoints

Pre-built aggregate views for common analytical queries. These are faster and cheaper than writing raw SQL or Cypher queries.

## GET /v1/analytics/counts

Returns document counts broken down by source type.

### Request

```bash
curl -s -H "X-API-Key: $API_KEY" "$API_URL/v1/analytics/counts"
```

### Response

```json
{
  "total": 125000,
  "buckets": [
    {"source_type": "jobs", "count": 45000},
    {"source_type": "blog", "count": 32000},
    {"source_type": "scholarly", "count": 28000},
    {"source_type": "news", "count": 12000},
    {"source_type": "social", "count": 8000}
  ]
}
```

---

## GET /v1/analytics/topic-trends

Returns monthly topic mention counts, showing how topics rise and fall over time.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 20 | Max number of trend data points to return |

### Request

```bash
curl -s -H "X-API-Key: $API_KEY" "$API_URL/v1/analytics/topic-trends?limit=50"
```

### Response

```json
{
  "trends": [
    {"topic": "large-language-models", "period": "2026-03", "count": 1450},
    {"topic": "large-language-models", "period": "2026-02", "count": 1320},
    {"topic": "agents", "period": "2026-03", "count": 980},
    {"topic": "computer-vision", "period": "2026-03", "count": 870}
  ]
}
```

Each entry is a (topic, period, count) triple. Group by `topic` to build time series, or group by `period` to see rankings for a specific month.

**Note:** Topics are coarse taxonomy tags (~33 categories), not fine-grained skills. See [the distinction between Topics and Skills](../getting-started.md#topics-vs-skills).

---

## GET /v1/analytics/entity-cooccurrence

Returns the most frequently co-mentioned entity pairs across all documents. Reveals partnerships, competitive dynamics, and technology stack associations.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 20 | Max number of entity pairs to return |

### Request

```bash
curl -s -H "X-API-Key: $API_KEY" "$API_URL/v1/analytics/entity-cooccurrence?limit=50"
```

### Response

```json
{
  "pairs": [
    {
      "entity_a_name": "OpenAI",
      "entity_b_name": "GPT-4",
      "count": 2340
    },
    {
      "entity_a_name": "Google",
      "entity_b_name": "DeepMind",
      "count": 1890
    }
  ]
}
```

---

## GET /v1/analytics/skills-by-role

Returns skill distributions for a given role. This is the **preferred endpoint** for analyzing what skills a job role requires.

The endpoint resolves role names via entity resolution (exact match first, then fuzzy full-text fallback), so you don't need exact canonical role labels. It also accepts comma-separated aliases to merge multiple role variants into a single aggregated skill profile.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `role` | string | *(none — returns all roles)* | Role name(s), comma-separated for aliases |

### Request

```bash
# Single role (fuzzy matching)
curl -s -H "X-API-Key: $API_KEY" \
  "$API_URL/v1/analytics/skills-by-role?role=Data+Scientist"

# Multiple aliases merged into one profile
curl -s -H "X-API-Key: $API_KEY" \
  "$API_URL/v1/analytics/skills-by-role?role=ML+Engineer,Machine+Learning+Engineer"
```

### Response

```json
{
  "roles": [
    {
      "role": "Data Scientist",
      "total_jobs": 1124,
      "skills": [
        {"skill": "Python", "count": 880},
        {"skill": "SQL", "count": 704},
        {"skill": "Machine Learning", "count": 650},
        {"skill": "TensorFlow", "count": 420},
        {"skill": "PyTorch", "count": 390}
      ]
    }
  ]
}
```

### Use Cases

- **Single role analysis:** What skills are most in demand for Data Scientists?
- **Role comparison:** Fetch Data Scientist and ML Engineer separately, then cross-tabulate the skill lists
- **Alias merging:** Combine "ML Engineer" and "Machine Learning Engineer" to get a unified view
- **Skill gap analysis:** Compare your resume skills against a role's top requirements

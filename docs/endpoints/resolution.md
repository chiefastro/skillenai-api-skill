# Entity Resolution Endpoint

## POST /v1/resolution/entities

Resolves free-text names to canonical entity IDs in the Skillenai knowledge graph. Use this to find entity IDs for `skill_boosts` in job search, or to normalize variant spellings before analysis.

### Request Body

```json
{
  "names": [
    {"name": "Python", "entity_type": "skill"},
    {"name": "Google", "entity_type": "company"},
    {"name": "TensorFlow"}
  ],
  "mode": "auto",
  "limit": 3
}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `names` | array | *required* | List of name objects to resolve. Each has `name` (required) and optional `entity_type`. |
| `mode` | string | `"auto"` | Resolution strategy (see below) |
| `limit` | int | 3 | Max candidates per name |

### Resolution Modes

| Mode | Behavior |
|------|----------|
| `auto` | Try exact match first, fall back to fuzzy full-text search if no exact match found. Best for most use cases. |
| `exact` | Exact match only. Fast, but returns nothing for misspellings or variants. |
| `fts` | Full-text search (BM25) only. Returns ranked candidates even for approximate matches. |

### Supported Entity Types

- `skill` — Technologies, tools, frameworks, methodologies
- `company` — Organizations and employers
- `product` — Software products and platforms
- `person` — People (researchers, executives, etc.)
- `location` — Cities, regions, countries

Omit `entity_type` to search across all types.

### Example

```bash
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  "$API_URL/v1/resolution/entities" \
  -d '{
    "names": [
      {"name": "Python", "entity_type": "skill"},
      {"name": "Google", "entity_type": "company"},
      {"name": "TensorFlow"}
    ],
    "mode": "auto",
    "limit": 3
  }'
```

### Response

```json
{
  "results": [
    {
      "query": {"name": "Python", "entity_type": "skill"},
      "matches": [
        {
          "entity_id": "175c2b707caa6eb1",
          "canonical_name": "Python",
          "entity_type": "skill",
          "score": 1.0,
          "method": "exact"
        }
      ]
    },
    {
      "query": {"name": "Google", "entity_type": "company"},
      "matches": [
        {
          "entity_id": "a3f2c8901bde4567",
          "canonical_name": "Google",
          "entity_type": "company",
          "score": 1.0,
          "method": "exact"
        }
      ]
    },
    {
      "query": {"name": "TensorFlow"},
      "matches": [
        {
          "entity_id": "f0109bbf0cbac010",
          "canonical_name": "TensorFlow",
          "entity_type": "product",
          "score": 1.0,
          "method": "exact"
        }
      ]
    }
  ]
}
```

### Common Workflow: Resolve Then Search

A typical pattern is to resolve skill names to entity IDs, then use those IDs as `skill_boosts` in a job search:

```python
import requests, os
from dotenv import load_dotenv

load_dotenv()
url, key = os.getenv("API_URL"), os.getenv("API_KEY")
headers = {"X-API-Key": key, "Content-Type": "application/json"}

# Step 1: Resolve skills
resolution = requests.post(f"{url}/v1/resolution/entities", headers=headers, json={
    "names": [
        {"name": "Python", "entity_type": "skill"},
        {"name": "PyTorch", "entity_type": "skill"},
    ],
    "mode": "auto",
}).json()

# Step 2: Build skill_boosts from resolved IDs
boosts = []
for result in resolution["results"]:
    if result["matches"]:
        boosts.append({
            "entity_id": result["matches"][0]["entity_id"],
            "weight": 10.0,
        })

# Step 3: Search jobs with skill boosts
jobs = requests.post(f"{url}/v1/jobs/search", headers=headers, json={
    "query": "ML engineer",
    "skill_boosts": boosts,
    "size": 20,
}).json()
```

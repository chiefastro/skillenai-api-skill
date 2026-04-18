# Catalog Endpoints

Schema introspection for the SkillenAI data platform. Use these endpoints to discover available tables, columns, and projections before writing queries.

## GET /v1/catalog

Lists all available data projections (query backends).

### Request

```bash
curl -s -H "X-API-Key: $API_KEY" "$API_URL/v1/catalog"
```

### Response

```json
{
  "projections": [
    {"name": "postgres", "description": "Relational data store — entities, documents, relationships"},
    {"name": "opensearch", "description": "Full-text search and aggregations"},
    {"name": "athena", "description": "S3-backed analytical queries"},
    {"name": "graph", "description": "Knowledge graph (Apache AGE / Cypher)"}
  ]
}
```

---

## GET /v1/catalog/{projection}

Returns the schema for a specific projection — tables, columns, types, and descriptions.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `projection` | string | One of: `postgres`, `opensearch`, `athena`, `graph` |

### Request

```bash
curl -s -H "X-API-Key: $API_KEY" "$API_URL/v1/catalog/postgres"
```

### Response

The response varies by projection type. For Postgres, it returns table schemas:

```json
{
  "projection": "postgres",
  "tables": [
    {
      "name": "skillenai.entities",
      "columns": [
        {"name": "entity_id", "type": "text", "description": "Unique entity identifier"},
        {"name": "canonical_name", "type": "text", "description": "Canonical display name"},
        {"name": "entity_type", "type": "text", "description": "One of: company, product, person, skill, location"},
        {"name": "aliases", "type": "text[]", "description": "Alternative names"},
        {"name": "topics", "type": "text[]", "description": "Associated taxonomy topics"}
      ]
    },
    {
      "name": "skillenai.documents",
      "columns": [
        {"name": "document_id", "type": "text"},
        {"name": "title", "type": "text"},
        {"name": "source_type", "type": "text"},
        {"name": "source_url", "type": "text"},
        {"name": "published_at", "type": "timestamptz"}
      ]
    }
  ]
}
```

### Available Projections

| Projection | Query Endpoint | Use Case |
|------------|---------------|----------|
| `postgres` | `POST /v1/query/sql` | Entity lookups, relationship queries, document metadata |
| `opensearch` | `POST /v1/query/search` | Full-text search, aggregations, nested entity queries |
| `athena` | `POST /v1/query/athena` | Large-scale analytical queries over S3 data |
| `graph` | `POST /v1/query/graph` | Knowledge graph traversal via Cypher |

### Key Postgres Tables

| Table | Description |
|-------|-------------|
| `skillenai.entities` | All canonical entities (companies, skills, people, etc.) |
| `skillenai.documents` | All indexed documents (jobs, blogs, papers, etc.) |
| `skillenai.document_entity_links` | Many-to-many links between documents and entities |
| `skillenai.relationships` | Entity-to-entity relationships extracted from content |

### Graph Node Labels

| Label | Description |
|-------|-------------|
| `job` | Job postings. Has `roles` property (pipe-delimited, e.g. `"Data Scientist\|ML Engineer"`). |
| `document` | Content documents (blogs, papers, news, etc.) |
| `skill` | Skills, technologies, tools |
| `company` | Organizations |
| `product` | Software products and platforms |
| `person` | People |
| `location` | Geographic entities |

### Graph Edge Labels

| Edge | Direction | Meaning |
|------|-----------|---------|
| `REQUIRES` | job -> skill | Job posting requires this skill |
| `MENTIONS` | document -> entity | Document mentions this entity |
| `POSTED_BY` | job -> company | Job was posted by this company |
| `AUTHORED` | person -> document | Person authored this document |

Always check `GET /v1/catalog/{projection}` before writing queries to verify current table/column names.

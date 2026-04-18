# Authentication

All API requests require an API key passed via the `X-API-Key` header.

## API Key Format

Keys follow the format `skn_live_` followed by a random string:

```
skn_live_a1b2c3d4e5f6g7h8i9j0...
```

## Setting the Header

Include the key in every request:

```bash
curl -H "X-API-Key: skn_live_your_key_here" \
  "https://api.skillenai.com/v1/analytics/counts"
```

In Python:

```python
headers = {"X-API-Key": "skn_live_your_key_here"}
requests.get("https://api.skillenai.com/v1/analytics/counts", headers=headers)
```

## Environment Setup

Store credentials in a `.env` file (never commit this):

```
API_URL=https://api.skillenai.com
API_KEY=skn_live_your_key_here
```

Load in shell scripts:

```bash
source .env
curl -H "X-API-Key: $API_KEY" "$API_URL/v1/health"
```

Load in Python:

```python
import os
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("API_URL")
API_KEY = os.getenv("API_KEY")
```

## Response Headers

Every API response includes billing headers:

| Header | Description |
|--------|-------------|
| `X-Credits-Used` | Credits consumed by this request |
| `X-Credits-Remaining` | Credits remaining in your account |

Monitor these to track usage and avoid hitting your credit limit.

## Rate Limit Tiers

Endpoints are grouped into rate limit tiers:

| Tier | Limit | Endpoints |
|------|-------|-----------|
| READ | 120/min | `/v1/health`, `/v1/version`, `/v1/catalog` |
| SEARCH | 60/min | `/v1/jobs/search`, `/v1/resolution/entities` |
| ANALYTICS | 20/min | `/v1/analytics/*` |
| QUERY | 10/min | `/v1/query/sql`, `/v1/query/athena`, `/v1/query/graph`, `/v1/query/search` |

When you exceed a rate limit, the API returns `429 Too Many Requests`. When your credits are exhausted, it returns `402 Payment Required`.

## Error Responses

| Status | Meaning |
|--------|---------|
| `401` | Missing or invalid API key |
| `402` | Credits exhausted |
| `429` | Rate limit exceeded |
| `403` | Key revoked or suspended |

All error responses include a JSON body with a `detail` field:

```json
{
  "detail": "Rate limit exceeded. Retry after 12 seconds.",
  "retry_after": 12
}
```

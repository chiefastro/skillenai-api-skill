# Rate Limits and Credits

## Rate Limit Tiers

Each API key is subject to per-minute rate limits, organized by endpoint tier:

| Tier | Limit | Endpoints |
|------|------:|-----------|
| READ | 120/min | `/v1/health`, `/v1/version`, `/v1/catalog`, `/v1/catalog/{projection}` |
| SEARCH | 60/min | `/v1/jobs/search`, `/v1/resolution/entities` |
| ANALYTICS | 20/min | `/v1/analytics/counts`, `/v1/analytics/topic-trends`, `/v1/analytics/entity-cooccurrence`, `/v1/analytics/skills-by-role` |
| QUERY | 10/min | `/v1/query/sql`, `/v1/query/athena`, `/v1/query/graph`, `/v1/query/search` |

Limits are per API key, not per IP address. All tiers use a sliding window.

## Credits

API calls consume credits from your account balance. Different endpoints cost different amounts of credits based on compute intensity.

### Checking Your Balance

Every response includes billing headers:

```
X-Credits-Used: 1
X-Credits-Remaining: 4832
```

You can also check your balance and usage in the web dashboard at [app.skillenai.com](https://app.skillenai.com).

## Error Codes

### 429 Too Many Requests

Returned when you exceed the rate limit for a tier. The response includes a `retry_after` field:

```json
{
  "detail": "Rate limit exceeded. Retry after 8 seconds.",
  "retry_after": 8
}
```

**Handling:** Wait for the indicated number of seconds before retrying. Implement exponential backoff for automated clients.

### 402 Payment Required

Returned when your credit balance reaches zero:

```json
{
  "detail": "Insufficient credits. Purchase additional credits at app.skillenai.com."
}
```

**Handling:** Purchase additional credits through the web dashboard.

### 401 Unauthorized

Returned when the `X-API-Key` header is missing or the key is invalid:

```json
{
  "detail": "Invalid API key."
}
```

## Best Practices

1. **Cache responses** — Analytics endpoints return data that changes slowly (hourly or daily). Cache results to reduce credit usage.
2. **Use appropriate endpoints** — `skills-by-role` is cheaper than a raw Cypher query that does the same thing. Prefer dedicated analytics endpoints over generic query endpoints.
3. **Batch entity resolution** — Send multiple names in a single `/v1/resolution/entities` call instead of one at a time.
4. **Monitor headers** — Check `X-Credits-Remaining` in your code and alert before running out.
5. **Respect rate limits** — Implement backoff logic. Don't retry immediately on 429.

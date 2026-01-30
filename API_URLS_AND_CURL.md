# API URLs and test curl

**Base URL:** `http://localhost:8000` (or your host, e.g. `https://pub-sub-7dv4.onrender.com`)  
**Auth:** All requests need header: `X-API-Key: <your-api-key>` (same as `API_KEY` in env)

---

## Final URLs

| Method | Path |
|--------|------|
| GET | `/api/v1/health` |
| GET | `/api/v1/stats` |
| POST | `/api/v1/topics` |
| GET | `/api/v1/topics` |
| DELETE | `/api/v1/topics/{name}` |
| POST | `/api/v1/subscribe` |
| WebSocket | `ws://localhost:8000/api/v1/ws` (or `wss://...` in prod) |

---

## Test curl (local)

Set your key (or use the same value as in `.env` `API_KEY`):

```bash
export API_KEY="my-secret-api-key"
BASE="http://localhost:8000"
```

**Health**
```bash
curl -s -H "X-API-Key: $API_KEY" "$BASE/api/v1/health" | jq
```

**Stats**
```bash
curl -s -H "X-API-Key: $API_KEY" "$BASE/api/v1/stats" | jq
```

**Create topic**
```bash
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"name":"orders"}' "$BASE/api/v1/topics" | jq
```

**List topics**
```bash
curl -s -H "X-API-Key: $API_KEY" "$BASE/api/v1/topics" | jq
```

**Delete topic**
```bash
curl -s -X DELETE -H "X-API-Key: $API_KEY" "$BASE/api/v1/topics/orders" | jq
```

**Subscribe (HTTP)**
```bash
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"topic":"orders","subscriber_id":"sub-1","last_n":0}' "$BASE/api/v1/subscribe" | jq
```

**Subscribe with replay (last 5 messages)**
```bash
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"topic":"orders","subscriber_id":"sub-2","last_n":5}' "$BASE/api/v1/subscribe" | jq
```

---

## One-liners (no jq)

```bash
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/health
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/stats
curl -s -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" -d '{"name":"orders"}' http://localhost:8000/api/v1/topics
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/topics
```

Remove `| jq` if you don't have jq; response is still JSON.

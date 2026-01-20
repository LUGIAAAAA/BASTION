# BASTION API Documentation

## Base URL

```
http://localhost:8001
```

---

## Endpoints

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "service": "BASTION",
  "version": "1.0.0-MVP",
  "timestamp": "2026-01-19T19:00:00.000Z"
}
```

---

### POST /calculate

Calculate risk levels for a trade setup.

**Request Body:**
```json
{
  "symbol": "BTCUSDT",
  "entry_price": 95000,
  "direction": "long",
  "timeframe": "4h",
  "account_balance": 100000,
  "risk_per_trade_pct": 1.0
}
```

**Parameters:**
- `symbol` (string, required) - Trading pair (e.g., BTCUSDT, ETHUSDT)
- `entry_price` (number, required) - Entry price for the trade (must be > 0)
- `direction` (string, required) - Trade direction: "long" or "short"
- `timeframe` (string, optional) - Candle timeframe: 1m, 5m, 15m, 1h, 4h, 1d (default: "4h")
- `account_balance` (number, optional) - Account balance in USD (default: 100000)
- `risk_per_trade_pct` (number, optional) - Risk percentage per trade, 0.1-10% (default: 1.0)

**Response:**
```json
{
  "symbol": "BTCUSDT",
  "entry_price": 95000,
  "direction": "long",
  "current_price": 94328,
  "stops": [
    {
      "type": "primary",
      "price": 92500,
      "distance_pct": 2.6,
      "reason": "Below support at 92800",
      "confidence": 0.8
    },
    {
      "type": "secondary",
      "price": 91500,
      "distance_pct": 3.7,
      "reason": "Secondary ATR stop (1.5x)",
      "confidence": 0.5
    }
  ],
  "targets": [
    {
      "price": 98000,
      "exit_percentage": 33,
      "distance_pct": 3.2,
      "reason": "Resistance level (R:R 2.5)",
      "confidence": 0.7
    },
    {
      "price": 100500,
      "exit_percentage": 33,
      "distance_pct": 5.8,
      "reason": "Resistance level (R:R 4.0)",
      "confidence": 0.6
    },
    {
      "price": 103000,
      "exit_percentage": 34,
      "distance_pct": 8.4,
      "reason": "5R target",
      "confidence": 0.5
    }
  ],
  "position_size": 0.421,
  "position_size_pct": 33.3,
  "risk_amount": 1000,
  "risk_reward_ratio": 2.5,
  "max_risk_reward_ratio": 6.5,
  "win_probability": 0.52,
  "expected_value": 0.8,
  "guarding_line": null,
  "calculated_at": "2026-01-19T19:00:00.000Z"
}
```

**Error Response:**
```json
{
  "error": "Could not fetch market data",
  "detail": "Symbol not found or API timeout",
  "timestamp": "2026-01-19T19:00:00.000Z"
}
```

---

## curl Examples

### Health Check
```bash
curl http://localhost:8001/health
```

### Calculate Long Position
```bash
curl -X POST http://localhost:8001/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "entry_price": 95000,
    "direction": "long",
    "timeframe": "4h",
    "account_balance": 100000,
    "risk_per_trade_pct": 1.0
  }'
```

### Calculate Short Position
```bash
curl -X POST http://localhost:8001/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "ETHUSDT",
    "entry_price": 3500,
    "direction": "short",
    "timeframe": "1h",
    "account_balance": 50000,
    "risk_per_trade_pct": 0.5
  }'
```

---

## Python Example

```python
import requests

url = "http://localhost:8001/calculate"
data = {
    "symbol": "BTCUSDT",
    "entry_price": 95000,
    "direction": "long",
    "timeframe": "4h",
    "account_balance": 100000,
    "risk_per_trade_pct": 1.0
}

response = requests.post(url, json=data)
levels = response.json()

print(f"Primary Stop: ${levels['stops'][0]['price']}")
print(f"First Target: ${levels['targets'][0]['price']}")
print(f"Position Size: {levels['position_size']}")
print(f"Risk:Reward: {levels['risk_reward_ratio']}R")
```

---

## JavaScript Example

```javascript
const response = await fetch('http://localhost:8001/calculate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    symbol: 'BTCUSDT',
    entry_price: 95000,
    direction: 'long',
    timeframe: '4h',
    account_balance: 100000,
    risk_per_trade_pct: 1.0
  })
});

const levels = await response.json();
console.log(`Primary Stop: $${levels.stops[0].price}`);
console.log(`First Target: $${levels.targets[0].price}`);
```

---

## Error Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Invalid request (bad parameters) |
| 422 | Validation error |
| 502 | Data fetch failed (market data unavailable) |
| 500 | Internal server error |

---

## Rate Limits

Currently no rate limits in MVP. 

For production deployment, consider:
- 60 requests/minute per IP
- 1000 requests/hour per IP

---

## Interactive Documentation

Visit `http://localhost:8001/docs` for interactive Swagger UI documentation.


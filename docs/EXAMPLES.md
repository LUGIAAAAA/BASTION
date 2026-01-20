# BASTION Usage Examples

## Example 1: Bitcoin Long Position

**Scenario:** You want to go long BTC at $95,000 on the 4H timeframe.

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

**Result:**
- Primary Stop: $92,500 (2.6% risk)
- Target 1: $98,000 (33% exit) - 2.5R
- Target 2: $100,500 (33% exit) - 4.0R
- Target 3: $103,000 (34% exit) - 6.5R
- Position Size: 0.421 BTC
- Risk Amount: $1,000

**Action:**
1. Enter 0.421 BTC long at $95,000
2. Place stop-loss at $92,500
3. Set take-profit orders:
   - Sell 0.14 BTC at $98,000
   - Sell 0.14 BTC at $100,500
   - Sell 0.13 BTC at $103,000

---

## Example 2: Ethereum Short Position

**Scenario:** You think ETH will drop from $3,500.

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

**Result:**
- Primary Stop: $3,625 (3.6% risk)
- Target 1: $3,350 (33% exit)
- Target 2: $3,200 (33% exit)
- Target 3: $3,050 (34% exit)
- Position Size: 2.0 ETH
- Risk Amount: $250

---

## Example 3: Smaller Account with Higher Risk

**Scenario:** $10K account, willing to risk 2% per trade.

```bash
curl -X POST http://localhost:8001/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "SOLUSDT",
    "entry_price": 180,
    "direction": "long",
    "timeframe": "15m",
    "account_balance": 10000,
    "risk_per_trade_pct": 2.0
  }'
```

**Result:**
- Risk Amount: $200
- Larger position size due to higher risk tolerance
- More aggressive stops/targets on 15m timeframe

---

## Example 4: Conservative Position (0.25% Risk)

**Scenario:** Large account, very conservative.

```bash
curl -X POST http://localhost:8001/calculate \
  -H "Content-Type": "application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "entry_price": 95000,
    "direction": "long",
    "timeframe": "1d",
    "account_balance": 1000000,
    "risk_per_trade_pct": 0.25
  }'
```

**Result:**
- Risk Amount: $2,500
- Wider stops on daily timeframe
- Lower position size relative to account
- Suitable for swing trading

---

## Example 5: Error Handling

**Invalid Symbol:**
```bash
curl -X POST http://localhost:8001/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "FAKECOIN",
    "entry_price": 100,
    "direction": "long"
  }'
```

**Response:**
```json
{
  "error": "Could not fetch market data for FAKECOIN",
  "detail": "Symbol not found",
  "timestamp": "2026-01-19T19:00:00.000Z"
}
```

---

## Integration with Trading Bots

```python
import requests

class BastionRiskManager:
    def __init__(self, api_url="http://localhost:8001"):
        self.api_url = api_url
    
    def get_risk_levels(self, symbol, entry, direction, account_balance):
        response = requests.post(
            f"{self.api_url}/calculate",
            json={
                "symbol": symbol,
                "entry_price": entry,
                "direction": direction,
                "account_balance": account_balance
            }
        )
        return response.json()
    
    def place_trade_with_risk(self, exchange, symbol, entry, direction, account_balance):
        # Get risk levels from BASTION
        levels = self.get_risk_levels(symbol, entry, direction, account_balance)
        
        stop = levels['stops'][0]['price']
        position_size = levels['position_size']
        targets = [t['price'] for t in levels['targets']]
        
        # Place trade on exchange
        exchange.place_order(
            symbol=symbol,
            side='buy' if direction == 'long' else 'sell',
            amount=position_size,
            stop_loss=stop,
            take_profits=targets
        )
        
        return levels

# Usage
rm = BastionRiskManager()
levels = rm.place_trade_with_risk(
    exchange=my_exchange,
    symbol='BTCUSDT',
    entry=95000,
    direction='long',
    account_balance=100000
)
```

---

## Copy Levels for Manual Trading

After getting API response, format for quick reference:

```python
def format_for_manual_trading(levels):
    print(f"""
🎯 TRADE SETUP - {levels['symbol']} {levels['direction'].upper()}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Entry: ${levels['entry_price']:,.2f}
Current: ${levels['current_price']:,.2f}

🛑 STOPS:
""")
    for stop in levels['stops']:
        print(f"  {stop['type'].upper()}: ${stop['price']:,.2f} ({stop['distance_pct']:.1f}%)")
    
    print("\n🎯 TARGETS:")
    for i, target in enumerate(levels['targets'], 1):
        print(f"  T{i}: ${target['price']:,.2f} ({target['exit_percentage']:.0f}% exit)")
    
    print(f"""
📊 POSITION:
  Size: {levels['position_size']:.4f}
  Risk: ${levels['risk_amount']:,.2f}
  R:R: {levels['risk_reward_ratio']:.1f}R
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
```


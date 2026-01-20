# AGENT TASK: Add Funding Rate + Liquidation Data

## Priority: Medium
## Estimated Time: 4-6 hours
## Dependencies: Helsinki VM Quant API

---

## Why These Features Matter for Risk Management

These are the **only 2 missing institutional features** that directly impact risk calculations:

| Feature | Impact on Risk |
|---------|----------------|
| **Funding Rate** | Extreme funding = higher holding cost = adjust position size |
| **Liquidation Levels** | Clustered liquidations = stop hunting zones = avoid placing stops there |

Everything else (dark pools, options flow, news) is signal/edge - not risk infrastructure.

---

## 1. Funding Rate Integration

### What It Does
- Funding rate is paid every 8 hours on perpetual futures
- Extreme positive funding (longs pay shorts) = expensive to hold longs
- Extreme negative funding (shorts pay longs) = expensive to hold shorts
- Should adjust position sizing based on expected holding cost

### Data Source
Helsinki VM already has this at `/quant/funding`:
```json
{
    "symbol": "BTCUSDT",
    "funding_rate": 0.0001,      // 0.01% per 8h
    "funding_interval_hours": 8,
    "next_funding_time": 1705881600,
    "annualized_rate": 10.95,    // 10.95% APR
    "sentiment": "bullish"       // Longs willing to pay
}
```

### Implementation

Create `core/funding_analyzer.py`:

```python
"""
Funding Rate Analyzer
=====================

Integrates funding rate data into position sizing and risk calculations.

High funding = expensive to hold = reduce size or tighten stops
"""

import httpx
from dataclasses import dataclass
from typing import Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class FundingBias(str, Enum):
    EXTREME_BULLISH = "extreme_bullish"   # > 0.05% per 8h
    BULLISH = "bullish"                    # 0.01% - 0.05%
    NEUTRAL = "neutral"                    # -0.01% to 0.01%
    BEARISH = "bearish"                    # -0.05% to -0.01%
    EXTREME_BEARISH = "extreme_bearish"   # < -0.05%


@dataclass
class FundingAnalysis:
    """Funding rate analysis result."""
    
    symbol: str
    current_rate: float          # e.g., 0.0001 = 0.01%
    annualized_rate: float       # APR
    bias: FundingBias
    next_funding_hours: float
    
    # Risk adjustments
    holding_cost_daily_pct: float    # Daily cost as % of position
    size_adjustment_factor: float    # Multiply position size by this
    
    def to_dict(self):
        return {
            'symbol': self.symbol,
            'current_rate': self.current_rate,
            'annualized_rate': self.annualized_rate,
            'bias': self.bias.value,
            'holding_cost_daily_pct': self.holding_cost_daily_pct,
            'size_adjustment_factor': self.size_adjustment_factor,
        }


class FundingAnalyzer:
    """Analyzes funding rate impact on trade risk."""
    
    HELSINKI_QUANT_API = "http://77.42.29.188:5002"
    
    # Thresholds
    EXTREME_THRESHOLD = 0.0005   # 0.05% per 8h
    NORMAL_THRESHOLD = 0.0001    # 0.01% per 8h
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def analyze(self, symbol: str, direction: str) -> FundingAnalysis:
        """
        Analyze funding rate and calculate risk adjustments.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            direction: 'long' or 'short'
            
        Returns:
            FundingAnalysis with risk adjustments
        """
        try:
            response = await self.client.get(
                f"{self.HELSINKI_QUANT_API}/quant/funding/{symbol}"
            )
            
            if response.status_code != 200:
                return self._default_analysis(symbol)
            
            data = response.json()
            rate = data.get('funding_rate', 0.0)
            
        except Exception as e:
            logger.warning(f"Funding rate fetch failed: {e}")
            return self._default_analysis(symbol)
        
        # Determine bias
        if rate > self.EXTREME_THRESHOLD:
            bias = FundingBias.EXTREME_BULLISH
        elif rate > self.NORMAL_THRESHOLD:
            bias = FundingBias.BULLISH
        elif rate < -self.EXTREME_THRESHOLD:
            bias = FundingBias.EXTREME_BEARISH
        elif rate < -self.NORMAL_THRESHOLD:
            bias = FundingBias.BEARISH
        else:
            bias = FundingBias.NEUTRAL
        
        # Calculate daily holding cost
        # Funding is paid 3x per day (every 8h)
        daily_cost_pct = abs(rate) * 3 * 100  # As percentage
        
        # Annualized rate
        annualized = abs(rate) * 3 * 365 * 100
        
        # Size adjustment factor
        # If funding works against your position, reduce size
        size_factor = 1.0
        
        if direction == "long" and rate > 0:
            # Longs pay funding - expensive to hold
            if bias == FundingBias.EXTREME_BULLISH:
                size_factor = 0.7  # Reduce 30%
            elif bias == FundingBias.BULLISH:
                size_factor = 0.9  # Reduce 10%
                
        elif direction == "short" and rate < 0:
            # Shorts pay funding - expensive to hold
            if bias == FundingBias.EXTREME_BEARISH:
                size_factor = 0.7
            elif bias == FundingBias.BEARISH:
                size_factor = 0.9
        
        # Next funding time
        next_funding = data.get('next_funding_time', 0)
        import time
        hours_until = max(0, (next_funding - time.time()) / 3600)
        
        return FundingAnalysis(
            symbol=symbol,
            current_rate=rate,
            annualized_rate=annualized,
            bias=bias,
            next_funding_hours=hours_until,
            holding_cost_daily_pct=daily_cost_pct,
            size_adjustment_factor=size_factor,
        )
    
    def _default_analysis(self, symbol: str) -> FundingAnalysis:
        """Return neutral analysis when data unavailable."""
        return FundingAnalysis(
            symbol=symbol,
            current_rate=0.0,
            annualized_rate=0.0,
            bias=FundingBias.NEUTRAL,
            next_funding_hours=8.0,
            holding_cost_daily_pct=0.0,
            size_adjustment_factor=1.0,
        )
    
    async def close(self):
        await self.client.aclose()
```

---

## 2. Liquidation Levels Integration

### What It Does
- Shows where large liquidation clusters exist
- Avoid placing stops at obvious liquidation levels (stop hunting)
- Institutional traders hunt these levels before reversing
- If your stop is at a liquidation cluster, expect slippage

### Data Source
Helsinki VM has this at `/quant/liquidations`:
```json
{
    "symbol": "BTCUSDT",
    "liquidation_levels": [
        {"price": 92500, "volume_usd": 45000000, "type": "long"},
        {"price": 93000, "volume_usd": 28000000, "type": "long"},
        {"price": 98500, "volume_usd": 32000000, "type": "short"},
    ],
    "largest_long_liq": 92500,
    "largest_short_liq": 98500,
    "total_long_liq_usd": 125000000,
    "total_short_liq_usd": 89000000
}
```

### Implementation

Create `core/liquidation_analyzer.py`:

```python
"""
Liquidation Level Analyzer
==========================

Identifies liquidation clusters to avoid placing stops at obvious hunt zones.

Key insight: Market makers hunt liquidation clusters before reversing.
"""

import httpx
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class LiquidationLevel:
    """A liquidation cluster at a price level."""
    price: float
    volume_usd: float
    liq_type: str  # "long" or "short"
    distance_pct: float = 0.0  # Distance from current price
    
    def is_significant(self, threshold_usd: float = 10_000_000) -> bool:
        """Check if this cluster is significant."""
        return self.volume_usd >= threshold_usd


@dataclass  
class LiquidationAnalysis:
    """Complete liquidation analysis."""
    
    symbol: str
    current_price: float
    
    # Key levels
    levels: List[LiquidationLevel] = field(default_factory=list)
    
    # Nearest danger zones
    nearest_long_liq: Optional[float] = None    # Below price
    nearest_short_liq: Optional[float] = None   # Above price
    
    # Aggregates
    total_long_liq_usd: float = 0.0
    total_short_liq_usd: float = 0.0
    
    # Risk flags
    stop_at_liq_cluster: bool = False
    suggested_stop_adjustment: float = 0.0
    
    def get_levels_near_price(self, price: float, tolerance_pct: float = 0.5) -> List[LiquidationLevel]:
        """Get liquidation levels within tolerance of a price."""
        tolerance = price * (tolerance_pct / 100)
        return [l for l in self.levels if abs(l.price - price) <= tolerance]
    
    def is_price_at_liq_cluster(self, price: float, min_volume_usd: float = 20_000_000) -> bool:
        """Check if a price level sits at a significant liquidation cluster."""
        nearby = self.get_levels_near_price(price, tolerance_pct=0.3)
        total_nearby = sum(l.volume_usd for l in nearby)
        return total_nearby >= min_volume_usd
    
    def suggest_safer_stop(self, proposed_stop: float, direction: str) -> Tuple[float, str]:
        """
        Suggest a safer stop that avoids liquidation clusters.
        
        Returns (new_stop_price, reason)
        """
        if not self.is_price_at_liq_cluster(proposed_stop):
            return proposed_stop, "Stop is clear of liquidation clusters"
        
        # Find nearby levels
        nearby = self.get_levels_near_price(proposed_stop, tolerance_pct=0.5)
        if not nearby:
            return proposed_stop, "No adjustment needed"
        
        # For longs, move stop BELOW the cluster
        # For shorts, move stop ABOVE the cluster
        if direction == "long":
            lowest_liq = min(l.price for l in nearby)
            new_stop = lowest_liq * 0.997  # 0.3% below cluster
            reason = f"Moved stop below ${lowest_liq:,.0f} liquidation cluster"
        else:
            highest_liq = max(l.price for l in nearby)
            new_stop = highest_liq * 1.003  # 0.3% above cluster
            reason = f"Moved stop above ${highest_liq:,.0f} liquidation cluster"
        
        return new_stop, reason
    
    def to_dict(self):
        return {
            'symbol': self.symbol,
            'current_price': self.current_price,
            'levels': [
                {'price': l.price, 'volume_usd': l.volume_usd, 'type': l.liq_type}
                for l in self.levels[:10]  # Top 10
            ],
            'nearest_long_liq': self.nearest_long_liq,
            'nearest_short_liq': self.nearest_short_liq,
            'total_long_liq_usd': self.total_long_liq_usd,
            'total_short_liq_usd': self.total_short_liq_usd,
        }


class LiquidationAnalyzer:
    """Analyzes liquidation data for stop placement optimization."""
    
    HELSINKI_QUANT_API = "http://77.42.29.188:5002"
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def analyze(self, symbol: str, current_price: float) -> LiquidationAnalysis:
        """
        Analyze liquidation levels for a symbol.
        
        Args:
            symbol: Trading pair
            current_price: Current market price
            
        Returns:
            LiquidationAnalysis with clusters and risk flags
        """
        analysis = LiquidationAnalysis(
            symbol=symbol,
            current_price=current_price,
        )
        
        try:
            response = await self.client.get(
                f"{self.HELSINKI_QUANT_API}/quant/liquidations/{symbol}"
            )
            
            if response.status_code != 200:
                return analysis
            
            data = response.json()
            
        except Exception as e:
            logger.warning(f"Liquidation data fetch failed: {e}")
            return analysis
        
        # Parse levels
        raw_levels = data.get('liquidation_levels', [])
        for level_data in raw_levels:
            level = LiquidationLevel(
                price=level_data['price'],
                volume_usd=level_data['volume_usd'],
                liq_type=level_data['type'],
                distance_pct=((level_data['price'] - current_price) / current_price) * 100,
            )
            analysis.levels.append(level)
        
        # Sort by volume (largest first)
        analysis.levels.sort(key=lambda l: l.volume_usd, reverse=True)
        
        # Find nearest levels
        longs_below = [l for l in analysis.levels if l.liq_type == 'long' and l.price < current_price]
        shorts_above = [l for l in analysis.levels if l.liq_type == 'short' and l.price > current_price]
        
        if longs_below:
            analysis.nearest_long_liq = max(l.price for l in longs_below)
        if shorts_above:
            analysis.nearest_short_liq = min(l.price for l in shorts_above)
        
        # Aggregates
        analysis.total_long_liq_usd = data.get('total_long_liq_usd', 0.0)
        analysis.total_short_liq_usd = data.get('total_short_liq_usd', 0.0)
        
        return analysis
    
    async def close(self):
        await self.client.aclose()
```

---

## 3. Integration with RiskEngine

Modify `core/risk_engine.py` to use these analyzers:

### Add to imports:
```python
from .funding_analyzer import FundingAnalyzer, FundingAnalysis
from .liquidation_analyzer import LiquidationAnalyzer, LiquidationAnalysis
```

### Add to `__init__`:
```python
def __init__(self, config: Optional[RiskEngineConfig] = None):
    self.config = config or RiskEngineConfig()
    
    # ... existing analyzers ...
    
    # NEW: Risk-relevant data
    self.funding_analyzer = FundingAnalyzer()
    self.liquidation_analyzer = LiquidationAnalyzer()
```

### Add to RiskLevels dataclass:
```python
@dataclass
class RiskLevels:
    # ... existing fields ...
    
    # NEW: Funding rate context
    funding_analysis: Optional[FundingAnalysis] = None
    
    # NEW: Liquidation awareness
    liquidation_analysis: Optional[LiquidationAnalysis] = None
    stop_at_liq_cluster: bool = False
```

### Modify `calculate_risk_levels`:
```python
async def calculate_risk_levels(self, ...):
    # ... existing code ...
    
    # Step 10: Funding Rate Analysis
    levels.funding_analysis = await self.funding_analyzer.analyze(symbol, direction)
    
    # Adjust position size based on funding
    if levels.funding_analysis.size_adjustment_factor < 1.0:
        levels.position_size *= levels.funding_analysis.size_adjustment_factor
        levels.position_size_pct *= levels.funding_analysis.size_adjustment_factor
        logger.info(f"Position reduced by {(1 - levels.funding_analysis.size_adjustment_factor)*100:.0f}% due to funding")
    
    # Step 11: Liquidation Level Check
    levels.liquidation_analysis = await self.liquidation_analyzer.analyze(symbol, levels.current_price)
    
    # Check if primary stop is at a liq cluster
    if levels.stops:
        primary_stop = levels.stops[0]['price']
        if levels.liquidation_analysis.is_price_at_liq_cluster(primary_stop):
            levels.stop_at_liq_cluster = True
            new_stop, reason = levels.liquidation_analysis.suggest_safer_stop(primary_stop, direction)
            
            # Add warning but don't auto-adjust (let user decide)
            levels.stops[0]['warning'] = f"Stop at liquidation cluster! Consider {new_stop:.2f}"
            logger.warning(f"Stop at liq cluster: {reason}")
    
    return levels
```

---

## 4. API Response Update

Add to `api/models.py`:

```python
class FundingContextResponse(BaseModel):
    """Funding rate context."""
    current_rate: float = Field(description="Current funding rate per 8h")
    annualized_rate: float = Field(description="Annualized funding rate %")
    bias: str = Field(description="Funding bias: bullish/bearish/neutral")
    holding_cost_daily_pct: float = Field(description="Daily holding cost %")
    size_adjusted: bool = Field(default=False, description="Was size reduced?")


class LiquidationContextResponse(BaseModel):
    """Liquidation level context."""
    nearest_long_liq: Optional[float] = Field(description="Nearest long liquidation below")
    nearest_short_liq: Optional[float] = Field(description="Nearest short liquidation above")
    stop_at_cluster: bool = Field(default=False, description="Is stop at liq cluster?")
    cluster_warning: Optional[str] = Field(default=None)
```

Update `RiskLevelsResponse` to include:
```python
class RiskLevelsResponse(BaseModel):
    # ... existing fields ...
    
    funding_context: Optional[FundingContextResponse] = None
    liquidation_context: Optional[LiquidationContextResponse] = None
```

---

## 5. Frontend Display

Add to sidebar in the institutional chart:

```html
<!-- Funding Rate Card -->
<div class="sidebar-section">
    <div class="section-title">Funding Rate</div>
    <div class="funding-display">
        <div class="funding-rate" id="fundingRate">+0.0100%</div>
        <div class="funding-label">per 8h</div>
    </div>
    <div class="funding-cost" id="fundingCost">
        Daily cost: <span>0.03%</span>
    </div>
</div>

<!-- Liquidation Warning -->
<div class="sidebar-section" id="liqWarning" style="display: none;">
    <div class="warning-card">
        <div class="warning-icon">⚠️</div>
        <div class="warning-text">
            Stop at liquidation cluster!
            <span id="liqSuggestion">Consider $92,200</span>
        </div>
    </div>
</div>
```

---

## 6. Testing Checklist

- [ ] Funding rate fetched from Helsinki VM
- [ ] Position size reduced when funding is extreme
- [ ] Liquidation levels fetched and parsed
- [ ] Stop checked against liq clusters
- [ ] Warning shown when stop is at cluster
- [ ] API response includes funding/liq data
- [ ] Frontend displays funding rate
- [ ] Frontend shows liq warning when applicable

---

## Summary

| Component | What It Does |
|-----------|--------------|
| `funding_analyzer.py` | Fetches funding, calculates holding cost, adjusts size |
| `liquidation_analyzer.py` | Fetches liq levels, warns if stop at cluster |
| `risk_engine.py` updates | Integrates both into risk calculation |
| `models.py` updates | Adds response models |
| Frontend updates | Displays funding + liq warnings |

These are the **only institutional features needed** for a pure risk engine. Everything else is signal/edge.


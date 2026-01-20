# BASTION FINAL FIXES - Comprehensive Task List

## Current Status: 65% Complete
## Target: 95% Institutional Grade

Last Updated: January 2026
Reviewed against: `http://localhost:8001/app/trade-manager.html`

---

## Executive Summary

The backend is **solid (80%)**. The frontend has made **significant progress** but still has critical gaps:

| Component | Status | Issue |
|-----------|--------|-------|
| Chart rendering | ✅ 90% | Working with Lightweight Charts |
| Horizontal price lines | ✅ 100% | Entry, stops, targets all draw |
| **ANGLED guarding line** | ❌ 0% | **Still horizontal - needs Canvas overlay** |
| **Volume profile (VPVR)** | ❌ 0% | **No histogram visualization** |
| Multi-shot UI | ✅ 85% | Working but execution is client-side only |
| Real API integration | ⚠️ 60% | Not calling `/calculate` - uses local math |
| Live price updates | ✅ 100% | Polling `/price/{symbol}` |
| Guarding activation | ⚠️ 70% | Works but not using API response |
| Session persistence | ❌ 20% | UI exists but not persisting to backend |
| **Funding rate display** | ❌ 0% | **Not implemented (backend or frontend)** |
| **Liquidation warnings** | ❌ 0% | **Not implemented** |

---

## 🔴 CRITICAL: Angled Guarding Line

### Current Problem

The guarding line is drawn as a **horizontal line**:

```javascript
// Line 1583-1590 in trade-manager.html
priceLines.push(candleSeries.createPriceLine({
    price: state.guardingLevel,  // HORIZONTAL - WRONG
    color: '#00c853',
    lineWidth: 2,
    ...
}));
```

### What It Should Be

The guarding line should be an **angled/sloped line** that rises (for longs) as bars progress:

```
Price
  |                    ╱ Guarding Line (rising)
  |                   ╱
  |                  ╱
  |                 ╱
  |               ╱
  |              ╱ Entry
  |            ╱
  +----------------------------------→ Time
```

### Solution: Canvas Overlay

Lightweight Charts doesn't support native trendlines. Use a **Canvas overlay**:

```javascript
// Add this to trade-manager.html

class GuardingLineOverlay {
    constructor(chartContainer, chart, candleSeries) {
        this.container = chartContainer;
        this.chart = chart;
        this.candleSeries = candleSeries;
        this.canvas = null;
        this.guardingParams = null;
        this.direction = 'long';
        
        this.createCanvas();
        this.setupResizeHandler();
    }
    
    createCanvas() {
        this.canvas = document.createElement('canvas');
        this.canvas.id = 'guardingOverlay';
        this.canvas.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 10;
        `;
        this.container.style.position = 'relative';
        this.container.appendChild(this.canvas);
    }
    
    setupResizeHandler() {
        const resizeObserver = new ResizeObserver(() => this.render());
        resizeObserver.observe(this.container);
        
        // Re-render on chart scroll/zoom
        this.chart.timeScale().subscribeVisibleTimeRangeChange(() => this.render());
    }
    
    setGuardingLine(params, direction) {
        // params = { slope, intercept, activation_bar, start_time }
        this.guardingParams = params;
        this.direction = direction;
        this.render();
    }
    
    render() {
        if (!this.guardingParams || !this.canvas) return;
        
        const rect = this.container.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        
        const ctx = this.canvas.getContext('2d');
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        const { slope, intercept, start_time, activation_bar } = this.guardingParams;
        
        // Get time scale for coordinate conversion
        const timeScale = this.chart.timeScale();
        const visibleRange = timeScale.getVisibleLogicalRange();
        if (!visibleRange) return;
        
        // Calculate line points
        const startLogical = visibleRange.from;
        const endLogical = visibleRange.to;
        
        // Convert logical bar indices to prices along the guarding line
        const startPrice = intercept + (slope * Math.max(0, startLogical - start_time));
        const endPrice = intercept + (slope * Math.max(0, endLogical - start_time));
        
        // Convert to screen coordinates
        const startX = timeScale.logicalToCoordinate(startLogical);
        const endX = timeScale.logicalToCoordinate(endLogical);
        
        const priceScale = this.chart.priceScale('right');
        // Note: priceToCoordinate not directly available, use series
        // We'll approximate using the visible price range
        
        const priceRange = this.candleSeries.priceScale().minValue !== undefined;
        
        // Alternative: Use bounding client approach
        // Calculate Y positions based on price axis
        const chartHeight = this.canvas.height;
        const visibleBars = this.chart.timeScale().getVisibleLogicalRange();
        
        // Draw the line
        ctx.beginPath();
        ctx.strokeStyle = '#58a6ff';
        ctx.lineWidth = 2;
        ctx.setLineDash([8, 4]);
        
        // For now, draw from activation point forward
        // This is a simplified version - full implementation needs price-to-pixel conversion
        
        // Glow effect
        ctx.shadowColor = '#58a6ff';
        ctx.shadowBlur = 8;
        
        ctx.moveTo(startX || 0, this.priceToY(startPrice));
        ctx.lineTo(endX || this.canvas.width, this.priceToY(endPrice));
        ctx.stroke();
        
        // Label
        ctx.fillStyle = '#58a6ff';
        ctx.font = '10px JetBrains Mono, monospace';
        ctx.fillText('GUARD', (endX || this.canvas.width) - 50, this.priceToY(endPrice) - 8);
    }
    
    priceToY(price) {
        // Convert price to Y coordinate
        // This needs access to the visible price range
        // Simplified: get from chart's price scale
        
        // Fallback: percentage-based
        const visibleBars = this.chart.timeScale().getVisibleLogicalRange();
        // ... implementation needs price scale access
        
        return this.canvas.height / 2; // Placeholder
    }
    
    clear() {
        if (this.canvas) {
            const ctx = this.canvas.getContext('2d');
            ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        }
        this.guardingParams = null;
    }
}
```

### Better Alternative: Use LineSeries for Angled Line

Lightweight Charts' `LineSeries` can draw angled lines by providing multiple data points:

```javascript
// In initChart(), add:
const guardingLineSeries = chart.addLineSeries({
    color: '#58a6ff',
    lineWidth: 2,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
});

// When guarding activates, draw the angled line:
function drawAngledGuardingLine(startTime, startPrice, slope, barsToProject = 50) {
    const data = [];
    
    // Generate points along the guarding line
    for (let i = 0; i <= barsToProject; i++) {
        const time = startTime + (i * getTimeframeSeconds(currentTimeframe));
        const price = startPrice + (slope * i);
        data.push({ time, value: price });
    }
    
    guardingLineSeries.setData(data);
}

function getTimeframeSeconds(tf) {
    const map = {
        '1m': 60,
        '5m': 300,
        '15m': 900,
        '1h': 3600,
        '4h': 14400,
        '1d': 86400,
    };
    return map[tf] || 14400;
}
```

---

## 🔴 CRITICAL: Volume Profile (VPVR) Visualization

### Current Problem

The backend calculates VPVR (`core/vpvr_analyzer.py`) but **nowhere is it visualized**.

### Solution: Add Volume Profile Histogram

Create a new overlay that draws the volume profile on the right edge of the chart:

```javascript
// volume-profile.js

class VolumeProfileOverlay {
    constructor(chartContainer, options = {}) {
        this.container = chartContainer;
        this.canvas = null;
        this.data = null;
        this.width = options.width || 60;
        
        this.colors = {
            hvn: '#3fb950',      // High volume = green
            lvn: '#21262d',      // Low volume = gray
            poc: '#58a6ff',      // Point of control = blue
            vah: '#d29922',      // Value area high
            val: '#d29922',      // Value area low
        };
        
        this.createCanvas();
    }
    
    createCanvas() {
        this.canvas = document.createElement('canvas');
        this.canvas.style.cssText = `
            position: absolute;
            top: 0;
            right: 52px;  /* To the left of price scale */
            width: ${this.width}px;
            height: 100%;
            pointer-events: none;
            z-index: 5;
        `;
        this.container.appendChild(this.canvas);
    }
    
    setData(vpvrData) {
        /*
        vpvrData = {
            price_bins: [92000, 92500, 93000, ...],
            volume_at_price: [1000, 5000, 2000, ...],
            hvn_indices: [3, 7, 12],
            lvn_indices: [5, 10],
            poc_index: 7,
            value_area: { vah: 98000, val: 93500 }
        }
        */
        this.data = vpvrData;
        this.render();
    }
    
    render() {
        if (!this.data) return;
        
        const rect = this.container.getBoundingClientRect();
        this.canvas.width = this.width;
        this.canvas.height = rect.height;
        
        const ctx = this.canvas.getContext('2d');
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        const { price_bins, volume_at_price, hvn_indices, lvn_indices, poc_index, value_area } = this.data;
        
        if (!price_bins || price_bins.length === 0) return;
        
        const maxVolume = Math.max(...volume_at_price);
        const priceRange = price_bins[price_bins.length - 1] - price_bins[0];
        const chartHeight = this.canvas.height * 0.8; // Leave margin
        const topMargin = this.canvas.height * 0.1;
        
        for (let i = 0; i < price_bins.length; i++) {
            const price = price_bins[i];
            const volume = volume_at_price[i];
            
            // Calculate Y position (inverted - higher price = lower Y)
            const priceRatio = (price - price_bins[0]) / priceRange;
            const y = topMargin + chartHeight - (priceRatio * chartHeight);
            
            // Calculate bar width
            const barWidth = (volume / maxVolume) * this.width * 0.9;
            
            // Determine color
            let color = this.colors.lvn;
            if (hvn_indices && hvn_indices.includes(i)) color = this.colors.hvn;
            if (i === poc_index) color = this.colors.poc;
            
            // Opacity based on value area
            const inValueArea = value_area && price >= value_area.val && price <= value_area.vah;
            ctx.globalAlpha = inValueArea ? 0.9 : 0.5;
            
            // Draw bar
            ctx.fillStyle = color;
            ctx.fillRect(this.width - barWidth, y - 2, barWidth, 4);
        }
        
        ctx.globalAlpha = 1.0;
        
        // Draw POC line
        if (poc_index !== undefined) {
            const pocPrice = price_bins[poc_index];
            const pocY = topMargin + chartHeight - ((pocPrice - price_bins[0]) / priceRange * chartHeight);
            
            ctx.strokeStyle = this.colors.poc;
            ctx.lineWidth = 1;
            ctx.setLineDash([4, 2]);
            ctx.beginPath();
            ctx.moveTo(0, pocY);
            ctx.lineTo(this.width, pocY);
            ctx.stroke();
        }
    }
    
    clear() {
        if (this.canvas) {
            const ctx = this.canvas.getContext('2d');
            ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        }
    }
}
```

### Backend API Addition

Add VPVR data to the `/calculate` response:

```python
# In api/server.py, after calculating risk levels:

return {
    # ... existing response ...
    "vpvr": {
        "price_bins": levels.vpvr_analysis.price_bins.tolist() if levels.vpvr_analysis else [],
        "volume_at_price": levels.vpvr_analysis.volume_at_price.tolist() if levels.vpvr_analysis else [],
        "hvn_indices": [i for i, node in enumerate(levels.vpvr_analysis.hvn_nodes)] if levels.vpvr_analysis else [],
        "poc_index": levels.vpvr_analysis.poc_index if levels.vpvr_analysis else 0,
        "value_area": levels.vpvr_analysis.value_area.to_dict() if levels.vpvr_analysis else {},
    }
}
```

---

## 🟡 MEDIUM: API Integration Issues

### Current Problem

`trade-manager.html` does **NOT call the `/calculate` endpoint**. It calculates stops/targets client-side:

```javascript
// Line 1713-1726 - All local math, no API call
const atr = Math.abs(state.entryPrice - state.supportLevel) * 0.2;
const structural = state.direction === 'long' ?
    state.supportLevel - atr : state.supportLevel + atr;
// ...
const t1 = state.entryPrice + (riskDist * 2);
```

### Solution

Call the API when session starts:

```javascript
async function startSession() {
    // ... existing code ...
    
    // Call the BASTION API for proper risk calculation
    const response = await fetch(`${API}/calculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            symbol: state.symbol,
            entry_price: state.entryPrice,
            direction: state.direction,
            timeframe: '4h',
            account_balance: state.account,
            risk_per_trade_pct: 2.0
        })
    });
    
    const data = await response.json();
    
    // Use API response for stops/targets
    state.stops = data.stops;
    state.targets = data.targets;
    state.guardingParams = data.guarding_line;
    state.vpvrData = data.vpvr;
    
    // Draw with real data
    drawRiskLevelsFromAPI(data);
    
    // Set up volume profile
    if (volumeProfile && data.vpvr) {
        volumeProfile.setData(data.vpvr);
    }
}
```

---

## 🟡 MEDIUM: Session Persistence

### Current Problem

Sessions exist only in browser memory. Refreshing loses everything.

### Solution

Use the existing session API:

```javascript
async function startSession() {
    // ... calculate everything ...
    
    // Create persistent session
    const sessionRes = await fetch(`${API}/session/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            symbol: state.symbol,
            direction: state.direction,
            entry_price: state.entryPrice,
            account_balance: state.account,
            support_level: state.supportLevel,
        })
    });
    
    const session = await sessionRes.json();
    state.sessionId = session.session_id;
    
    // Save to localStorage as backup
    localStorage.setItem('activeSession', JSON.stringify(state));
}

// On page load, check for active session
async function checkActiveSession() {
    const saved = localStorage.getItem('activeSession');
    if (saved) {
        const parsed = JSON.parse(saved);
        // Restore session...
    }
}
```

---

## 🟡 MEDIUM: Funding Rate Display (Backend + Frontend)

### Backend Addition

Create `core/funding_analyzer.py` (see `AGENT_TASK_FUNDING_LIQUIDATION.md`)

### Frontend Addition

```html
<!-- Add to right panel in trade-manager.html -->
<div class="section" id="fundingSection" style="display: none;">
    <div class="section-title">Funding Rate</div>
    <div class="funding-card">
        <div class="funding-rate" id="fundingRate">+0.0100%</div>
        <div class="funding-label">per 8h</div>
        <div class="funding-cost" id="fundingCost">Daily: 0.03%</div>
    </div>
</div>
```

```javascript
async function loadFundingRate() {
    try {
        const res = await fetch(`${API}/funding/${state.symbol}`);
        const data = await res.json();
        
        document.getElementById('fundingRate').textContent = 
            `${data.current_rate >= 0 ? '+' : ''}${(data.current_rate * 100).toFixed(4)}%`;
        document.getElementById('fundingCost').textContent = 
            `Daily: ${data.holding_cost_daily_pct.toFixed(2)}%`;
        
        // Color based on direction vs funding
        const isCostly = (state.direction === 'long' && data.current_rate > 0) ||
                         (state.direction === 'short' && data.current_rate < 0);
        document.getElementById('fundingRate').style.color = isCostly ? 'var(--red)' : 'var(--green)';
        
    } catch (e) {
        console.warn('Funding rate unavailable');
    }
}
```

---

## 🟢 LOW: Visual Polish

### Issues

1. Too many bright colors (cyan targets, green guarding, red stops)
2. Phase indicators could be more subtle
3. Some font inconsistencies

### Recommendations

```css
/* Mute the colors slightly */
:root {
    /* Change from bright to muted */
    --green: #238636;      /* Was #00c853 */
    --red: #da3633;        /* Was #dc143c */
    --blue: #388bfd;       /* Was #2196f3 */
    --cyan: #79c0ff;       /* For targets */
    
    /* Add proper grays */
    --gray-1: #f0f6fc;
    --gray-2: #c9d1d9;
    --gray-3: #8b949e;
    --gray-4: #6e7681;
    --gray-5: #484f58;
}
```

---

## Implementation Checklist

### Day 1: Angled Guarding Line
- [ ] Add `LineSeries` for guarding line to `initChart()`
- [ ] Create `drawAngledGuardingLine()` function
- [ ] Integrate with `activateGuarding()` to use slope from API
- [ ] Test with different timeframes
- [ ] Add guarding line legend to chart

### Day 2: Volume Profile
- [ ] Create `VolumeProfileOverlay` class
- [ ] Add VPVR data to `/calculate` API response
- [ ] Instantiate overlay in chart initialization
- [ ] Call `volumeProfile.setData()` after API response
- [ ] Style with proper colors (HVN green, LVN gray, POC blue)

### Day 3: API Integration
- [ ] Replace local calculations with `/calculate` API call
- [ ] Use `data.stops` and `data.targets` from response
- [ ] Use `data.guarding_line` parameters
- [ ] Use `data.vpvr` for volume profile
- [ ] Add loading state during API call

### Day 4: Session Persistence
- [ ] Call `POST /session/` when starting
- [ ] Store `session_id` in state
- [ ] Save to localStorage as backup
- [ ] Add `checkActiveSession()` on page load
- [ ] Show session recovery prompt if found

### Day 5: Funding + Liquidation
- [ ] Implement `FundingAnalyzer` in backend
- [ ] Add `/funding/{symbol}` endpoint
- [ ] Add funding display to frontend
- [ ] Implement `LiquidationAnalyzer` in backend  
- [ ] Add `/liquidations/{symbol}` endpoint
- [ ] Show warning if stop is at liq cluster

### Day 6: Polish
- [ ] Update color palette to muted tones
- [ ] Ensure all numbers use JetBrains Mono
- [ ] Test responsive layout
- [ ] Add keyboard shortcuts
- [ ] Final testing

---

## File Changes Summary

| File | Changes |
|------|---------|
| `web/trade-manager.html` | Add guarding LineSeries, API integration, volume profile |
| `web/volume-profile.js` | NEW - Volume profile overlay component |
| `api/server.py` | Add VPVR to response, add funding/liq endpoints |
| `core/funding_analyzer.py` | NEW - Funding rate analysis |
| `core/liquidation_analyzer.py` | NEW - Liquidation level analysis |
| `web/styles.css` | Update color palette |

---

## Success Criteria

| Feature | Test |
|---------|------|
| Angled guarding | Line visibly slopes upward for long trades |
| Volume profile | Histogram visible on right edge of chart |
| API integration | Console shows `/calculate` call |
| Session persistence | Refresh page, session still there |
| Funding display | Shows current funding rate with color |

---

## Priority Order

1. **🔴 Angled Guarding Line** - Most requested, most visible
2. **🔴 Volume Profile** - Key MCF differentiator  
3. **🟡 API Integration** - Correctness of calculations
4. **🟡 Session Persistence** - User experience
5. **🟡 Funding/Liquidation** - Institutional features
6. **🟢 Visual Polish** - Final touches

---

## Notes for Agent

- The backend is **solid** - focus on frontend integration
- `chart.js` already has good patterns - extend it
- Don't break existing functionality when adding features
- Test in Chrome and Firefox
- Keep the file under 2000 lines - split if needed


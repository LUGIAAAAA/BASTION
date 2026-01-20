# AGENT TASK: Institutional-Grade Chart Component

## Priority: CRITICAL
## Estimated Time: 3-4 days
## Dependencies: TradingView Lightweight Charts (MIT)

---

## Executive Summary

The current BASTION frontend is **15% complete** and looks amateur. We need a Bloomberg/TradingView-quality charting component that:

1. Renders real candlestick data from the API
2. Draws risk levels as **actual lines on the chart** (not colored boxes)
3. Visualizes the **guarding line as an angled, rising line**
4. Shows **volume profile histogram** on the price axis
5. Updates in **real-time via WebSocket**

---

## Current State (What's Wrong)

### `index.html`:
- Mobile-first 480px layout (should be desktop)
- Shows stops/targets as **colored boxes** not chart lines
- No actual candlestick chart
- Hardcoded simulation data

### `trade-manager.html`:
- CSS divs pretending to be a chart:
```css
.guarding-line {
    position: absolute;
    width: 100%;
    height: 3px;
    background: linear-gradient(90deg, rgba(0, 255, 136, 0.3), #00ff88);
}
```
- This is NOT institutional quality

---

## Target State (What We Need)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  BTCUSDT │ 94,328.00 │ +1.23% │ 4H                          ◉ LIVE     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ $98,500 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  VAH ────────────  ████ │
│                         ╱╲                                         ███ │
│ $97,500 ═══════════════╱══╲════════════════════  T1 (33%) ══════  ████ │
│                       ╱    ╲      ╱╲                              █████│
│ $96,200 ─ ─ ─ ─ ─ ─ ─╱─ ─ ─ ╲─ ─ ╱─ ╲─ ─ ─ ─ ─  POC ───────────  █████│
│                     ╱        ╲  ╱    ╲                            ████ │
│ $95,500 ═══════════╱══════════╲╱══════╲════════  T2 (33%) ══════   ███ │
│                   ╱            ║       ╲                           ██  │
│ $94,500 ════════•════════════════════════════  ENTRY ════════════  ██  │
│                ╱               ║         ╲                         █   │
│               ╱     ╱╲         ║          ╲    ╱╲                  █   │
│ $93,800 ────╱─────╱──╲────────╱────────────╲──╱──╲───  GUARD ──── (7)  │
│            ╱     ╱    ╲      ╱              ╲╱    ╲     ↗ rising       │
│ $92,500 ──╱─────────────────────────────────────────  STOP ══════      │
│          ╱                                                             │
│         ╱                                                              │
├─────────────────────────────────────────────────────────────────────────┤
│  ║ Volume Profile                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key Visual Elements**:
- **Candlesticks**: Real OHLCV data
- **Volume Profile**: Histogram on right edge showing HVN/LVN
- **Entry Line**: Horizontal gold/amber dashed line
- **Stop Lines**: Horizontal red lines (solid for primary, dashed for secondary)
- **Target Lines**: Horizontal green lines with exit % labels
- **Guarding Line**: **ANGLED cyan line** that rises with each bar
- **Current Price**: Animated marker that moves with live updates

---

## Technical Requirements

### 1. Charting Library

Use **TradingView Lightweight Charts** (MIT License):
```html
<script src="https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
```

Why this library:
- Used by TradingView, Binance, Coinbase
- Canvas-based (performant)
- Native price lines, trend lines support
- Dark theme built-in
- 50KB gzipped

### 2. File Structure

```
bastion/web/
├── index.html           # REPLACE - Full dashboard
├── chart.js             # NEW - Chart component
├── api-client.js        # NEW - API wrapper
├── websocket.js         # NEW - Live updates
├── styles.css           # REPLACE - Institutional styling
└── components/
    ├── price-ladder.js  # Price levels sidebar
    ├── position-card.js # Position info
    └── session-list.js  # Active sessions
```

### 3. API Endpoints to Use

```javascript
// Get OHLCV data for chart
GET /bars/{symbol}?timeframe=4h&limit=200

// Calculate risk levels (on form submit)
POST /calculate
{
    "symbol": "BTCUSDT",
    "entry_price": 94500,
    "direction": "long",
    "timeframe": "4h",
    "account_balance": 100000,
    "risk_per_trade_pct": 1.0
}

// Live price stream
GET /price/{symbol}  // Poll every 2s or use WebSocket

// Session management
GET /session/         // List sessions
POST /session/        // Create session
GET /session/{id}     // Get session details
```

### 4. Chart Component Specification

```javascript
// chart.js - Core chart component

class BastionChart {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.chart = null;
        this.candleSeries = null;
        this.volumeSeries = null;
        this.lines = {};  // Store drawn lines
        this.guardingLine = null;
        
        this.colors = {
            background: '#0d1117',
            grid: '#21262d',
            text: '#8b949e',
            textBright: '#c9d1d9',
            
            // Level colors
            entry: '#d29922',       // Amber/gold
            stop: '#f85149',        // Red
            stopSecondary: '#da3633',
            target: '#3fb950',      // Green
            guarding: '#58a6ff',    // Cyan/blue
            
            // Candles
            up: '#3fb950',
            down: '#f85149',
            
            // Volume profile
            hvn: '#238636',         // Mountain
            lvn: '#f85149',         // Valley
            poc: '#58a6ff',         // Point of control
        };
        
        this.init();
    }
    
    init() {
        this.chart = LightweightCharts.createChart(this.container, {
            width: this.container.clientWidth,
            height: this.container.clientHeight,
            layout: {
                background: { color: this.colors.background },
                textColor: this.colors.text,
            },
            grid: {
                vertLines: { color: this.colors.grid },
                horzLines: { color: this.colors.grid },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
            },
            rightPriceScale: {
                borderColor: this.colors.grid,
            },
            timeScale: {
                borderColor: this.colors.grid,
                timeVisible: true,
            },
        });
        
        // Candlestick series
        this.candleSeries = this.chart.addCandlestickSeries({
            upColor: this.colors.up,
            downColor: this.colors.down,
            borderVisible: false,
            wickUpColor: this.colors.up,
            wickDownColor: this.colors.down,
        });
        
        // Volume series (bottom)
        this.volumeSeries = this.chart.addHistogramSeries({
            color: '#26a69a',
            priceFormat: { type: 'volume' },
            priceScaleId: '',
            scaleMargins: { top: 0.8, bottom: 0 },
        });
    }
    
    // Load OHLCV data
    async loadData(symbol, timeframe = '4h', limit = 200) {
        const response = await fetch(`/bars/${symbol}?timeframe=${timeframe}&limit=${limit}`);
        const data = await response.json();
        
        // Format for lightweight-charts
        const candles = data.bars.map(bar => ({
            time: bar.timestamp / 1000,  // Unix seconds
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
        }));
        
        const volumes = data.bars.map(bar => ({
            time: bar.timestamp / 1000,
            value: bar.volume,
            color: bar.close >= bar.open ? this.colors.up + '80' : this.colors.down + '80',
        }));
        
        this.candleSeries.setData(candles);
        this.volumeSeries.setData(volumes);
        
        return candles;
    }
    
    // Draw entry line
    drawEntryLine(price) {
        this.lines.entry = this.candleSeries.createPriceLine({
            price: price,
            color: this.colors.entry,
            lineWidth: 2,
            lineStyle: LightweightCharts.LineStyle.Dashed,
            axisLabelVisible: true,
            title: 'ENTRY',
        });
    }
    
    // Draw stop lines
    drawStopLines(stops) {
        stops.forEach((stop, i) => {
            const isMain = stop.type === 'structural' || stop.type === 'primary';
            this.lines[`stop_${i}`] = this.candleSeries.createPriceLine({
                price: stop.price,
                color: isMain ? this.colors.stop : this.colors.stopSecondary,
                lineWidth: isMain ? 2 : 1,
                lineStyle: isMain ? LightweightCharts.LineStyle.Solid : LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: true,
                title: stop.type.toUpperCase(),
            });
        });
    }
    
    // Draw target lines
    drawTargetLines(targets) {
        targets.forEach((target, i) => {
            this.lines[`target_${i}`] = this.candleSeries.createPriceLine({
                price: target.price,
                color: this.colors.target,
                lineWidth: 2,
                lineStyle: LightweightCharts.LineStyle.Solid,
                axisLabelVisible: true,
                title: `T${i+1} (${target.exit_percentage}%)`,
            });
        });
    }
    
    // Draw guarding line (ANGLED - this is the key feature)
    drawGuardingLine(guardingParams, entryBar, currentBar) {
        if (!guardingParams) return;
        
        const { slope, intercept, activation_bar } = guardingParams;
        const barsActive = currentBar - entryBar - activation_bar;
        
        if (barsActive < 0) {
            // Not yet active - show as dashed horizontal
            this.guardingLine = this.candleSeries.createPriceLine({
                price: intercept,
                color: this.colors.guarding + '60',
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dotted,
                axisLabelVisible: false,
                title: `GUARD (${activation_bar - (currentBar - entryBar)} bars)`,
            });
            return;
        }
        
        // Active - draw as angled trend line
        // NOTE: Lightweight Charts doesn't have native trendlines
        // We need to use markers or a custom overlay
        
        // For now, use price line at current level
        const currentLevel = intercept + (slope * barsActive);
        this.guardingLine = this.candleSeries.createPriceLine({
            price: currentLevel,
            color: this.colors.guarding,
            lineWidth: 2,
            lineStyle: LightweightCharts.LineStyle.Solid,
            axisLabelVisible: true,
            title: 'GUARD',
        });
        
        // TODO: Add Canvas overlay for proper angled line
        // See drawAngledGuardingLine() below
    }
    
    // Draw angled guarding line using Canvas overlay
    drawAngledGuardingLine(startBar, startPrice, slope, barsCount) {
        // Get the canvas overlay
        const chartElement = this.container.querySelector('canvas');
        if (!chartElement) return;
        
        // Create overlay canvas
        let overlay = this.container.querySelector('.guarding-overlay');
        if (!overlay) {
            overlay = document.createElement('canvas');
            overlay.className = 'guarding-overlay';
            overlay.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                pointer-events: none;
            `;
            this.container.appendChild(overlay);
        }
        
        overlay.width = this.container.clientWidth;
        overlay.height = this.container.clientHeight;
        
        const ctx = overlay.getContext('2d');
        ctx.clearRect(0, 0, overlay.width, overlay.height);
        
        // Convert price/bar to pixel coordinates
        const timeScale = this.chart.timeScale();
        const priceScale = this.candleSeries.priceScale();
        
        // Calculate start and end points
        const startX = timeScale.logicalToCoordinate(startBar);
        const endX = timeScale.logicalToCoordinate(startBar + barsCount);
        
        const startY = priceScale.priceToCoordinate(startPrice);
        const endPrice = startPrice + (slope * barsCount);
        const endY = priceScale.priceToCoordinate(endPrice);
        
        // Draw the angled line
        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(endX, endY);
        ctx.strokeStyle = this.colors.guarding;
        ctx.lineWidth = 2;
        ctx.setLineDash([8, 4]);  // Dashed
        ctx.stroke();
        
        // Draw glow effect
        ctx.shadowColor = this.colors.guarding;
        ctx.shadowBlur = 10;
        ctx.stroke();
    }
    
    // Clear all lines
    clearLines() {
        Object.values(this.lines).forEach(line => {
            this.candleSeries.removePriceLine(line);
        });
        this.lines = {};
        
        if (this.guardingLine) {
            this.candleSeries.removePriceLine(this.guardingLine);
            this.guardingLine = null;
        }
    }
    
    // Update with new candle
    updateCandle(candle) {
        this.candleSeries.update({
            time: candle.timestamp / 1000,
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close,
        });
    }
    
    // Resize handler
    resize() {
        this.chart.applyOptions({
            width: this.container.clientWidth,
            height: this.container.clientHeight,
        });
    }
}
```

### 5. Volume Profile Overlay

```javascript
// volume-profile.js - VPVR visualization

class VolumeProfileOverlay {
    constructor(chart, candleSeries, options = {}) {
        this.chart = chart;
        this.candleSeries = candleSeries;
        this.canvas = null;
        this.data = null;
        
        this.colors = {
            hvn: '#238636',
            lvn: '#21262d',
            poc: '#58a6ff',
            val: '#30363d',
        };
        
        this.width = options.width || 80;  // Pixel width of histogram
        
        this.createCanvas();
    }
    
    createCanvas() {
        const container = this.chart.chartElement().parentElement;
        
        this.canvas = document.createElement('canvas');
        this.canvas.style.cssText = `
            position: absolute;
            top: 0;
            right: 60px;  /* Right of price scale */
            width: ${this.width}px;
            height: 100%;
            pointer-events: none;
        `;
        container.appendChild(this.canvas);
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
        
        const ctx = this.canvas.getContext('2d');
        const { width, height } = this.canvas.getBoundingClientRect();
        this.canvas.width = width;
        this.canvas.height = height;
        
        ctx.clearRect(0, 0, width, height);
        
        const { price_bins, volume_at_price, hvn_indices, poc_index, value_area } = this.data;
        const maxVolume = Math.max(...volume_at_price);
        const priceScale = this.candleSeries.priceScale();
        
        for (let i = 0; i < price_bins.length; i++) {
            const price = price_bins[i];
            const volume = volume_at_price[i];
            
            // Convert price to Y coordinate
            const y = priceScale.priceToCoordinate(price);
            if (y === null) continue;
            
            // Calculate bar width based on volume
            const barWidth = (volume / maxVolume) * width * 0.9;
            
            // Determine color
            let color = this.colors.lvn;
            if (hvn_indices.includes(i)) color = this.colors.hvn;
            if (i === poc_index) color = this.colors.poc;
            
            // Value area tint
            if (price >= value_area.val && price <= value_area.vah) {
                ctx.globalAlpha = 0.8;
            } else {
                ctx.globalAlpha = 0.5;
            }
            
            // Draw bar
            ctx.fillStyle = color;
            ctx.fillRect(width - barWidth, y - 2, barWidth, 4);
        }
        
        ctx.globalAlpha = 1.0;
    }
}
```

---

## 6. CSS Design System

```css
/* styles.css - Institutional Design System */

:root {
    /* Colors - Bloomberg Dark Theme */
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --bg-tertiary: #21262d;
    --border: #30363d;
    --border-muted: #21262d;
    
    /* Text */
    --text-primary: #c9d1d9;
    --text-secondary: #8b949e;
    --text-muted: #6e7681;
    --text-link: #58a6ff;
    
    /* Semantic - Trade */
    --color-long: #3fb950;
    --color-short: #f85149;
    --color-neutral: #8b949e;
    --color-entry: #d29922;
    --color-guarding: #58a6ff;
    
    /* Semantic - Data */
    --color-positive: #3fb950;
    --color-negative: #f85149;
    --color-warning: #d29922;
    
    /* Typography */
    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif;
    --font-mono: ui-monospace, 'SF Mono', 'Cascadia Code', 'Source Code Pro', Menlo, Consolas, monospace;
    
    /* Spacing */
    --space-1: 4px;
    --space-2: 8px;
    --space-3: 12px;
    --space-4: 16px;
    --space-5: 24px;
    --space-6: 32px;
    
    /* Borders */
    --radius-sm: 3px;
    --radius-md: 6px;
    --radius-lg: 8px;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: var(--font-sans);
    font-size: 14px;
    line-height: 1.5;
    color: var(--text-primary);
    background: var(--bg-primary);
    -webkit-font-smoothing: antialiased;
}

/* Layout */
.dashboard {
    display: grid;
    grid-template-columns: 1fr 320px;
    grid-template-rows: 56px 1fr;
    height: 100vh;
    gap: 1px;
    background: var(--border);
}

.header {
    grid-column: 1 / -1;
    background: var(--bg-secondary);
    display: flex;
    align-items: center;
    padding: 0 var(--space-4);
    gap: var(--space-4);
}

.chart-container {
    background: var(--bg-primary);
    position: relative;
    overflow: hidden;
}

.sidebar {
    background: var(--bg-secondary);
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

/* Header Components */
.logo {
    font-family: var(--font-mono);
    font-size: 16px;
    font-weight: 600;
    letter-spacing: 0.05em;
    color: var(--text-muted);
}

.symbol-display {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
}

.symbol-name {
    font-family: var(--font-mono);
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
}

.symbol-price {
    font-family: var(--font-mono);
    font-size: 20px;
    font-weight: 600;
}

.symbol-change {
    font-family: var(--font-mono);
    font-size: 12px;
    padding: 2px 6px;
    border-radius: var(--radius-sm);
}

.symbol-change.positive {
    color: var(--color-positive);
    background: rgba(63, 185, 80, 0.1);
}

.symbol-change.negative {
    color: var(--color-negative);
    background: rgba(248, 81, 73, 0.1);
}

/* Live Indicator */
.live-indicator {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-left: auto;
    font-size: 12px;
    color: var(--text-muted);
}

.live-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--color-positive);
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

/* Sidebar Sections */
.sidebar-section {
    padding: var(--space-4);
    border-bottom: 1px solid var(--border);
}

.sidebar-section:last-child {
    border-bottom: none;
}

.section-title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin-bottom: var(--space-3);
}

/* Data Grid */
.data-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-3);
}

.data-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.data-label {
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
}

.data-value {
    font-family: var(--font-mono);
    font-size: 14px;
    font-weight: 500;
}

.data-value.positive { color: var(--color-positive); }
.data-value.negative { color: var(--color-negative); }
.data-value.highlight { color: var(--color-entry); }

/* Level List */
.level-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
}

.level-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-2) var(--space-3);
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
    border-left: 3px solid transparent;
}

.level-item.stop { border-left-color: var(--color-negative); }
.level-item.target { border-left-color: var(--color-positive); }
.level-item.entry { border-left-color: var(--color-entry); }
.level-item.guarding { border-left-color: var(--color-guarding); }

.level-type {
    font-size: 11px;
    text-transform: uppercase;
    color: var(--text-muted);
}

.level-price {
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 500;
}

.level-distance {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-muted);
}

/* Form Controls */
.form-group {
    margin-bottom: var(--space-3);
}

.form-label {
    display: block;
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    margin-bottom: var(--space-1);
}

.form-input {
    width: 100%;
    padding: var(--space-2) var(--space-3);
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: 14px;
}

.form-input:focus {
    outline: none;
    border-color: var(--color-guarding);
}

/* Direction Toggle */
.direction-toggle {
    display: flex;
    gap: 1px;
    background: var(--border);
    border-radius: var(--radius-md);
    overflow: hidden;
}

.direction-btn {
    flex: 1;
    padding: var(--space-3);
    background: var(--bg-tertiary);
    border: none;
    color: var(--text-muted);
    font-family: var(--font-sans);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
}

.direction-btn:hover {
    background: var(--bg-secondary);
    color: var(--text-primary);
}

.direction-btn.active.long {
    background: rgba(63, 185, 80, 0.15);
    color: var(--color-long);
}

.direction-btn.active.short {
    background: rgba(248, 81, 73, 0.15);
    color: var(--color-short);
}

/* Primary Button */
.btn-primary {
    width: 100%;
    padding: var(--space-3);
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
}

.btn-primary:hover {
    background: var(--bg-secondary);
    border-color: var(--color-guarding);
}

.btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

/* Guarding Status */
.guarding-status {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3);
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
}

.guarding-status.active {
    border-color: var(--color-guarding);
    background: rgba(88, 166, 255, 0.1);
}

.guarding-indicator {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--text-muted);
}

.guarding-status.active .guarding-indicator {
    background: var(--color-guarding);
    box-shadow: 0 0 8px var(--color-guarding);
    animation: pulse 2s infinite;
}

.guarding-label {
    font-size: 12px;
    color: var(--text-secondary);
}

.guarding-value {
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 500;
    margin-left: auto;
}

/* NO GRADIENTS, NO ROUNDED > 8px, NO BRIGHT COLORS */
```

---

## 7. Implementation Checklist

### Phase 1: Chart Core (Day 1)
- [ ] Set up Lightweight Charts in new `index.html`
- [ ] Create `chart.js` component class
- [ ] Load OHLCV data from `/bars/{symbol}`
- [ ] Render candlesticks + volume
- [ ] Implement resize handling

### Phase 2: Risk Levels Drawing (Day 2)
- [ ] Draw entry line (horizontal, amber)
- [ ] Draw stop lines (horizontal, red variants)
- [ ] Draw target lines (horizontal, green)
- [ ] Draw guarding line as horizontal (placeholder)
- [ ] Create Canvas overlay for angled guarding line

### Phase 3: Live Updates (Day 3)
- [ ] Connect to `/price/{symbol}` endpoint
- [ ] Update last candle in real-time
- [ ] Animate guarding line rising
- [ ] Show live P&L in sidebar
- [ ] WebSocket integration (if available)

### Phase 4: Sidebar + Forms (Day 3-4)
- [ ] Symbol selector
- [ ] Direction toggle
- [ ] Entry price / account balance inputs
- [ ] Calculate button → POST `/calculate`
- [ ] Display response in sidebar
- [ ] Price levels list with colors

### Phase 5: Volume Profile (Day 4)
- [ ] Create volume profile overlay
- [ ] Parse VPVR data from response
- [ ] Draw histogram on right edge
- [ ] Color HVN/LVN/POC differently

### Phase 6: Polish (Day 4)
- [ ] Apply institutional CSS
- [ ] Test dark theme
- [ ] Ensure no gradients/bright colors
- [ ] Test on different screen sizes
- [ ] Performance optimization

---

## 8. Success Criteria

| Requirement | Pass Criteria |
|-------------|---------------|
| Candlestick chart | Real data from API, not hardcoded |
| Stop/target lines | Drawn ON the chart as price lines |
| Guarding line | Visible as angled/rising line |
| Volume profile | Histogram visible on chart edge |
| Live updates | Price updates every 2-5 seconds |
| No gradients | Zero gradient backgrounds |
| No mobile-first | Desktop layout (min 1200px) |
| Monospace numbers | All prices in monospace font |
| Color discipline | Only levels are colored, rest is muted |

---

## 9. Files to Create

1. `web/index.html` - REPLACE completely
2. `web/chart.js` - NEW
3. `web/api-client.js` - NEW
4. `web/styles.css` - REPLACE completely
5. `web/volume-profile.js` - NEW (optional)

## 10. Files to Delete

1. `web/trade-manager.html` - Merge into new index.html
2. `web/session.html` - Merge into new index.html

---

## Reference: Bloomberg Terminal Aesthetics

1. **Dense information** - Every pixel has purpose
2. **Muted palette** - Grays dominate, colors only for data
3. **Monospace everywhere** - All numbers, prices, metrics
4. **No decoration** - No shadows, no gradients, no rounded corners
5. **Hierarchy through weight** - Bold vs regular, not size
6. **Status through color** - Green/red only for gain/loss
7. **Grid alignment** - Everything snaps to a grid

---

## Questions?

The core BASTION backend is solid. This task is 100% frontend visualization. The agent should NOT modify any Python files unless specifically needed for a new endpoint.

Start with the chart. Everything else is secondary.


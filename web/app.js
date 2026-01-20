const API_URL = 'http://localhost:8001';

let currentLevels = null;

document.getElementById('riskForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    await calculateRisk();
});

async function calculateRisk() {
    const form = document.getElementById('riskForm');
    const formData = new FormData(form);
    
    const data = {
        symbol: formData.get('symbol'),
        entry_price: parseFloat(formData.get('entry_price')),
        direction: formData.get('direction'),
        timeframe: formData.get('timeframe'),
        account_balance: parseFloat(formData.get('account_balance')),
        risk_per_trade_pct: parseFloat(formData.get('risk_pct'))
    };

    // Show loading
    document.getElementById('loading').style.display = 'block';
    document.getElementById('results').style.display = 'none';
    document.getElementById('error').style.display = 'none';
    document.getElementById('calculateBtn').disabled = true;

    try {
        const response = await fetch(`${API_URL}/calculate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to calculate risk');
        }

        const levels = await response.json();
        currentLevels = levels;
        displayResults(levels);
    } catch (error) {
        showError(error.message);
    } finally {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('calculateBtn').disabled = false;
    }
}

function displayResults(levels) {
    // Set title
    document.getElementById('resultsTitle').textContent = 
        `${levels.symbol} ${levels.direction.toUpperCase()}`;

    // Set prices
    document.getElementById('entryPrice').textContent = `$${levels.entry_price.toLocaleString()}`;
    document.getElementById('currentPrice').textContent = `$${levels.current_price.toLocaleString()}`;

    // Display market context
    if (levels.market_context) {
        const ctx = levels.market_context;
        
        // Structure quality (0-10)
        const structureEl = document.getElementById('structureQuality');
        structureEl.textContent = ctx.structure_quality.toFixed(1);
        structureEl.className = `context-value ${getScoreClass(ctx.structure_quality, 10)}`;
        
        // Volume score (0-10)
        const volumeEl = document.getElementById('volumeScore');
        volumeEl.textContent = ctx.volume_profile_score.toFixed(1);
        volumeEl.className = `context-value ${getScoreClass(ctx.volume_profile_score, 10)}`;
        
        // Order flow bias
        const flowEl = document.getElementById('orderflowBias');
        flowEl.textContent = ctx.orderflow_bias.toUpperCase();
        flowEl.className = `context-value ${getBiasClass(ctx.orderflow_bias)}`;
        
        // MTF alignment (0-1)
        const mtfEl = document.getElementById('mtfAlignment');
        mtfEl.textContent = `${(ctx.mtf_alignment * 100).toFixed(0)}%`;
        mtfEl.className = `context-value ${getScoreClass(ctx.mtf_alignment * 10, 10)}`;
    }

    // Display stops
    const stopsHtml = levels.stops.map(stop => `
        <div class="level-item">
            <div class="level-type">${stop.type.toUpperCase()}</div>
            <div class="level-price stop">$${stop.price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
            <div class="level-distance">${stop.distance_pct.toFixed(1)}%</div>
            <div class="level-reason">${stop.reason}</div>
        </div>
    `).join('');
    document.getElementById('stops').innerHTML = stopsHtml;

    // Display targets
    const targetsHtml = levels.targets.map((target, i) => `
        <div class="level-item">
            <div class="level-type">T${i + 1} <span class="exit-pct">${target.exit_percentage.toFixed(0)}%</span></div>
            <div class="level-price target">$${target.price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
            <div class="level-distance">+${target.distance_pct.toFixed(1)}%</div>
            <div class="level-reason">${target.reason}</div>
        </div>
    `).join('');
    document.getElementById('targets').innerHTML = targetsHtml;

    // Display position info
    const positionHtml = `
        <div class="level-item">
            <div class="level-type">Position Size</div>
            <div class="level-price">${levels.position_size.toFixed(4)}</div>
        </div>
        <div class="level-item">
            <div class="level-type">Risk Amount</div>
            <div class="level-price">$${levels.risk_amount.toLocaleString()}</div>
        </div>
        <div class="level-item">
            <div class="level-type">Risk:Reward</div>
            <div class="level-price">${levels.risk_reward_ratio.toFixed(1)}R - ${levels.max_risk_reward_ratio.toFixed(1)}R</div>
        </div>
    `;
    document.getElementById('position').innerHTML = positionHtml;

    // Show results
    document.getElementById('results').style.display = 'block';
}

function getScoreClass(score, max) {
    const pct = score / max;
    if (pct >= 0.7) return 'score-high';
    if (pct >= 0.4) return 'score-medium';
    return 'score-low';
}

function getBiasClass(bias) {
    if (bias === 'bullish') return 'bias-bullish';
    if (bias === 'bearish') return 'bias-bearish';
    return 'bias-neutral';
}

function showError(message) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = `Error: ${message}`;
    errorDiv.style.display = 'block';
}

function copyLevels() {
    if (!currentLevels) return;

    const text = formatLevelsForCopy(currentLevels);
    
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.querySelector('.btn-copy');
        btn.textContent = 'Copied!';
        setTimeout(() => {
            btn.textContent = 'Copy Levels';
        }, 2000);
    });
}

function formatLevelsForCopy(levels) {
    let text = `BASTION RISK LEVELS - ${levels.symbol} ${levels.direction.toUpperCase()}\n`;
    text += `${'='.repeat(50)}\n\n`;
    text += `Entry: $${levels.entry_price.toLocaleString()}\n`;
    text += `Current: $${levels.current_price.toLocaleString()}\n\n`;
    
    // Market Context
    if (levels.market_context) {
        const ctx = levels.market_context;
        text += `MARKET CONTEXT:\n`;
        text += `  Structure Quality: ${ctx.structure_quality.toFixed(1)}/10\n`;
        text += `  Volume Profile: ${ctx.volume_profile_score.toFixed(1)}/10\n`;
        text += `  Order Flow: ${ctx.orderflow_bias.toUpperCase()}\n`;
        text += `  MTF Alignment: ${(ctx.mtf_alignment * 100).toFixed(0)}%\n\n`;
    }
    
    text += `STOPS:\n`;
    levels.stops.forEach(stop => {
        text += `  ${stop.type.toUpperCase()}: $${stop.price.toLocaleString()} (${stop.distance_pct.toFixed(1)}%)\n`;
    });
    
    text += `\nTARGETS:\n`;
    levels.targets.forEach((target, i) => {
        text += `  T${i + 1}: $${target.price.toLocaleString()} (+${target.distance_pct.toFixed(1)}%, ${target.exit_percentage.toFixed(0)}% exit)\n`;
    });
    
    text += `\nPOSITION:\n`;
    text += `  Size: ${levels.position_size.toFixed(4)}\n`;
    text += `  Risk: $${levels.risk_amount.toLocaleString()}\n`;
    text += `  R:R: ${levels.risk_reward_ratio.toFixed(1)}R - ${levels.max_risk_reward_ratio.toFixed(1)}R\n`;
    
    return text;
}

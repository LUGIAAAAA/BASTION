# 🚀 CURSOR AGENT START HERE

## ✅ Project Setup Complete

The BASTION workspace has been fully prepared. All directory structures, templates, and documentation are in place.

---

## 📂 What's Been Created

```
C:\Users\Banke\MCF-Project\bastion\
├── api/
│   ├── __init__.py           ✅ Created
│   ├── server.py             ✅ Created (needs core integration)
│   └── models.py             ✅ Created
├── core/                     ❌ NEEDS: Copy files from riskshield/
├── data/                     ❌ NEEDS: Copy fetcher from mcf_live_service/
├── web/
│   ├── index.html            ✅ Created
│   ├── styles.css            ✅ Created
│   └── app.js                ✅ Created
├── tests/
│   └── __init__.py           ✅ Created
├── docs/
│   ├── API.md                ✅ Created
│   └── EXAMPLES.md           ✅ Created
├── requirements.txt          ✅ Created
├── README.md                 ✅ Created
├── run.py                    ✅ Created
├── .gitignore                ✅ Created
└── __init__.py               ✅ Created
```

---

## 🎯 YOUR MISSION (7-Day Build)

### **Priority 1: Copy Core Files (Day 1 - Morning)**

**Task:** Copy existing working code into the bastion/ directory.

```powershell
# Navigate to bastion
cd C:\Users\Banke\MCF-Project\bastion

# Copy RiskShield core files
Copy-Item ..\riskshield\core\engine.py core\engine.py
Copy-Item ..\riskshield\core\models.py core\models.py
Copy-Item ..\riskshield\core\living_tp.py core\living_tp.py
Copy-Item ..\riskshield\core\guarding_line.py core\guarding_line.py
Copy-Item ..\riskshield\core\adaptive_budget.py core\adaptive_budget.py

# Copy data fetcher
Copy-Item ..\mcf_live_service\data_fetcher.py data\fetcher.py
```

**Verification:**
```powershell
# Check files exist
ls core\*.py
ls data\*.py
```

---

### **Priority 2: Install Dependencies (Day 1 - Morning)**

```powershell
cd C:\Users\Banke\MCF-Project\bastion

# Create virtual environment (optional but recommended)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

---

### **Priority 3: Test API Server (Day 1 - Afternoon)**

```powershell
# Start the server
python run.py
```

**Expected Output:**
```
╔═══════════════════════════════════════════════╗
║                                               ║
║              BASTION API Server               ║
║                                               ║
║      Proactive Risk Management                ║
║                                               ║
╚═══════════════════════════════════════════════╝

Starting server on http://0.0.0.0:8001
```

**Test Health Endpoint:**
```powershell
# In new terminal
curl http://localhost:8001/health
```

**Expected Response:**
```json
{
  "status": "ok",
  "service": "BASTION",
  "version": "1.0.0-MVP"
}
```

---

### **Priority 4: Test Calculate Endpoint (Day 1 - Afternoon)**

```powershell
# Test with curl
curl -X POST http://localhost:8001/calculate -H "Content-Type: application/json" -d '{\"symbol\":\"BTCUSDT\",\"entry_price\":95000,\"direction\":\"long\",\"timeframe\":\"4h\",\"account_balance\":100000,\"risk_per_trade_pct\":1.0}'
```

**If this works, you have a working MVP!**

---

### **Priority 5: Test Web Calculator (Day 2)**

1. **Start API server** (if not already running)
2. **Open browser** to `http://localhost:8001/app/` (note trailing slash)
3. **Fill in form:**
   - Symbol: BTCUSDT
   - Entry Price: 95000
   - Direction: LONG
   - Timeframe: 4H
   - Risk %: 1.0
   - Account Balance: 100000
4. **Click "Calculate Risk Levels"**
5. **Verify results display correctly**

---

### **Priority 6: Debug & Fix Issues (Days 2-3)**

**Common Issues:**

#### Issue 1: Import errors in server.py
```python
# If you get import errors, adjust sys.path in server.py
import sys
from pathlib import Path
bastion_path = Path(__file__).parent.parent
sys.path.insert(0, str(bastion_path.parent))
```

#### Issue 2: Data fetcher failing
```python
# Check Helsinki VM is accessible
# Test manually:
import requests
r = requests.get('http://77.42.29.188:5000/api/klines/BTCUSDT?interval=1h&limit=200')
print(r.status_code, r.json()[:2])  # Should return 200 and candle data
```

#### Issue 3: Engine calculation errors
```python
# Add logging to engine.py
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add debug prints in calculate_risk_levels()
logger.debug(f"Calculating for {setup.symbol} {setup.direction}")
```

---

### **Priority 7: Write Tests (Days 4-5)**

Create `tests/test_api.py`:

```python
import pytest
from fastapi.testclient import TestClient
from bastion.api.server import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_calculate_btc_long():
    response = client.post("/calculate", json={
        "symbol": "BTCUSDT",
        "entry_price": 95000,
        "direction": "long",
        "timeframe": "4h",
        "account_balance": 100000,
        "risk_per_trade_pct": 1.0
    })
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTCUSDT"
    assert len(data["stops"]) > 0
    assert len(data["targets"]) > 0
```

**Run tests:**
```powershell
pytest tests/test_api.py -v
```

---

### **Priority 8: Polish & Document (Days 6-7)**

1. **Fix any remaining bugs**
2. **Update README.md** with actual setup steps
3. **Add more examples** to EXAMPLES.md
4. **Take screenshots** of web calculator
5. **Test on different symbols** (ETH, SOL, etc.)
6. **Test edge cases** (very high/low prices, extreme risk %)

---

## 🔍 KEY FILES TO FOCUS ON

### 1. `api/server.py` (MOST IMPORTANT)
This is the main FastAPI application. Make sure:
- All imports work
- `/calculate` endpoint works
- Error handling is robust
- Logging is verbose enough

### 2. `data/fetcher.py`
This fetches market data. Make sure:
- Helsinki VM connection works
- Fallback to Binance works
- Data is formatted correctly for engine

### 3. `core/engine.py`
This is the risk calculation logic. Make sure:
- All dependencies are available
- Calculations don't crash
- Results are reasonable

---

## ✅ SUCCESS CHECKLIST

Mark these off as you complete them:

### Day 1
- [ ] Core files copied successfully
- [ ] Dependencies installed
- [ ] API server starts without errors
- [ ] `/health` endpoint returns 200
- [ ] `/calculate` endpoint works for BTCUSDT

### Day 2
- [ ] Web calculator loads in browser
- [ ] Form submission works
- [ ] Results display correctly
- [ ] Copy function works

### Day 3-4
- [ ] Tested with multiple symbols
- [ ] Tested long and short positions
- [ ] Tested different timeframes
- [ ] Fixed all bugs found

### Day 5-6
- [ ] Unit tests written
- [ ] All tests pass
- [ ] Documentation updated
- [ ] Code is clean and commented

### Day 7
- [ ] Final testing complete
- [ ] README accurate
- [ ] Ready for user testing
- [ ] Deployment-ready

---

## 🚨 IF YOU GET STUCK

### Problem: Import errors
**Solution:** Check sys.path configuration in server.py. Make sure bastion's parent directory is in path.

### Problem: Helsinki VM timeout
**Solution:** The fetcher has a fallback to Binance. Make sure fallback logic works.

### Problem: Engine calculation crashes
**Solution:** Add try/except around engine.calculate_risk_levels() and log the full error.

### Problem: Web calculator doesn't connect to API
**Solution:** Check CORS is configured in server.py. Check API_URL in app.js is correct.

---

## 📞 REFERENCE DOCUMENTATION

- **Build Instructions:** `C:\Users\Banke\MCF-Project\BASTION_BUILD_INSTRUCTIONS.md`
- **API Docs:** `bastion/docs/API.md`
- **Examples:** `bastion/docs/EXAMPLES.md`
- **Helsinki VM Docs:** `C:\Users\Banke\IROS_Lives\HELSINKI_VM_PHASE2_ALL_QUANT_FEATURES.md`

---

## 🎯 FINAL DELIVERABLES

When done, you should have:

1. ✅ Working API at `http://localhost:8001`
2. ✅ Web calculator at `http://localhost:8001/app/`
3. ✅ All tests passing
4. ✅ Complete documentation
5. ✅ Clean, commented code

---

## 🎉 COMPLETION CRITERIA

The build is complete when:
1. User can input a trade setup in web calculator
2. Click "Calculate Risk Levels"
3. See stops, targets, and position size
4. Copy the levels for manual execution
5. All of this happens in <3 seconds

---

**START HERE. BUILD METHODICALLY. TEST FREQUENTLY.**

**You've got this. 🏰**


# 🏰 BASTION - Quick Reference Card

## 📍 Location
```
C:\Users\Banke\MCF-Project\bastion\
```

## 🚀 Quick Start (For Next Agent)

### 1. Copy Core Files (PowerShell)
```powershell
cd C:\Users\Banke\MCF-Project\bastion

Copy-Item ..\riskshield\core\engine.py core\
Copy-Item ..\riskshield\core\models.py core\
Copy-Item ..\riskshield\core\living_tp.py core\
Copy-Item ..\riskshield\core\guarding_line.py core\
Copy-Item ..\riskshield\core\adaptive_budget.py core\
Copy-Item ..\mcf_live_service\data_fetcher.py data\fetcher.py
```

### 2. Install
```powershell
pip install -r requirements.txt
```

### 3. Run
```powershell
python run.py
```

### 4. Test
```powershell
curl http://localhost:8001/health
```

---

## 📂 Key Files

| File | Purpose |
|------|---------|
| `CURSOR_AGENT_START_HERE.md` | **START HERE** - Step-by-step guide |
| `BASTION_BUILD_INSTRUCTIONS.md` | Detailed 7-day build plan |
| `WORKSPACE_SUMMARY.md` | Complete setup summary |
| `api/server.py` | Main FastAPI application |
| `web/index.html` | Calculator UI |
| `docs/API.md` | API documentation |

---

## 🎯 Mission

Build a working risk management calculator:
- **Input:** Trade setup (symbol, entry, direction)
- **Output:** Stops, targets, position size
- **Time:** 1 week
- **Status:** Templates ready, needs assembly

---

## ✅ What's Done
- ✅ Directory structure
- ✅ All templates created
- ✅ Documentation complete
- ✅ Brand/design defined
- ✅ API models defined
- ✅ Web UI ready

## ⏳ What's Needed
- ⏳ Copy core engine files
- ⏳ Test API integration
- ⏳ Debug & polish
- ⏳ Write unit tests

---

## 🔗 External Dependencies

- Helsinki VM: `77.42.29.188:5000` (data)
- Binance API (fallback)
- Existing RiskShield code

---

## 📞 Help

Read these in order:
1. `CURSOR_AGENT_START_HERE.md`
2. `BASTION_BUILD_INSTRUCTIONS.md`
3. `docs/API.md`

**Everything you need is documented. Just follow the steps.**

---

**🏰 Ready to build. Good luck!**


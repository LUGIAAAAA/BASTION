"""
BASTION API Tests
=================

Test suite for the BASTION risk management API.

Run with: pytest tests/test_api.py -v
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient


@pytest.fixture(scope="function")
def client():
    """Create a fresh test client for each test."""
    # Import inside fixture to ensure fresh module state
    from api.server import app
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    """Tests for the /health endpoint."""
    
    def test_health_returns_200(self, client):
        """Health endpoint should return 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_health_returns_correct_status(self, client):
        """Health endpoint should return status 'ok'."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"
    
    def test_health_returns_service_name(self, client):
        """Health endpoint should return service name 'BASTION'."""
        response = client.get("/health")
        data = response.json()
        assert data["service"] == "BASTION"
    
    def test_health_returns_version(self, client):
        """Health endpoint should return version."""
        response = client.get("/health")
        data = response.json()
        assert "version" in data
        assert data["version"] == "1.0.0-MVP"


class TestRootEndpoint:
    """Tests for the root / endpoint."""
    
    def test_root_returns_200(self, client):
        """Root endpoint should return 200 OK."""
        response = client.get("/")
        assert response.status_code == 200
    
    def test_root_returns_api_info(self, client):
        """Root endpoint should return API information."""
        response = client.get("/")
        data = response.json()
        assert data["service"] == "BASTION API"
        assert "docs" in data
        assert "health" in data
        assert "calculate" in data


class TestCalculateEndpointValidation:
    """Tests for /calculate endpoint input validation."""
    
    def test_calculate_requires_entry_price(self, client):
        """Calculate endpoint should require entry_price."""
        response = client.post("/calculate", json={
            "symbol": "BTCUSDT",
            "direction": "long",
            "timeframe": "4h"
        })
        assert response.status_code == 422  # Validation error
    
    def test_calculate_requires_direction(self, client):
        """Calculate endpoint should require direction."""
        response = client.post("/calculate", json={
            "symbol": "BTCUSDT",
            "entry_price": 95000,
            "timeframe": "4h"
        })
        assert response.status_code == 422
    
    def test_calculate_validates_direction(self, client):
        """Calculate endpoint should only accept 'long' or 'short'."""
        response = client.post("/calculate", json={
            "symbol": "BTCUSDT",
            "entry_price": 95000,
            "direction": "sideways",  # Invalid
            "timeframe": "4h"
        })
        assert response.status_code == 422
    
    def test_calculate_validates_positive_entry_price(self, client):
        """Calculate endpoint should require positive entry price."""
        response = client.post("/calculate", json={
            "symbol": "BTCUSDT",
            "entry_price": -1000,
            "direction": "long",
            "timeframe": "4h"
        })
        assert response.status_code == 422


# Integration tests that require network access
@pytest.mark.skipif(
    True,  # Skip by default - set to False to run integration tests
    reason="Integration tests require network access"
)
class TestCalculateEndpointIntegration:
    """Integration tests for /calculate endpoint (require network)."""
    
    def test_calculate_btc_long(self, client):
        """Calculate endpoint should work for BTC long position."""
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
        assert data["direction"] == "long"
        assert len(data["stops"]) > 0
        assert len(data["targets"]) > 0
    
    def test_calculate_btc_short(self, client):
        """Calculate endpoint should work for BTC short position."""
        response = client.post("/calculate", json={
            "symbol": "BTCUSDT",
            "entry_price": 95000,
            "direction": "short",
            "timeframe": "4h",
            "account_balance": 100000,
            "risk_per_trade_pct": 1.0
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data["symbol"] == "BTCUSDT"
        assert data["direction"] == "short"


class TestCoreComponents:
    """Tests for core risk engine components (no network required)."""
    
    def test_risk_engine_import(self):
        """RiskEngine should be importable."""
        from core.engine import RiskEngine
        engine = RiskEngine()
        assert engine is not None
    
    def test_trade_setup_import(self):
        """TradeSetup model should be importable."""
        from core.models import TradeSetup
        setup = TradeSetup(
            entry_price=95000,
            direction="long",
            timeframe="4h",
            symbol="BTCUSDT"
        )
        assert setup.entry_price == 95000
        assert setup.direction == "long"
    
    def test_market_context_atr_calculation(self):
        """MarketContext should calculate ATR."""
        from core.models import MarketContext
        from datetime import datetime
        
        # Create mock market data
        highs = [100, 102, 101, 103, 100, 99, 101, 102, 100, 98, 99, 100, 101, 102, 103]
        lows = [98, 99, 99, 100, 97, 97, 99, 100, 98, 96, 97, 98, 99, 100, 101]
        closes = [99, 101, 100, 101, 99, 98, 100, 101, 99, 97, 98, 99, 100, 101, 102]
        
        market = MarketContext(
            timestamps=[datetime.now()] * 15,
            opens=[99] * 15,
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=[1000] * 15,
            current_price=102
        )
        
        # ATR should be calculated
        atr = market.atr
        assert atr > 0
    
    def test_stop_level_creation(self):
        """StopLevel should be creatable."""
        from core.models import StopLevel, StopType
        
        stop = StopLevel(
            price=92500,
            type=StopType.PRIMARY,
            confidence=0.8,
            reason="Below support",
            distance_pct=2.6
        )
        
        assert stop.price == 92500
        assert stop.type == StopType.PRIMARY
    
    def test_target_level_creation(self):
        """TargetLevel should be creatable."""
        from core.models import TargetLevel, TargetType
        
        target = TargetLevel(
            price=98000,
            type=TargetType.STRUCTURAL,
            exit_percentage=33,
            confidence=0.7,
            reason="Resistance level",
            distance_pct=3.2
        )
        
        assert target.price == 98000
        assert target.exit_percentage == 33
    
    def test_risk_engine_with_mock_data(self):
        """RiskEngine should calculate levels with mock market data."""
        from core.engine import RiskEngine
        from core.models import TradeSetup, MarketContext
        from datetime import datetime
        
        engine = RiskEngine()
        
        # Create mock market data with enough bars
        n_bars = 200
        base_price = 95000
        
        # Simulate some price movement
        import random
        random.seed(42)
        
        closes = [base_price]
        for _ in range(n_bars - 1):
            change = random.uniform(-200, 200)
            closes.append(closes[-1] + change)
        
        highs = [c + random.uniform(50, 150) for c in closes]
        lows = [c - random.uniform(50, 150) for c in closes]
        opens = [closes[i-1] if i > 0 else closes[0] for i in range(len(closes))]
        
        market = MarketContext(
            timestamps=[datetime.now()] * n_bars,
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=[1000000] * n_bars,
            current_price=closes[-1]
        )
        
        setup = TradeSetup(
            entry_price=95000,
            direction="long",
            timeframe="4h",
            symbol="BTCUSDT",
            account_balance=100000,
            risk_per_trade_pct=1.0
        )
        
        # Calculate risk levels
        levels = engine.calculate_risk_levels(setup, market)
        
        # Verify results
        assert len(levels.stops) > 0
        assert len(levels.targets) > 0
        assert levels.position_size > 0
        assert levels.risk_amount > 0
        
        # For long, stops should be below entry
        for stop in levels.stops:
            assert stop.price < setup.entry_price
        
        # For long, targets should be above entry
        for target in levels.targets:
            assert target.price > setup.entry_price


class TestGuardingLine:
    """Tests for guarding line calculations."""
    
    def test_guarding_line_import(self):
        """GuardingLine should be importable."""
        from core.guarding_line import GuardingLine
        gl = GuardingLine()
        assert gl is not None
    
    def test_guarding_line_calculation(self):
        """GuardingLine should calculate initial line."""
        from core.guarding_line import GuardingLine
        
        gl = GuardingLine(activation_bars=10)
        
        # Mock lows for a long position
        lows = [94000, 93800, 93900, 94100, 94000, 93700, 93800, 94000, 94200, 94100,
                94300, 94500, 94400, 94600, 94700, 94500, 94800, 94900, 95000, 95100]
        
        line = gl.calculate_initial_line(
            entry_price=95000,
            direction="long",
            price_data=lows
        )
        
        assert "slope" in line
        assert "intercept" in line
        assert "activation_bar" in line
    
    def test_guarding_line_level(self):
        """GuardingLine should return current level."""
        from core.guarding_line import GuardingLine
        
        gl = GuardingLine(activation_bars=5)
        
        line = {
            "slope": 50,
            "intercept": 94000,
            "activation_bar": 5,
            "buffer_pct": 0.3
        }
        
        # Before activation
        level_before = gl.get_current_level(line, bars_since_entry=3)
        
        # After activation
        level_after = gl.get_current_level(line, bars_since_entry=10)
        
        # After activation, level should be higher (for positive slope)
        assert level_after > level_before


class TestAdaptiveBudget:
    """Tests for adaptive risk budget system."""
    
    def test_budget_creation(self):
        """Should create a risk budget."""
        from core.adaptive_budget import AdaptiveRiskBudget
        
        budget_mgr = AdaptiveRiskBudget(max_shots=3, total_risk_cap=2.0)
        budget = budget_mgr.create_budget("BTCUSDT", "long")
        
        assert budget is not None
        assert budget.symbol == "BTCUSDT"
        assert budget.direction == "long"
        assert budget.can_take_shot
    
    def test_shot_taking(self):
        """Should take shots against budget."""
        from core.adaptive_budget import AdaptiveRiskBudget
        
        budget_mgr = AdaptiveRiskBudget(max_shots=3, total_risk_cap=2.0)
        budget = budget_mgr.create_budget("BTCUSDT", "long")
        
        # Take first shot
        shot = budget_mgr.take_shot(
            budget.id,
            entry_price=95000,
            stop_price=93000,
            account_balance=100000
        )
        
        assert shot is not None
        assert shot.entry_price == 95000
        assert shot.size > 0
        assert budget.risk_used > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

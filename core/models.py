"""
RiskShield Data Models
======================

Clean, serializable data structures for the risk management engine.
Designed for easy integration with any trading platform.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class StopType(Enum):
    """Types of stop-loss levels."""
    PRIMARY = "primary"          # Structural stop - tightest
    SECONDARY = "secondary"      # Backup stop - gives room to breathe  
    SAFETY_NET = "safety_net"    # Emergency stop - max loss protection
    GUARDING = "guarding"        # Trailing structural stop


class TargetType(Enum):
    """Types of take-profit targets."""
    STRUCTURAL = "structural"    # Based on S/R levels
    EXTENSION = "extension"      # Fibonacci extensions
    VOLUME_GAP = "volume_gap"    # VRVP valley targets
    TRAILING = "trailing"        # Dynamic trailing target


class Direction(Enum):
    """Trade direction."""
    LONG = "long"
    SHORT = "short"


@dataclass
class StopLevel:
    """A single stop-loss level with metadata."""
    price: float
    type: StopType
    confidence: float           # 0-1 confidence in this level
    reason: str                 # Human-readable explanation
    distance_pct: float         # Distance from entry as percentage
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "price": self.price,
            "type": self.type.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "distance_pct": self.distance_pct
        }


@dataclass  
class TargetLevel:
    """A single take-profit target with metadata."""
    price: float
    type: TargetType
    exit_percentage: float      # What % of position to exit here
    confidence: float           # 0-1 confidence in this level
    reason: str                 # Human-readable explanation
    distance_pct: float         # Distance from entry as percentage
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "price": self.price,
            "type": self.type.value,
            "exit_percentage": self.exit_percentage,
            "confidence": self.confidence,
            "reason": self.reason,
            "distance_pct": self.distance_pct
        }


@dataclass
class RiskLevels:
    """
    Complete risk management output for a trade.
    
    This is the main output of the RiskEngine - contains everything
    needed to manage a trade's risk.
    """
    # Core levels
    stops: List[StopLevel]
    targets: List[TargetLevel]
    
    # Position sizing
    position_size: float                    # Recommended size in base currency
    position_size_pct: float               # As percentage of account
    risk_amount: float                      # Dollar risk per trade
    
    # Risk metrics
    risk_reward_ratio: float               # R:R to first target
    max_risk_reward_ratio: float           # R:R to final target
    win_probability: float                 # Estimated win probability
    expected_value: float                  # Expected value of trade
    
    # Metadata
    entry_price: float
    direction: str
    timeframe: str
    calculated_at: datetime = field(default_factory=datetime.now)
    
    # Optional: Guarding line for swing trades
    guarding_line: Optional[Dict[str, float]] = None  # {slope, intercept, activation_bar}
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for API responses."""
        return {
            "stops": [s.to_dict() for s in self.stops],
            "targets": [t.to_dict() for t in self.targets],
            "position_size": self.position_size,
            "position_size_pct": self.position_size_pct,
            "risk_amount": self.risk_amount,
            "risk_reward_ratio": self.risk_reward_ratio,
            "max_risk_reward_ratio": self.max_risk_reward_ratio,
            "win_probability": self.win_probability,
            "expected_value": self.expected_value,
            "entry_price": self.entry_price,
            "direction": self.direction,
            "timeframe": self.timeframe,
            "calculated_at": self.calculated_at.isoformat(),
            "guarding_line": self.guarding_line
        }
    
    def get_primary_stop(self) -> Optional[StopLevel]:
        """Get the tightest (primary) stop level."""
        primary = [s for s in self.stops if s.type == StopType.PRIMARY]
        return primary[0] if primary else None
    
    def get_first_target(self) -> Optional[TargetLevel]:
        """Get the first (closest) take-profit target."""
        return self.targets[0] if self.targets else None


@dataclass
class TradeSetup:
    """
    Input to the RiskEngine representing a potential trade.
    """
    entry_price: float
    direction: str              # "long" or "short"
    timeframe: str              # "1m", "5m", "15m", "1h", "4h", "1d"
    symbol: str                 # Trading pair/symbol
    
    # Optional: Account context for position sizing
    account_balance: float = 10000.0
    risk_per_trade_pct: float = 1.0  # Risk 1% per trade
    
    # Optional: User preferences
    max_stop_distance_pct: float = 5.0   # Max allowed stop distance
    min_rr_ratio: float = 2.0            # Minimum R:R to accept
    
    # Optional: Existing position context (for re-entries)
    existing_position_size: float = 0.0
    existing_avg_price: float = 0.0
    shots_taken: int = 0                  # How many entries already taken
    max_shots: int = 3                    # Maximum re-entries allowed


@dataclass
class MarketContext:
    """
    Market data context passed to the RiskEngine.
    
    Can be populated from any data source (TradingView, exchange API, etc.)
    """
    # OHLCV data (most recent first)
    timestamps: List[datetime]
    opens: List[float]
    highs: List[float]
    lows: List[float]
    closes: List[float]
    volumes: List[float]
    
    # Current price
    current_price: float
    
    # Optional: Pre-calculated levels (if available)
    support_levels: Optional[List[float]] = None
    resistance_levels: Optional[List[float]] = None
    
    # Optional: Volume profile data
    volume_profile: Optional[Dict[str, Any]] = None  # {poc, vah, val, hvn, lvn}
    
    # Optional: Regime info
    regime: Optional[str] = None  # "trending_up", "trending_down", "ranging", "volatile"
    
    @property
    def latest_close(self) -> float:
        return self.closes[0] if self.closes else self.current_price
    
    @property
    def atr(self) -> float:
        """Calculate ATR from the data."""
        if len(self.highs) < 14:
            return 0.0
        
        tr_values = []
        for i in range(min(14, len(self.highs) - 1)):
            high = self.highs[i]
            low = self.lows[i]
            prev_close = self.closes[i + 1]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)
        
        return sum(tr_values) / len(tr_values) if tr_values else 0.0


@dataclass
class PositionUpdate:
    """
    Real-time position update for dynamic stop/target adjustment.
    
    Send this to the engine as price moves to get updated levels.
    """
    current_price: float
    bars_since_entry: int
    highest_since_entry: float
    lowest_since_entry: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    
    # Optional: Recent candles for structure analysis
    recent_closes: Optional[List[float]] = None
    recent_highs: Optional[List[float]] = None
    recent_lows: Optional[List[float]] = None


@dataclass
class RiskUpdate:
    """
    Output from dynamic risk updates.
    
    Contains updated stops/targets and any triggered actions.
    """
    updated_stops: List[StopLevel]
    updated_targets: List[TargetLevel]
    
    # Signals
    exit_signal: bool = False
    exit_reason: Optional[str] = None
    exit_percentage: float = 0.0          # What % to exit
    
    # Trailing adjustments
    stop_moved: bool = False
    new_stop_price: Optional[float] = None
    
    # Guarding line status
    guarding_active: bool = False
    guarding_broken: bool = False


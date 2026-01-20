"""
BASTION Core Risk Engine - Pure Risk Management
================================================

BASTION is strategy-agnostic risk management.

What it DOES:
✅ Calculate optimal stops (structural, ATR-based, multi-tier)
✅ Calculate optimal targets (structural, volume-informed, dynamic)
✅ Position sizing (volatility-adjusted)
✅ Trade management (trailing stops, partial exits, guarding lines)
✅ Provide market context (structure quality, volume profile, order flow)
✅ Dynamic position updates (living TP, guarding line trailing)

What it DOES NOT do:
❌ Judge if your trade is "good" or "bad" (that's IROS)
❌ Give entry signals (that's your strategy)
❌ Score trade quality (that's IROS with MCF)

BASTION provides the infrastructure. You provide the strategy.

Author: MCF Labs / BASTION
Date: January 2026
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import numpy as np
import pandas as pd
from datetime import datetime
import logging
import asyncio

from .vpvr_analyzer import VPVRAnalyzer, VPVRAnalysis
from .structure_detector import StructureDetector, StructureAnalysis
from .mtf_structure import MTFStructureAnalyzer, MTFAlignment
from .orderflow_detector import OrderFlowDetector, OrderFlowAnalysis

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================

class StopType(str, Enum):
    """Types of stop-loss levels."""
    PRIMARY = "primary"          # Structural stop - tightest
    SECONDARY = "secondary"      # Backup stop - gives room to breathe  
    SAFETY_NET = "safety_net"    # Emergency stop - max loss protection
    GUARDING = "guarding"        # Trailing structural stop


class TargetType(str, Enum):
    """Types of take-profit targets."""
    STRUCTURAL = "structural"    # Based on S/R levels
    VPVR = "vpvr"               # Volume profile HVN
    EXTENSION = "extension"      # R-multiple extensions
    DYNAMIC = "dynamic"          # Added after entry as price extends


class StructureHealth(str, Enum):
    """Health status of supporting structure."""
    STRONG = "strong"       # Structure intact, no concerns
    WEAKENING = "weakening" # Structure showing stress
    BROKEN = "broken"       # Structure has failed


class VolatilityRegime(str, Enum):
    """Current volatility regime for position sizing adjustment."""
    LOW = "low"          # ATR < 50% of 100-day average - can use tighter stops
    NORMAL = "normal"    # ATR within 50-150% of average
    HIGH = "high"        # ATR > 150% of average - wider stops needed
    EXTREME = "extreme"  # ATR > 250% of average - reduce position size


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class TradeSetup:
    """Input to the RiskEngine representing a potential trade."""
    symbol: str
    entry_price: float
    direction: str              # "long" or "short"
    timeframe: str              # "1m", "5m", "15m", "1h", "4h", "1d"
    account_balance: float = 10000.0
    risk_per_trade_pct: float = 1.0


@dataclass
class PositionUpdate:
    """Real-time position update for dynamic stop/target adjustment."""
    current_price: float
    bars_since_entry: int
    highest_since_entry: float
    lowest_since_entry: float
    unrealized_pnl_pct: float
    recent_lows: Optional[List[float]] = None
    recent_highs: Optional[List[float]] = None


@dataclass
class RiskLevels:
    """Risk levels output - pure risk management, no trade scoring."""
    
    # Stop levels
    stops: List[Dict[str, Any]] = field(default_factory=list)
    
    # Target levels
    targets: List[Dict[str, Any]] = field(default_factory=list)
    
    # Position sizing
    position_size: float = 0.0
    position_size_pct: float = 0.0
    risk_amount: float = 0.0
    
    # Risk metrics
    risk_reward_ratio: float = 0.0
    max_risk_reward_ratio: float = 0.0
    
    # Entry context
    entry_price: float = 0.0
    direction: str = "long"
    timeframe: str = "4h"
    symbol: str = ""
    current_price: float = 0.0
    
    # Market Context (for your strategy to use - informational only)
    structure_quality: float = 0.0      # 0-10 from StructureDetector
    volume_profile_score: float = 0.0   # 0-10 from VPVRAnalyzer
    orderflow_bias: str = "neutral"     # bullish/bearish/neutral
    mtf_alignment: float = 0.0          # 0-1 alignment score
    
    # Guarding line (swing trades)
    guarding_line: Optional[Dict[str, Any]] = None
    
    # Detailed analyses (for advanced users)
    structure_analysis: Optional[StructureAnalysis] = None
    vpvr_analysis: Optional[VPVRAnalysis] = None
    orderflow_analysis: Optional[OrderFlowAnalysis] = None
    mtf_analysis: Optional[MTFAlignment] = None
    
    # === NEW: Entry Gate ===
    entry_blocked: bool = False          # True if entry should be blocked
    block_reason: Optional[str] = None   # Reason for blocking entry
    
    # === NEW: Volatility Context ===
    volatility_regime: str = "normal"    # low/normal/high/extreme
    atr_current: float = 0.0             # Current ATR value
    atr_pct: float = 0.0                 # ATR as % of price
    
    # === NEW: Breakeven tracking ===
    breakeven_price: float = 0.0         # Price for breakeven stop
    one_r_price: float = 0.0             # Price at +1R profit
    
    # Timestamp
    calculated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'entry_price': self.entry_price,
            'direction': self.direction,
            'current_price': self.current_price,
            'stops': self.stops,
            'targets': self.targets,
            'position_size': self.position_size,
            'position_size_pct': self.position_size_pct,
            'risk_amount': self.risk_amount,
            'risk_reward_ratio': self.risk_reward_ratio,
            'max_risk_reward_ratio': self.max_risk_reward_ratio,
            'market_context': {
                'structure_quality': self.structure_quality,
                'volume_profile_score': self.volume_profile_score,
                'orderflow_bias': self.orderflow_bias,
                'mtf_alignment': self.mtf_alignment,
                'volatility_regime': self.volatility_regime,
            },
            'guarding_line': self.guarding_line,
            'entry_gate': {
                'blocked': self.entry_blocked,
                'reason': self.block_reason,
            },
            'volatility': {
                'regime': self.volatility_regime,
                'atr': self.atr_current,
                'atr_pct': self.atr_pct,
            },
            'breakeven': {
                'breakeven_price': self.breakeven_price,
                'one_r_price': self.one_r_price,
            },
            'calculated_at': self.calculated_at.isoformat(),
        }
    
    def get_primary_stop(self) -> Optional[Dict]:
        """Get the tightest (primary) stop level."""
        for stop in self.stops:
            if stop.get('type') == 'primary' or stop.get('type') == 'structural':
                return stop
        return self.stops[0] if self.stops else None


@dataclass
class RiskUpdate:
    """Output from dynamic risk updates (position management)."""
    updated_stops: List[Dict[str, Any]] = field(default_factory=list)
    updated_targets: List[Dict[str, Any]] = field(default_factory=list)
    
    # Signals
    exit_signal: bool = False
    exit_reason: Optional[str] = None
    exit_percentage: float = 0.0
    
    # Trailing adjustments
    stop_moved: bool = False
    new_stop_price: Optional[float] = None
    stop_move_reason: Optional[str] = None
    
    # Guarding line status
    guarding_active: bool = False
    guarding_broken: bool = False
    guarding_level: Optional[float] = None
    
    # Structure health
    structure_health: StructureHealth = StructureHealth.STRONG
    
    # === NEW: Breakeven tracking ===
    breakeven_hit: bool = False          # True when +1R reached
    moved_to_breakeven: bool = False     # True when stop moved to BE
    current_r_multiple: float = 0.0      # Current R-multiple (profit/risk)
    
    # === NEW: Dynamic targets ===
    new_target_added: bool = False       # True if living TP added new target
    new_target_price: Optional[float] = None
    
    # === NEW: Divergence detection ===
    divergence_detected: bool = False
    divergence_type: Optional[str] = None  # "bearish" or "bullish"
    
    # === NEW: Momentum Trailing TP ===
    momentum_trailing_active: bool = False
    momentum_trailing_level: float = 0.0
    momentum_slope_strength: float = 0.0  # 0-1
    momentum_buffer_pct: float = 0.0
    
    # Alerts
    alerts: List[str] = field(default_factory=list)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class RiskEngineConfig:
    """Configuration for Risk Engine."""
    
    # Detection Systems (all optional)
    enable_structure_detection: bool = True
    enable_vpvr_analysis: bool = True
    enable_orderflow_detection: bool = True
    enable_mtf_analysis: bool = True
    
    # Stop-loss settings
    use_structural_stops: bool = True
    atr_stop_multiplier: float = 2.0
    max_stop_pct: float = 5.0
    enable_multi_tier_stops: bool = True
    
    # Take-profit settings
    use_structural_targets: bool = True
    min_rr_ratio: float = 2.0
    enable_partial_exits: bool = True
    partial_exit_ratios: List[float] = field(default_factory=lambda: [0.33, 0.33, 0.34])
    
    # Position sizing
    default_risk_pct: float = 1.0
    volatility_adjusted_sizing: bool = True
    
    # Guarding line (swing trading)
    enable_guarding_line: bool = True
    guarding_activation_bars: int = 10
    guarding_buffer_pct: float = 0.3
    
    # Living Take-Profit
    enable_dynamic_targets: bool = True
    dynamic_target_threshold: float = 1.5  # Add new target at 1.5R
    
    # === NEW: Entry Gate ===
    enforce_min_rr: bool = True           # Block entries below min R:R
    min_rr_for_entry: float = 2.0         # Minimum R:R required
    
    # === NEW: Breakeven Stop ===
    enable_breakeven_stop: bool = True    # Move to BE at +1R
    breakeven_trigger_r: float = 1.0      # R-multiple to trigger BE move
    breakeven_buffer_pct: float = 0.1     # Buffer above entry (0.1%)
    
    # === NEW: Volatility Regime ===
    enable_volatility_regime: bool = True
    volatility_lookback: int = 100        # Bars for baseline ATR
    low_vol_threshold: float = 0.5        # Below 50% = low vol
    high_vol_threshold: float = 1.5       # Above 150% = high vol
    extreme_vol_threshold: float = 2.5    # Above 250% = extreme
    extreme_vol_size_reduction: float = 0.5  # Reduce size by 50% in extreme
    
    # === NEW: Structure Staleness ===
    enable_staleness_penalty: bool = True
    staleness_threshold_bars: int = 50    # Bars before structure is "stale"
    staleness_max_penalty: float = 2.0    # Max points to deduct
    freshness_bonus_bars: int = 10        # Bars for "fresh" bonus
    freshness_bonus: float = 1.5          # Points to add for fresh structure
    
    # === NEW: Divergence Detection ===
    enable_divergence_detection: bool = True
    divergence_lookback: int = 20         # Bars to check for divergence
    rsi_period: int = 14                  # RSI calculation period


# =============================================================================
# GUARDING LINE (Integrated)
# =============================================================================

class GuardingLineManager:
    """Trailing structural stop for swing trades with DYNAMIC slope calculation."""
    
    def __init__(self, activation_bars: int = 10, buffer_pct: float = 0.3):
        self.activation_bars = activation_bars
        self.buffer_pct = buffer_pct
        self.min_slope_pct = 0.05   # Minimum 0.05% per bar
        self.max_slope_pct = 0.5    # Maximum 0.5% per bar
    
    def calculate_initial_line(
        self,
        entry_price: float,
        direction: str,
        price_data: List[float],
        lookback: int = 20
    ) -> Dict[str, float]:
        """
        Calculate initial guarding line parameters with DYNAMIC slope.
        
        The slope is calculated from actual swing point progression,
        not an arbitrary fixed percentage.
        """
        if len(price_data) < 5:
            # Fallback to default slope
            default_slope = entry_price * (self.min_slope_pct / 100)
            return {
                "slope": default_slope if direction == "long" else -default_slope,
                "intercept": entry_price * (0.97 if direction == "long" else 1.03),
                "activation_bar": self.activation_bars,
                "buffer_pct": self.buffer_pct,
                "slope_source": "default"
            }
        
        recent = price_data[:min(lookback, len(price_data))]
        swing_points = self._find_swing_points(recent, direction)
        
        # Calculate slope from swing points (preferred) or all data
        if len(swing_points) >= 2:
            slope = self._calculate_dynamic_slope(swing_points, direction, entry_price)
            slope_source = "swing_regression"
        else:
            # Fallback: use linear regression on all recent data
            x = np.arange(len(recent))
            y = np.array(recent)
            slope, _ = np.polyfit(x, y, 1)
            slope_source = "linear_regression"
        
        # Enforce slope direction matches trade direction
        if direction == "long":
            slope = max(0, slope)  # Only rising guard for longs
            # Ensure minimum slope (don't let guard go flat)
            min_slope = entry_price * (self.min_slope_pct / 100)
            slope = max(slope, min_slope)
        else:
            slope = min(0, slope)  # Only falling guard for shorts
            min_slope = -entry_price * (self.min_slope_pct / 100)
            slope = min(slope, min_slope)
        
        # Cap maximum slope
        max_slope = entry_price * (self.max_slope_pct / 100)
        slope = max(-max_slope, min(max_slope, slope))
        
        # Calculate intercept with buffer
        if direction == "long":
            # Start below the lowest recent swing low
            base_intercept = min(recent) if recent else entry_price * 0.97
            intercept = base_intercept * (1 - self.buffer_pct / 100)
        else:
            base_intercept = max(recent) if recent else entry_price * 1.03
            intercept = base_intercept * (1 + self.buffer_pct / 100)
        
        return {
            "slope": float(slope),
            "intercept": float(intercept),
            "activation_bar": self.activation_bars,
            "buffer_pct": self.buffer_pct,
            "slope_source": slope_source,
            "base_level": float(base_intercept)
        }
    
    def _calculate_dynamic_slope(
        self, 
        swing_points: List[Tuple[int, float]], 
        direction: str,
        entry_price: float
    ) -> float:
        """
        Calculate slope from actual swing point progression.
        
        This gives a realistic trailing angle based on how the market
        is actually forming higher lows (for longs) or lower highs (for shorts).
        """
        if len(swing_points) < 2:
            return entry_price * (self.min_slope_pct / 100)
        
        # Use linear regression on swing points
        x = np.array([p[0] for p in swing_points])
        y = np.array([p[1] for p in swing_points])
        
        # Fit line to swing points
        slope, _ = np.polyfit(x, y, 1)
        
        return float(slope)
    
    def update_slope(
        self,
        line_params: Dict[str, float],
        new_swing_points: List[Tuple[int, float]],
        direction: str,
        entry_price: float
    ) -> Dict[str, float]:
        """
        Update guarding line slope based on new swing points.
        
        Call this when new swing points form to adapt the guard angle.
        """
        if len(new_swing_points) < 2:
            return line_params
        
        new_slope = self._calculate_dynamic_slope(new_swing_points, direction, entry_price)
        
        # Only update if new slope is more favorable (steeper for longs)
        current_slope = line_params.get("slope", 0)
        
        if direction == "long" and new_slope > current_slope:
            line_params["slope"] = new_slope
            line_params["slope_source"] = "dynamic_update"
        elif direction == "short" and new_slope < current_slope:
            line_params["slope"] = new_slope
            line_params["slope_source"] = "dynamic_update"
        
        return line_params
    
    def get_current_level(self, line_params: Dict[str, float], bars_since_entry: int) -> float:
        """Get current guarding line level."""
        slope = line_params["slope"]
        intercept = line_params["intercept"]
        activation = line_params.get("activation_bar", self.activation_bars)
        
        if bars_since_entry < activation:
            # Before activation, return a level far from price (inactive)
            return intercept * 0.9 if slope >= 0 else intercept * 1.1
        
        bars_active = bars_since_entry - activation
        return intercept + (slope * bars_active)
    
    def check_break(self, current_price: float, guarding_level: float, direction: str) -> Tuple[bool, str]:
        """Check if guarding line is broken."""
        if direction == "long" and current_price < guarding_level:
            return True, f"Price {current_price:.2f} broke below guarding at {guarding_level:.2f}"
        elif direction == "short" and current_price > guarding_level:
            return True, f"Price {current_price:.2f} broke above guarding at {guarding_level:.2f}"
        return False, ""
    
    def _find_swing_points(self, prices: List[float], direction: str) -> List[Tuple[int, float]]:
        """Find swing lows (long) or swing highs (short) using fractal detection."""
        swing_points = []
        
        # Need at least 5 bars for fractal detection
        if len(prices) < 5:
            return swing_points
        
        for i in range(2, len(prices) - 2):
            if direction == "long":
                # Swing low: lower than 2 bars on each side
                if (prices[i] < prices[i-1] and prices[i] < prices[i-2] and 
                    prices[i] < prices[i+1] and prices[i] < prices[i+2]):
                    swing_points.append((i, prices[i]))
            else:
                # Swing high: higher than 2 bars on each side
                if (prices[i] > prices[i-1] and prices[i] > prices[i-2] and 
                    prices[i] > prices[i+1] and prices[i] > prices[i+2]):
                    swing_points.append((i, prices[i]))
        
        return swing_points


# =============================================================================
# MOMENTUM TRAILING TAKE-PROFIT (Living TP)
# =============================================================================

@dataclass
class MomentumState:
    """Tracks the momentum trailing TP state."""
    active: bool = False
    trailing_level: float = 0.0           # Current trailing TP level
    slope: float = 0.0                    # Current price slope (per bar)
    slope_strength: float = 0.0           # 0-1, how aggressive the move is
    bars_in_momentum: int = 0             # How long we've been trailing
    peak_price: float = 0.0               # Best price reached
    trail_buffer_pct: float = 0.0         # Current buffer % from price
    last_candle_body_high: float = 0.0
    last_candle_body_low: float = 0.0
    activation_r: float = 0.0             # R-multiple when activated


class MomentumTrailingTP:
    """
    Aggressive Momentum-Based Trailing Take-Profit.
    
    LOGIC:
    1. Activate when price moves aggressively in trade direction
    2. Calculate slope aggressiveness from recent candles
    3. Steeper slope = tighter trail (capture the momentum)
    4. Trail above/below candle bodies based on direction
    5. Exit when price breaks the trailing level (momentum exhausted)
    
    For SHORTS in a dump:
    - Trail ABOVE the candle bodies
    - As price drills down, trail follows aggressively
    - When price reverses and breaks above trail = exit with profits
    
    For LONGS in a pump:
    - Trail BELOW the candle bodies
    - As price pumps up, trail follows aggressively  
    - When price reverses and breaks below trail = exit with profits
    """
    
    def __init__(
        self,
        # Activation thresholds
        min_r_to_activate: float = 1.0,        # Minimum R before trailing starts
        min_slope_to_activate: float = 0.002,  # Minimum 0.2% per bar slope
        
        # Trail aggressiveness
        base_buffer_pct: float = 0.5,          # Base buffer from price (0.5%)
        min_buffer_pct: float = 0.15,          # Minimum buffer (aggressive trail)
        max_buffer_pct: float = 1.5,           # Maximum buffer (relaxed trail)
        
        # Slope calculation
        slope_lookback: int = 5,               # Bars to calculate slope
        
        # Candle trailing
        trail_wicks: bool = False,             # Trail wicks (True) or bodies (False)
        body_buffer_pct: float = 0.1,          # Extra buffer beyond candle body
    ):
        self.min_r_to_activate = min_r_to_activate
        self.min_slope_to_activate = min_slope_to_activate
        self.base_buffer_pct = base_buffer_pct
        self.min_buffer_pct = min_buffer_pct
        self.max_buffer_pct = max_buffer_pct
        self.slope_lookback = slope_lookback
        self.trail_wicks = trail_wicks
        self.body_buffer_pct = body_buffer_pct
    
    def calculate_slope(
        self,
        closes: List[float],
        direction: str
    ) -> Tuple[float, float]:
        """
        Calculate price slope and its strength.
        
        Returns:
            (slope_per_bar, strength 0-1)
            
        Strength indicates how aggressive the move is:
        - 1.0 = Extremely aggressive (parabolic move)
        - 0.5 = Moderate trend
        - 0.0 = No trend / choppy
        """
        if len(closes) < 3:
            return 0.0, 0.0
        
        recent = closes[-self.slope_lookback:] if len(closes) >= self.slope_lookback else closes
        
        # Calculate slope using linear regression
        x = np.arange(len(recent))
        y = np.array(recent)
        
        if len(x) < 2:
            return 0.0, 0.0
        
        slope, intercept = np.polyfit(x, y, 1)
        
        # Normalize slope to percentage per bar
        avg_price = np.mean(recent)
        slope_pct = (slope / avg_price) * 100 if avg_price > 0 else 0
        
        # Calculate R-squared (how clean is the move)
        y_pred = slope * x + intercept
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        r_squared = max(0, min(1, r_squared))
        
        # Strength = magnitude of slope * cleanness of move
        slope_magnitude = abs(slope_pct) / 1.0  # Normalize: 1% per bar = magnitude 1
        strength = min(1.0, slope_magnitude * r_squared)
        
        # Direction check - slope should match trade direction
        if direction == "long" and slope < 0:
            strength *= 0.3  # Penalize wrong direction
        elif direction == "short" and slope > 0:
            strength *= 0.3
        
        return slope_pct, strength
    
    def calculate_trail_buffer(self, slope_strength: float) -> float:
        """
        Calculate trailing buffer based on slope strength.
        
        Stronger slope = tighter buffer (more aggressive trailing)
        Weaker slope = wider buffer (give room to breathe)
        """
        # Inverse relationship: strong momentum = tight trail
        # slope_strength 0 -> max_buffer
        # slope_strength 1 -> min_buffer
        
        buffer_range = self.max_buffer_pct - self.min_buffer_pct
        buffer = self.max_buffer_pct - (slope_strength * buffer_range)
        
        return max(self.min_buffer_pct, min(self.max_buffer_pct, buffer))
    
    def calculate_trail_level(
        self,
        current_price: float,
        direction: str,
        recent_candles: List[Dict[str, float]],  # [{open, high, low, close}, ...]
        buffer_pct: float
    ) -> float:
        """
        Calculate trailing level based on candle bodies/wicks.
        
        For LONGS: Trail below candle bodies (or wicks)
        For SHORTS: Trail above candle bodies (or wicks)
        """
        if not recent_candles:
            # Fallback to simple buffer
            if direction == "long":
                return current_price * (1 - buffer_pct / 100)
            else:
                return current_price * (1 + buffer_pct / 100)
        
        # Get last few candles for trailing reference
        lookback = min(3, len(recent_candles))
        recent = recent_candles[-lookback:]
        
        if direction == "long":
            # Trail BELOW candle bodies/wicks
            if self.trail_wicks:
                # Trail below the lowest wick
                reference_price = min(c['low'] for c in recent)
            else:
                # Trail below the lowest candle body
                reference_price = min(min(c['open'], c['close']) for c in recent)
            
            # Apply additional buffer
            trail_level = reference_price * (1 - self.body_buffer_pct / 100)
            
            # But never trail higher than current price minus minimum buffer
            max_trail = current_price * (1 - self.min_buffer_pct / 100)
            trail_level = min(trail_level, max_trail)
            
        else:  # SHORT
            # Trail ABOVE candle bodies/wicks
            if self.trail_wicks:
                # Trail above the highest wick
                reference_price = max(c['high'] for c in recent)
            else:
                # Trail above the highest candle body
                reference_price = max(max(c['open'], c['close']) for c in recent)
            
            # Apply additional buffer
            trail_level = reference_price * (1 + self.body_buffer_pct / 100)
            
            # But never trail lower than current price plus minimum buffer
            min_trail = current_price * (1 + self.min_buffer_pct / 100)
            trail_level = max(trail_level, min_trail)
        
        return trail_level
    
    def update(
        self,
        state: MomentumState,
        current_price: float,
        current_r: float,
        direction: str,
        recent_closes: List[float],
        recent_candles: List[Dict[str, float]],
    ) -> Tuple[MomentumState, bool, Optional[str]]:
        """
        Update momentum trailing state.
        
        Args:
            state: Current momentum state
            current_price: Current price
            current_r: Current R-multiple profit
            direction: 'long' or 'short'
            recent_closes: List of recent close prices
            recent_candles: List of recent candle dicts
            
        Returns:
            (updated_state, should_exit, exit_reason)
        """
        # Check activation
        if not state.active:
            # Should we activate?
            if current_r >= self.min_r_to_activate:
                slope_pct, strength = self.calculate_slope(recent_closes, direction)
                
                # Check if slope is strong enough
                if abs(slope_pct) >= self.min_slope_to_activate and strength >= 0.3:
                    # ACTIVATE momentum trailing!
                    state.active = True
                    state.activation_r = current_r
                    state.slope = slope_pct
                    state.slope_strength = strength
                    state.peak_price = current_price
                    state.bars_in_momentum = 0
                    
                    # Calculate initial trail
                    state.trail_buffer_pct = self.calculate_trail_buffer(strength)
                    state.trailing_level = self.calculate_trail_level(
                        current_price, direction, recent_candles, state.trail_buffer_pct
                    )
                    
                    return state, False, None
            
            return state, False, None
        
        # Already active - UPDATE the trail
        state.bars_in_momentum += 1
        
        # Recalculate slope
        slope_pct, strength = self.calculate_slope(recent_closes, direction)
        state.slope = slope_pct
        state.slope_strength = strength
        
        # Update buffer based on current slope
        state.trail_buffer_pct = self.calculate_trail_buffer(strength)
        
        # Update peak price
        if direction == "long":
            state.peak_price = max(state.peak_price, current_price)
        else:
            state.peak_price = min(state.peak_price, current_price)
        
        # Calculate new trail level
        new_trail = self.calculate_trail_level(
            current_price, direction, recent_candles, state.trail_buffer_pct
        )
        
        # Only move trail in favorable direction (ratchet effect)
        if direction == "long":
            # Trail can only move UP for longs
            if new_trail > state.trailing_level:
                state.trailing_level = new_trail
        else:
            # Trail can only move DOWN for shorts
            if new_trail < state.trailing_level:
                state.trailing_level = new_trail
        
        # Store candle body info
        if recent_candles:
            last = recent_candles[-1]
            state.last_candle_body_high = max(last['open'], last['close'])
            state.last_candle_body_low = min(last['open'], last['close'])
        
        # CHECK FOR EXIT - Has momentum broken?
        if direction == "long" and current_price < state.trailing_level:
            profit_captured = current_r - state.activation_r if state.activation_r else current_r
            reason = (
                f"Momentum trail broken at ${state.trailing_level:,.2f} "
                f"(captured +{profit_captured:.1f}R of momentum move)"
            )
            return state, True, reason
        
        elif direction == "short" and current_price > state.trailing_level:
            profit_captured = current_r - state.activation_r if state.activation_r else current_r
            reason = (
                f"Momentum trail broken at ${state.trailing_level:,.2f} "
                f"(captured +{profit_captured:.1f}R of momentum move)"
            )
            return state, True, reason
        
        return state, False, None
    
    def get_state_summary(self, state: MomentumState, direction: str) -> Dict:
        """Get summary of current momentum state."""
        return {
            'active': state.active,
            'trailing_level': state.trailing_level,
            'slope_per_bar_pct': state.slope,
            'slope_strength': state.slope_strength,
            'trail_buffer_pct': state.trail_buffer_pct,
            'bars_in_momentum': state.bars_in_momentum,
            'peak_price': state.peak_price,
            'activation_r': state.activation_r,
            'direction': direction,
        }


# =============================================================================
# MAIN RISK ENGINE
# =============================================================================

class RiskEngine:
    """
    BASTION Risk Engine - Strategy-Agnostic Risk Management.
    
    YOU provide:
    - Entry price, direction, account balance, risk tolerance
    
    BASTION provides:
    - Optimal stops (structural + ATR-based)
    - Optimal targets (structural + volume-informed)
    - Position sizing (volatility-adjusted)
    - Market context (structure quality, volume profile, order flow, MTF)
    - Dynamic position updates (guarding line, living TP)
    
    Usage:
        engine = RiskEngine()
        
        levels = await engine.calculate_risk_levels(
            symbol='BTCUSDT',
            entry_price=94500,
            direction='long',
            timeframe='4h',
            account_balance=100000,
            ohlcv_data={'4h': df_4h, '1d': df_daily}
        )
        
        # Later, update position
        update = engine.update_position(levels, position_update)
    """
    
    def __init__(self, config: Optional[RiskEngineConfig] = None):
        self.config = config or RiskEngineConfig()
        
        # Initialize detection systems
        self.structure_detector = StructureDetector() if self.config.enable_structure_detection else None
        self.vpvr_analyzer = VPVRAnalyzer() if self.config.enable_vpvr_analysis else None
        self.orderflow_detector = OrderFlowDetector() if self.config.enable_orderflow_detection else None
        self.mtf_analyzer = MTFStructureAnalyzer() if self.config.enable_mtf_analysis else None
        
        # Guarding line manager
        self.guarding_manager = GuardingLineManager(
            activation_bars=self.config.guarding_activation_bars,
            buffer_pct=self.config.guarding_buffer_pct
        )
        
        # Momentum Trailing TP (Living Take-Profit)
        self.momentum_tp = MomentumTrailingTP(
            min_r_to_activate=1.0,           # Activate at +1R
            min_slope_to_activate=0.002,     # 0.2% per bar minimum slope
            base_buffer_pct=0.5,
            min_buffer_pct=0.15,             # Very tight trail on strong momentum
            max_buffer_pct=1.5,
            slope_lookback=5,
            trail_wicks=False,               # Trail candle bodies, not wicks
            body_buffer_pct=0.1,
        )
        
        # Per-position momentum states (keyed by symbol or session)
        self._momentum_states: Dict[str, MomentumState] = {}
    
    async def calculate_risk_levels(
        self,
        symbol: str,
        entry_price: float,
        direction: str,
        timeframe: str,
        account_balance: float,
        ohlcv_data: Dict[str, pd.DataFrame],
        risk_per_trade_pct: float = 1.0,
    ) -> RiskLevels:
        """
        Calculate risk levels for YOUR trade setup.
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            entry_price: YOUR entry price
            direction: YOUR direction ('long' or 'short')
            timeframe: Primary timeframe ('4h', '1d', etc.)
            account_balance: Account size in USD
            ohlcv_data: Dict of timeframe -> OHLCV DataFrame
            risk_per_trade_pct: Risk per trade (default 1%)
            
        Returns:
            RiskLevels with stops, targets, and market context
        """
        levels = RiskLevels(
            entry_price=entry_price,
            direction=direction,
            timeframe=timeframe,
            symbol=symbol,
        )
        
        primary_df = ohlcv_data.get(timeframe)
        if primary_df is None or len(primary_df) < 50:
            logger.error(f"Insufficient data for timeframe {timeframe}")
            return levels
        
        # Current price
        levels.current_price = float(primary_df['close'].iloc[-1])
        
        # Calculate ATR
        atr = self._calculate_atr(primary_df)
        atr_pct = (atr / entry_price) * 100
        levels.atr_current = atr
        levels.atr_pct = atr_pct
        
        # === NEW: Volatility Regime Detection ===
        if self.config.enable_volatility_regime:
            levels.volatility_regime = self._detect_volatility_regime(primary_df, atr).value
        
        # Step 1: Structure Analysis
        if self.structure_detector:
            levels.structure_analysis = self.structure_detector.analyze(primary_df)
            levels.structure_quality = levels.structure_analysis.structure_score
            
            # === NEW: Apply staleness penalty ===
            if self.config.enable_staleness_penalty:
                levels.structure_quality = self._apply_staleness_penalty(
                    levels.structure_quality, levels.structure_analysis
                )
        
        # Step 2: VPVR Analysis
        if self.vpvr_analyzer:
            levels.vpvr_analysis = self.vpvr_analyzer.analyze(primary_df, direction=direction)
            levels.volume_profile_score = levels.vpvr_analysis.volume_score
        
        # Step 3: Order Flow Analysis
        if self.orderflow_detector:
            levels.orderflow_analysis = await self.orderflow_detector.analyze(symbol=symbol, ohlcv=primary_df)
            levels.orderflow_bias = self._determine_orderflow_bias(levels.orderflow_analysis)
        
        # Step 4: MTF Analysis
        if self.mtf_analyzer and len(ohlcv_data) > 1:
            levels.mtf_analysis = self.mtf_analyzer.analyze(ohlcv_data, proposed_direction=direction)
            levels.mtf_alignment = levels.mtf_analysis.alignment_score
        
        # Step 5: Calculate Stops
        levels.stops = self._calculate_stops(levels, primary_df, atr)
        
        # Step 6: Calculate Targets
        levels.targets = self._calculate_targets(levels, primary_df, atr)
        
        # Step 7: Guarding Line (for swing timeframes)
        if self.config.enable_guarding_line and self._is_swing_timeframe(timeframe):
            price_data = primary_df['low'].tolist() if direction == "long" else primary_df['high'].tolist()
            levels.guarding_line = self.guarding_manager.calculate_initial_line(
                entry_price, direction, price_data
            )
        
        # Step 8: Position Sizing (with volatility adjustment)
        primary_stop_price = levels.stops[0]['price'] if levels.stops else entry_price - (atr * 2)
        risk_distance = abs(entry_price - primary_stop_price)
        
        # Apply volatility regime adjustment
        adjusted_risk_pct = risk_per_trade_pct
        if levels.volatility_regime == VolatilityRegime.EXTREME.value:
            adjusted_risk_pct *= self.config.extreme_vol_size_reduction
            logger.warning(f"EXTREME volatility: Reducing position size by {(1-self.config.extreme_vol_size_reduction)*100:.0f}%")
        
        levels.position_size, levels.position_size_pct, levels.risk_amount = self._calculate_position_size(
            account_balance, adjusted_risk_pct, entry_price, risk_distance, atr_pct
        )
        
        # Step 9: Risk Metrics
        if levels.stops and levels.targets:
            levels.risk_reward_ratio = self._calculate_rr_ratio(
                entry_price, levels.stops[0]['price'], levels.targets[0]['price']
            )
            levels.max_risk_reward_ratio = self._calculate_rr_ratio(
                entry_price, levels.stops[0]['price'], levels.targets[-1]['price']
            )
        
        # === NEW: Calculate breakeven and 1R prices ===
        if levels.stops:
            levels.breakeven_price = self._calculate_breakeven_price(entry_price, direction)
            levels.one_r_price = self._calculate_one_r_price(
                entry_price, levels.stops[0]['price'], direction
            )
        
        # === NEW: Entry Gate - Block poor R:R trades ===
        if self.config.enforce_min_rr:
            if levels.risk_reward_ratio < self.config.min_rr_for_entry:
                levels.entry_blocked = True
                levels.block_reason = (
                    f"R:R of {levels.risk_reward_ratio:.2f} below minimum "
                    f"{self.config.min_rr_for_entry:.1f}. Find better entry or tighter stop."
                )
                logger.warning(f"Entry BLOCKED: {levels.block_reason}")
        
        return levels
    
    def _detect_volatility_regime(self, ohlcv: pd.DataFrame, current_atr: float) -> VolatilityRegime:
        """
        Detect current volatility regime by comparing current ATR to historical.
        
        Returns regime for position sizing adjustment.
        """
        if len(ohlcv) < self.config.volatility_lookback:
            return VolatilityRegime.NORMAL
        
        # Calculate baseline ATR (longer period)
        baseline_atr = self._calculate_atr(ohlcv, period=self.config.volatility_lookback)
        
        if baseline_atr == 0:
            return VolatilityRegime.NORMAL
        
        ratio = current_atr / baseline_atr
        
        if ratio < self.config.low_vol_threshold:
            return VolatilityRegime.LOW
        elif ratio > self.config.extreme_vol_threshold:
            return VolatilityRegime.EXTREME
        elif ratio > self.config.high_vol_threshold:
            return VolatilityRegime.HIGH
        else:
            return VolatilityRegime.NORMAL
    
    def _apply_staleness_penalty(
        self, 
        base_score: float, 
        structure: StructureAnalysis
    ) -> float:
        """
        Apply penalty for stale structure and bonus for fresh structure.
        """
        adjusted_score = base_score
        
        # Check trendlines for staleness
        if structure.trendlines:
            avg_staleness = np.mean([t.bars_since_last_touch for t in structure.trendlines])
            
            if avg_staleness > self.config.staleness_threshold_bars:
                # Penalize stale structure
                penalty = min(
                    self.config.staleness_max_penalty,
                    (avg_staleness - self.config.staleness_threshold_bars) / 50
                )
                adjusted_score -= penalty
                logger.debug(f"Structure staleness penalty: -{penalty:.2f}")
            
            elif avg_staleness < self.config.freshness_bonus_bars:
                # Bonus for fresh structure
                adjusted_score += self.config.freshness_bonus
                logger.debug(f"Fresh structure bonus: +{self.config.freshness_bonus}")
        
        return max(0.0, min(10.0, adjusted_score))
    
    def _calculate_breakeven_price(self, entry_price: float, direction: str) -> float:
        """Calculate breakeven price with small buffer."""
        buffer = entry_price * (self.config.breakeven_buffer_pct / 100)
        
        if direction == "long":
            return entry_price + buffer  # Slightly above entry
        else:
            return entry_price - buffer  # Slightly below entry
    
    def _calculate_one_r_price(self, entry_price: float, stop_price: float, direction: str) -> float:
        """Calculate price at +1R profit."""
        risk_distance = abs(entry_price - stop_price)
        
        if direction == "long":
            return entry_price + risk_distance
        else:
            return entry_price - risk_distance
    
    def _detect_divergence(self, ohlcv: pd.DataFrame, direction: str) -> Tuple[bool, Optional[str]]:
        """
        Detect price/RSI divergence for early exit signals.
        
        For longs: bearish divergence = price making highs, RSI making lows
        For shorts: bullish divergence = price making lows, RSI making highs
        """
        if not self.config.enable_divergence_detection:
            return False, None
        
        if len(ohlcv) < self.config.divergence_lookback:
            return False, None
        
        close = ohlcv['close'].values[-self.config.divergence_lookback:]
        
        # Calculate RSI
        delta = np.diff(close)
        gains = np.where(delta > 0, delta, 0)
        losses = np.where(delta < 0, -delta, 0)
        
        avg_gain = np.mean(gains[-self.config.rsi_period:])
        avg_loss = np.mean(losses[-self.config.rsi_period:])
        
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        # Compare first half vs second half of lookback period
        mid = len(close) // 2
        first_half_high = np.max(close[:mid])
        second_half_high = np.max(close[mid:])
        first_half_low = np.min(close[:mid])
        second_half_low = np.min(close[mid:])
        
        if direction == "long":
            # Bearish divergence: price making higher highs, but RSI weakening
            price_making_highs = second_half_high > first_half_high
            rsi_weakening = rsi < 50
            
            if price_making_highs and rsi_weakening:
                return True, "bearish"
        
        else:  # short
            # Bullish divergence: price making lower lows, but RSI strengthening
            price_making_lows = second_half_low < first_half_low
            rsi_strengthening = rsi > 50
            
            if price_making_lows and rsi_strengthening:
                return True, "bullish"
        
        return False, None
    
    def update_position(
        self, 
        levels: RiskLevels, 
        update: PositionUpdate,
        ohlcv: Optional[pd.DataFrame] = None,
        session_id: Optional[str] = None
    ) -> RiskUpdate:
        """
        Update risk levels based on current price action.
        
        Call this on each bar to get dynamic stop/target adjustments.
        
        FEATURES:
        - Breakeven stop at +1R
        - Momentum Trailing TP (aggressive slope-based trailing)
        - Divergence detection
        """
        result = RiskUpdate(
            updated_stops=list(levels.stops),
            updated_targets=list(levels.targets),
        )
        
        direction = levels.direction
        entry = levels.entry_price
        current = update.current_price
        
        # Use session_id or symbol as key for momentum state
        momentum_key = session_id or levels.symbol
        
        # === Calculate current R-multiple ===
        if levels.stops:
            risk_distance = abs(entry - levels.stops[0]['price'])
            if risk_distance > 0:
                if direction == "long":
                    profit_distance = current - entry
                else:
                    profit_distance = entry - current
                result.current_r_multiple = profit_distance / risk_distance
        
        # === Breakeven Stop at +1R ===
        if self.config.enable_breakeven_stop and result.current_r_multiple >= self.config.breakeven_trigger_r:
            result.breakeven_hit = True
            
            # Move stop to breakeven if not already there
            current_stop = levels.stops[0]['price'] if levels.stops else None
            breakeven_price = levels.breakeven_price or self._calculate_breakeven_price(entry, direction)
            
            if current_stop and self._is_better_stop(breakeven_price, current_stop, direction):
                result.stop_moved = True
                result.moved_to_breakeven = True
                result.new_stop_price = breakeven_price
                result.stop_move_reason = f"Moved to breakeven at +{result.current_r_multiple:.1f}R"
                result.alerts.append(f"📈 Stop moved to BREAKEVEN at ${breakeven_price:,.2f} (+{result.current_r_multiple:.1f}R)")
                
                # Update the levels object
                if levels.stops:
                    levels.stops[0]['price'] = breakeven_price
                    levels.stops[0]['reason'] = "Breakeven stop (profit protection)"
                    levels.stops[0]['type'] = 'breakeven'
        
        # === MOMENTUM TRAILING TP (Living Take-Profit) ===
        if self.config.enable_dynamic_targets and ohlcv is not None and len(ohlcv) >= 5:
            # Get or create momentum state
            if momentum_key not in self._momentum_states:
                self._momentum_states[momentum_key] = MomentumState()
            
            momentum_state = self._momentum_states[momentum_key]
            
            # Prepare candle data for momentum TP
            recent_closes = ohlcv['close'].tolist()[-10:]
            recent_candles = [
                {
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                }
                for _, row in ohlcv.tail(5).iterrows()
            ]
            
            # Update momentum trailing
            updated_state, should_exit, exit_reason = self.momentum_tp.update(
                state=momentum_state,
                current_price=current,
                current_r=result.current_r_multiple,
                direction=direction,
                recent_closes=recent_closes,
                recent_candles=recent_candles,
            )
            
            self._momentum_states[momentum_key] = updated_state
            
            # Report momentum state
            if updated_state.active:
                # Update result with momentum state
                result.momentum_trailing_active = True
                result.momentum_trailing_level = updated_state.trailing_level
                result.momentum_slope_strength = updated_state.slope_strength
                result.momentum_buffer_pct = updated_state.trail_buffer_pct
                
                if not momentum_state.active:
                    # Just activated
                    result.alerts.append(
                        f"🚀 MOMENTUM TRAILING ACTIVATED at +{result.current_r_multiple:.1f}R "
                        f"(slope: {updated_state.slope:.2f}%/bar, strength: {updated_state.slope_strength:.0%})"
                    )
                    result.alerts.append(
                        f"📍 Trailing at ${updated_state.trailing_level:,.2f} "
                        f"(buffer: {updated_state.trail_buffer_pct:.1f}%)"
                    )
                
                # Add new dynamic target at trailing level
                result.new_target_added = True
                result.new_target_price = updated_state.trailing_level
            
            # Check for momentum exit
            if should_exit and exit_reason:
                result.exit_signal = True
                result.exit_reason = exit_reason
                result.exit_percentage = 100.0  # Full exit on momentum break
                result.alerts.append(f"🎯 MOMENTUM EXIT: {exit_reason}")
        
        # === Divergence Detection ===
        if ohlcv is not None and self.config.enable_divergence_detection:
            div_detected, div_type = self._detect_divergence(ohlcv, direction)
            if div_detected:
                result.divergence_detected = True
                result.divergence_type = div_type
                
                # Divergence against position = partial exit signal
                if (direction == "long" and div_type == "bearish") or \
                   (direction == "short" and div_type == "bullish"):
                    result.alerts.append(f"⚠️ {div_type.upper()} divergence detected - consider partial exit")
                    
                    # Only signal exit if we're in profit and momentum trailing not active
                    momentum_state = self._momentum_states.get(momentum_key)
                    if result.current_r_multiple > 0.5 and (not momentum_state or not momentum_state.active):
                        result.exit_signal = True
                        result.exit_reason = f"{div_type} divergence - momentum weakening"
                        result.exit_percentage = 33.0  # Partial exit
        
        # Check fixed targets hit (only if momentum trailing not active)
        momentum_state = self._momentum_states.get(momentum_key)
        if not (momentum_state and momentum_state.active):
            for target in levels.targets:
                if direction == "long" and current >= target['price']:
                    result.exit_signal = True
                    result.exit_reason = f"Target hit: {target['reason']}"
                    result.exit_percentage = target.get('exit_percentage', 100)
                    result.alerts.append(f"🎯 TARGET HIT at ${target['price']:,.2f}")
                    break
                elif direction == "short" and current <= target['price']:
                    result.exit_signal = True
                    result.exit_reason = f"Target hit: {target['reason']}"
                    result.exit_percentage = target.get('exit_percentage', 100)
                    result.alerts.append(f"🎯 TARGET HIT at ${target['price']:,.2f}")
                    break
        
        # Check guarding line
        if levels.guarding_line and update.bars_since_entry >= self.config.guarding_activation_bars:
            result.guarding_active = True
            result.guarding_level = self.guarding_manager.get_current_level(
                levels.guarding_line, update.bars_since_entry
            )
            
            is_broken, reason = self.guarding_manager.check_break(current, result.guarding_level, direction)
            if is_broken:
                result.guarding_broken = True
                result.exit_signal = True
                result.exit_reason = reason
                result.exit_percentage = 100.0
                result.alerts.append(f"🛡️ GUARDING LINE BROKEN - {reason}")
        
        # Trail stop if in profit (after breakeven)
        if update.unrealized_pnl_pct > 0 and not result.moved_to_breakeven:
            new_stop = self._trail_stop(direction, entry, current, update, levels.stops)
            if new_stop:
                result.stop_moved = True
                result.new_stop_price = new_stop
                result.stop_move_reason = "Trailing stop adjustment"
        
        # Check structure health
        if update.recent_lows and update.recent_highs:
            result.structure_health = self._check_structure_health(
                direction, current, update.recent_lows, update.recent_highs
            )
            if result.structure_health == StructureHealth.BROKEN and not result.exit_signal:
                result.exit_signal = True
                result.exit_reason = "Supporting structure broken"
                result.exit_percentage = 100.0
                result.alerts.append("🔴 STRUCTURE BROKEN - Exit position")
        
        return result
    
    def get_momentum_state(self, session_id: str) -> Optional[Dict]:
        """Get current momentum trailing state for a session."""
        state = self._momentum_states.get(session_id)
        if state:
            return {
                'active': state.active,
                'trailing_level': state.trailing_level,
                'slope_pct_per_bar': state.slope,
                'slope_strength': state.slope_strength,
                'trail_buffer_pct': state.trail_buffer_pct,
                'bars_in_momentum': state.bars_in_momentum,
                'peak_price': state.peak_price,
                'activation_r': state.activation_r,
            }
        return None
    
    def reset_momentum_state(self, session_id: str):
        """Reset momentum state for a session (e.g., after exit)."""
        if session_id in self._momentum_states:
            del self._momentum_states[session_id]
    
    def _is_better_stop(self, new_stop: float, current_stop: float, direction: str) -> bool:
        """Check if new stop is tighter (better) than current stop."""
        if direction == "long":
            return new_stop > current_stop  # Higher stop is better for longs
        else:
            return new_stop < current_stop  # Lower stop is better for shorts
    
    def _check_dynamic_target(
        self, 
        levels: RiskLevels, 
        current_price: float,
        current_r: float
    ) -> Optional[Dict[str, Any]]:
        """
        LEGACY: Simple R-based target extension.
        See MomentumTrailingTP for the new aggressive trailing system.
        """
        # This is now handled by MomentumTrailingTP
        return None
    
    def _determine_orderflow_bias(self, orderflow: OrderFlowAnalysis) -> str:
        """Determine order flow bias."""
        from .orderflow_detector import FlowDirection
        
        if orderflow.flow_direction in [FlowDirection.STRONG_BULLISH, FlowDirection.BULLISH]:
            return "bullish"
        elif orderflow.flow_direction in [FlowDirection.STRONG_BEARISH, FlowDirection.BEARISH]:
            return "bearish"
        return "neutral"
    
    def _calculate_stops(self, levels: RiskLevels, ohlcv: pd.DataFrame, atr: float) -> List[Dict[str, Any]]:
        """Calculate stops using structural levels."""
        stops = []
        entry = levels.entry_price
        direction = levels.direction
        
        if direction == "long":
            # Use structure for support
            if levels.structure_analysis and levels.structure_analysis.best_support:
                support_price = levels.structure_analysis.best_support.price
                if support_price < entry:
                    stop_price = support_price - (atr * 0.2)
                    distance_pct = ((entry - stop_price) / entry) * 100
                    
                    if distance_pct <= self.config.max_stop_pct:
                        stops.append({
                            'price': stop_price,
                            'type': 'structural',
                            'reason': f"Below structural support at {support_price:.2f}",
                            'confidence': levels.structure_analysis.best_support.confluence_score / 10,
                            'distance_pct': distance_pct,
                        })
            
            # Fallback: ATR-based
            if not stops:
                stop_price = entry - (atr * self.config.atr_stop_multiplier)
                distance_pct = ((entry - stop_price) / entry) * 100
                stops.append({
                    'price': stop_price,
                    'type': 'atr',
                    'reason': f"{self.config.atr_stop_multiplier}x ATR stop",
                    'confidence': 0.6,
                    'distance_pct': distance_pct,
                })
            
            # Multi-tier stops
            if self.config.enable_multi_tier_stops:
                stops.append({
                    'price': entry - (atr * self.config.atr_stop_multiplier * 1.5),
                    'type': 'secondary',
                    'reason': "Secondary stop (wider protection)",
                    'confidence': 0.5,
                    'distance_pct': (atr * self.config.atr_stop_multiplier * 1.5 / entry) * 100,
                })
                stops.append({
                    'price': entry * (1 - self.config.max_stop_pct / 100),
                    'type': 'safety_net',
                    'reason': f"Maximum {self.config.max_stop_pct}% loss protection",
                    'confidence': 1.0,
                    'distance_pct': self.config.max_stop_pct,
                })
        
        else:  # short
            if levels.structure_analysis and levels.structure_analysis.best_resistance:
                resistance_price = levels.structure_analysis.best_resistance.price
                if resistance_price > entry:
                    stop_price = resistance_price + (atr * 0.2)
                    distance_pct = ((stop_price - entry) / entry) * 100
                    
                    if distance_pct <= self.config.max_stop_pct:
                        stops.append({
                            'price': stop_price,
                            'type': 'structural',
                            'reason': f"Above structural resistance at {resistance_price:.2f}",
                            'confidence': levels.structure_analysis.best_resistance.confluence_score / 10,
                            'distance_pct': distance_pct,
                        })
            
            if not stops:
                stop_price = entry + (atr * self.config.atr_stop_multiplier)
                distance_pct = ((stop_price - entry) / entry) * 100
                stops.append({
                    'price': stop_price,
                    'type': 'atr',
                    'reason': f"{self.config.atr_stop_multiplier}x ATR stop",
                    'confidence': 0.6,
                    'distance_pct': distance_pct,
                })
            
            if self.config.enable_multi_tier_stops:
                stops.append({
                    'price': entry + (atr * self.config.atr_stop_multiplier * 1.5),
                    'type': 'secondary',
                    'reason': "Secondary stop (wider protection)",
                    'confidence': 0.5,
                    'distance_pct': (atr * self.config.atr_stop_multiplier * 1.5 / entry) * 100,
                })
                stops.append({
                    'price': entry * (1 + self.config.max_stop_pct / 100),
                    'type': 'safety_net',
                    'reason': f"Maximum {self.config.max_stop_pct}% loss protection",
                    'confidence': 1.0,
                    'distance_pct': self.config.max_stop_pct,
                })
        
        return stops
    
    def _calculate_targets(self, levels: RiskLevels, ohlcv: pd.DataFrame, atr: float) -> List[Dict[str, Any]]:
        """Calculate targets using structural levels + VPVR."""
        targets = []
        entry = levels.entry_price
        direction = levels.direction
        exit_ratios = self.config.partial_exit_ratios
        
        # VPVR targets (HVN mountains)
        vpvr_targets = []
        if levels.vpvr_analysis and self.vpvr_analyzer:
            vpvr_targets = self.vpvr_analyzer.get_targets(levels.vpvr_analysis, direction, entry)
        
        # Structural targets
        structural_targets = []
        if levels.structure_analysis:
            if direction == "long" and levels.structure_analysis.best_resistance:
                resist_price = levels.structure_analysis.best_resistance.price
                if resist_price > entry:
                    structural_targets.append((resist_price, "Structural resistance", "structural"))
            elif direction == "short" and levels.structure_analysis.best_support:
                support_price = levels.structure_analysis.best_support.price
                if support_price < entry:
                    structural_targets.append((support_price, "Structural support", "structural"))
        
        # Combine and sort
        all_targets = [(p, r, "vpvr") for p, r in vpvr_targets] + structural_targets
        all_targets.sort(key=lambda t: abs(t[0] - entry))
        
        # Create target levels
        for i, (target_price, reason, ttype) in enumerate(all_targets[:3]):
            exit_pct = exit_ratios[i] if i < len(exit_ratios) else exit_ratios[-1]
            distance_pct = abs((target_price - entry) / entry) * 100
            
            targets.append({
                'price': target_price,
                'type': ttype,
                'reason': reason,
                'exit_percentage': exit_pct * 100,
                'distance_pct': distance_pct,
                'confidence': 0.75,
            })
        
        # Fallback: R multiples
        if not targets:
            stop_distance = atr * self.config.atr_stop_multiplier
            for i, multiple in enumerate([2.0, 3.0, 5.0]):
                target_price = entry + (stop_distance * multiple) if direction == "long" else entry - (stop_distance * multiple)
                exit_pct = exit_ratios[i] if i < len(exit_ratios) else exit_ratios[-1]
                
                targets.append({
                    'price': target_price,
                    'type': 'extension',
                    'reason': f"{multiple}R target",
                    'exit_percentage': exit_pct * 100,
                    'distance_pct': abs((target_price - entry) / entry) * 100,
                    'confidence': 0.5,
                })
        
        return targets
    
    def _calculate_position_size(
        self, account_balance: float, risk_pct: float, entry_price: float,
        risk_distance: float, atr_pct: float
    ) -> Tuple[float, float, float]:
        """Calculate position size with volatility adjustment."""
        if self.config.volatility_adjusted_sizing:
            vol_factor = 2.0 / max(atr_pct, 0.5)
            vol_factor = max(0.5, min(2.0, vol_factor))
            risk_pct *= vol_factor
        
        risk_amount = account_balance * (risk_pct / 100)
        position_size = risk_amount / risk_distance if risk_distance > 0 else 0
        position_value = position_size * entry_price
        position_pct = (position_value / account_balance) * 100
        
        return position_size, position_pct, risk_amount
    
    def _calculate_rr_ratio(self, entry: float, stop: float, target: float) -> float:
        """Calculate risk:reward ratio."""
        risk = abs(entry - stop)
        reward = abs(target - entry)
        return reward / risk if risk > 0 else 0.0
    
    def _calculate_atr(self, ohlcv: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range."""
        high = ohlcv['high'].values
        low = ohlcv['low'].values
        close = ohlcv['close'].values
        
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1]))
        )
        
        return float(np.mean(tr[-period:]) if len(tr) >= period else np.mean(tr))
    
    def _is_swing_timeframe(self, timeframe: str) -> bool:
        """Check if timeframe is suitable for swing trading."""
        swing_timeframes = {"4h", "1d", "1w", "4H", "1D", "1W", "daily", "weekly"}
        return timeframe.lower() in {tf.lower() for tf in swing_timeframes}
    
    def _trail_stop(
        self, direction: str, entry: float, current: float,
        update: PositionUpdate, stops: List[Dict]
    ) -> Optional[float]:
        """Calculate trailed stop price."""
        if not stops:
            return None
        
        primary = stops[0]
        primary_distance = primary.get('distance_pct', 2.0)
        
        if direction == "long":
            profit_pct = (current - entry) / entry * 100
            if profit_pct >= primary_distance:
                new_stop = entry * 1.001
                if new_stop > primary['price']:
                    return new_stop
        else:
            profit_pct = (entry - current) / entry * 100
            if profit_pct >= primary_distance:
                new_stop = entry * 0.999
                if new_stop < primary['price']:
                    return new_stop
        
        return None
    
    def _check_structure_health(
        self, direction: str, current: float,
        recent_lows: List[float], recent_highs: List[float]
    ) -> StructureHealth:
        """Check if supporting structure is still intact."""
        if len(recent_lows) < 3 or len(recent_highs) < 3:
            return StructureHealth.STRONG
        
        if direction == "long":
            # Lower lows = weakening
            if recent_lows[0] < recent_lows[1] < recent_lows[2]:
                return StructureHealth.WEAKENING
            # Significant drop
            if (max(recent_highs[-10:]) - current) / current > 0.03:
                return StructureHealth.BROKEN
        else:
            # Higher highs = weakening
            if recent_highs[0] > recent_highs[1] > recent_highs[2]:
                return StructureHealth.WEAKENING
            # Significant rise
            if (current - min(recent_lows[-10:])) / current > 0.03:
                return StructureHealth.BROKEN
        
        return StructureHealth.STRONG
    
    async def close(self):
        """Close async resources."""
        if self.orderflow_detector:
            await self.orderflow_detector.close()

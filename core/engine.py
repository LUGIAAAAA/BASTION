"""
RiskShield Core Engine
======================

The main orchestrator that combines all risk management components
into a single, easy-to-use interface.

Usage:
    engine = RiskEngine(config)
    levels = engine.calculate_risk_levels(setup, market_data)
    update = engine.update_position(position_update)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
import numpy as np
from datetime import datetime

from .models import (
    RiskLevels, TradeSetup, MarketContext, PositionUpdate, RiskUpdate,
    StopLevel, TargetLevel, StopType, TargetType
)
from .living_tp import LivingTakeProfit
from .adaptive_budget import AdaptiveRiskBudget
from .guarding_line import GuardingLine


@dataclass
class RiskEngineConfig:
    """Configuration for the RiskEngine."""
    
    # Stop-loss settings
    use_structural_stops: bool = True       # Use S/R for stops vs fixed %
    atr_stop_multiplier: float = 2.0        # ATR multiplier for stops
    max_stop_pct: float = 5.0               # Maximum stop distance
    enable_multi_tier_stops: bool = True    # Primary/Secondary/Safety-net
    
    # Take-profit settings
    use_structural_targets: bool = True     # Use S/R for targets
    min_rr_ratio: float = 2.0               # Minimum risk:reward
    enable_partial_exits: bool = True       # Scale out at targets
    partial_exit_ratios: List[float] = field(default_factory=lambda: [0.33, 0.33, 0.34])
    
    # Guarding line (swing trading)
    enable_guarding_line: bool = True
    guarding_activation_bars: int = 10      # Bars before guarding activates
    guarding_buffer_pct: float = 0.3        # Buffer below guarding line
    
    # Adaptive risk budget
    enable_adaptive_budget: bool = True
    max_shots: int = 3                      # Maximum re-entries
    total_risk_cap_pct: float = 2.0         # Max total risk for all shots
    
    # Position sizing
    default_risk_pct: float = 1.0           # Default risk per trade
    volatility_adjusted_sizing: bool = True  # Adjust size based on volatility


class RiskEngine:
    """
    Main RiskShield engine - calculates optimal stop-losses, take-profits,
    and position sizes for any trade setup.
    """
    
    def __init__(self, config: Optional[RiskEngineConfig] = None):
        self.config = config or RiskEngineConfig()
        
        # Initialize sub-components
        self.living_tp = LivingTakeProfit()
        self.adaptive_budget = AdaptiveRiskBudget(
            max_shots=self.config.max_shots,
            total_risk_cap=self.config.total_risk_cap_pct
        )
        self.guarding_line = GuardingLine(
            activation_bars=self.config.guarding_activation_bars,
            buffer_pct=self.config.guarding_buffer_pct
        )
        
        # Active position tracking
        self._active_positions: Dict[str, Dict[str, Any]] = {}
    
    def calculate_risk_levels(
        self,
        setup: TradeSetup,
        market: MarketContext
    ) -> RiskLevels:
        """
        Calculate complete risk levels for a trade setup.
        
        This is the main entry point - give it your trade idea and market data,
        get back everything you need to manage the trade.
        """
        # Calculate ATR for volatility context
        atr = market.atr
        atr_pct = (atr / setup.entry_price) * 100 if setup.entry_price > 0 else 1.0
        
        # Find structural levels
        support_levels = self._find_support_levels(setup, market)
        resistance_levels = self._find_resistance_levels(setup, market)
        
        # Calculate stops
        stops = self._calculate_stops(setup, market, support_levels, resistance_levels, atr)
        
        # Calculate targets
        targets = self._calculate_targets(setup, market, support_levels, resistance_levels, atr)
        
        # Calculate position size
        primary_stop = stops[0] if stops else None
        risk_distance = abs(setup.entry_price - primary_stop.price) if primary_stop else atr * 2
        
        position_size, position_pct, risk_amount = self._calculate_position_size(
            setup, risk_distance, atr_pct
        )
        
        # Calculate risk metrics
        first_target = targets[0] if targets else None
        rr_ratio = self._calculate_rr_ratio(setup.entry_price, primary_stop, first_target)
        max_rr = self._calculate_rr_ratio(setup.entry_price, primary_stop, targets[-1] if targets else None)
        win_prob = self._estimate_win_probability(setup, market, rr_ratio)
        expected_value = (win_prob * rr_ratio) - ((1 - win_prob) * 1.0)
        
        # Calculate guarding line for swing trades
        guarding = None
        if self.config.enable_guarding_line and self._is_swing_timeframe(setup.timeframe):
            guarding = self.guarding_line.calculate_initial_line(
                setup.entry_price,
                setup.direction,
                market.lows if setup.direction == "long" else market.highs
            )
        
        return RiskLevels(
            stops=stops,
            targets=targets,
            position_size=position_size,
            position_size_pct=position_pct,
            risk_amount=risk_amount,
            risk_reward_ratio=rr_ratio,
            max_risk_reward_ratio=max_rr,
            win_probability=win_prob,
            expected_value=expected_value,
            entry_price=setup.entry_price,
            direction=setup.direction,
            timeframe=setup.timeframe,
            guarding_line=guarding
        )
    
    def update_position(
        self,
        position_id: str,
        update: PositionUpdate,
        original_levels: RiskLevels
    ) -> RiskUpdate:
        """
        Update risk levels based on current price action.
        
        Call this on each bar (or price update) to get dynamic stop/target adjustments.
        """
        updated_stops = list(original_levels.stops)
        updated_targets = list(original_levels.targets)
        
        exit_signal = False
        exit_reason = None
        exit_pct = 0.0
        stop_moved = False
        new_stop = None
        guarding_active = False
        guarding_broken = False
        
        direction = original_levels.direction
        entry = original_levels.entry_price
        current = update.current_price
        
        # Check if any targets hit (partial exits)
        for target in original_levels.targets:
            if direction == "long" and current >= target.price:
                exit_signal = True
                exit_reason = f"Target hit: {target.reason}"
                exit_pct = target.exit_percentage
                break
            elif direction == "short" and current <= target.price:
                exit_signal = True
                exit_reason = f"Target hit: {target.reason}"
                exit_pct = target.exit_percentage
                break
        
        # Check guarding line (swing trades)
        if original_levels.guarding_line and update.bars_since_entry >= self.config.guarding_activation_bars:
            guarding_active = True
            guarding_price = self.guarding_line.get_current_level(
                original_levels.guarding_line,
                update.bars_since_entry
            )
            
            if direction == "long" and current < guarding_price:
                guarding_broken = True
                exit_signal = True
                exit_reason = "Guarding line broken"
                exit_pct = 100.0
            elif direction == "short" and current > guarding_price:
                guarding_broken = True
                exit_signal = True
                exit_reason = "Guarding line broken"
                exit_pct = 100.0
        
        # Trail stops if in profit
        if update.unrealized_pnl_pct > 0:
            new_stop = self._trail_stop(
                direction, entry, current,
                update.highest_since_entry,
                update.lowest_since_entry,
                original_levels.stops
            )
            if new_stop:
                stop_moved = True
        
        # Check if stop hit
        primary_stop = original_levels.get_primary_stop()
        if primary_stop:
            if direction == "long" and current <= primary_stop.price:
                exit_signal = True
                exit_reason = f"Stop hit: {primary_stop.reason}"
                exit_pct = 100.0
            elif direction == "short" and current >= primary_stop.price:
                exit_signal = True
                exit_reason = f"Stop hit: {primary_stop.reason}"
                exit_pct = 100.0
        
        return RiskUpdate(
            updated_stops=updated_stops,
            updated_targets=updated_targets,
            exit_signal=exit_signal,
            exit_reason=exit_reason,
            exit_percentage=exit_pct,
            stop_moved=stop_moved,
            new_stop_price=new_stop,
            guarding_active=guarding_active,
            guarding_broken=guarding_broken
        )
    
    def _find_support_levels(
        self,
        setup: TradeSetup,
        market: MarketContext
    ) -> List[Tuple[float, float]]:
        """Find support levels with confidence scores."""
        if market.support_levels:
            # Use pre-calculated levels
            return [(level, 0.8) for level in market.support_levels]
        
        # Calculate from price data
        supports = []
        lows = market.lows[:100]  # Look at recent 100 bars
        
        for i in range(2, len(lows) - 2):
            # Find swing lows
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                # Count touches
                level = lows[i]
                touches = sum(1 for low in lows if abs(low - level) / level < 0.005)
                confidence = min(1.0, touches / 5)
                supports.append((level, confidence))
        
        # Sort by proximity to current price
        supports.sort(key=lambda x: abs(x[0] - setup.entry_price))
        return supports[:5]  # Top 5 nearest
    
    def _find_resistance_levels(
        self,
        setup: TradeSetup,
        market: MarketContext
    ) -> List[Tuple[float, float]]:
        """Find resistance levels with confidence scores."""
        if market.resistance_levels:
            return [(level, 0.8) for level in market.resistance_levels]
        
        resistances = []
        highs = market.highs[:100]
        
        for i in range(2, len(highs) - 2):
            # Find swing highs
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                level = highs[i]
                touches = sum(1 for high in highs if abs(high - level) / level < 0.005)
                confidence = min(1.0, touches / 5)
                resistances.append((level, confidence))
        
        resistances.sort(key=lambda x: abs(x[0] - setup.entry_price))
        return resistances[:5]
    
    def _calculate_stops(
        self,
        setup: TradeSetup,
        market: MarketContext,
        supports: List[Tuple[float, float]],
        resistances: List[Tuple[float, float]],
        atr: float
    ) -> List[StopLevel]:
        """Calculate multi-tier stop levels."""
        stops = []
        entry = setup.entry_price
        direction = setup.direction
        
        if direction == "long":
            # Primary stop: Below nearest support
            if supports:
                support_price, confidence = supports[0]
                if support_price < entry:
                    stop_price = support_price - (atr * 0.2)  # Small buffer
                    distance_pct = ((entry - stop_price) / entry) * 100
                    
                    if distance_pct <= self.config.max_stop_pct:
                        stops.append(StopLevel(
                            price=stop_price,
                            type=StopType.PRIMARY,
                            confidence=confidence,
                            reason=f"Below support at {support_price:.2f}",
                            distance_pct=distance_pct
                        ))
            
            # Fallback: ATR-based primary stop
            if not stops:
                stop_price = entry - (atr * self.config.atr_stop_multiplier)
                distance_pct = ((entry - stop_price) / entry) * 100
                stops.append(StopLevel(
                    price=stop_price,
                    type=StopType.PRIMARY,
                    confidence=0.6,
                    reason=f"{self.config.atr_stop_multiplier}x ATR stop",
                    distance_pct=distance_pct
                ))
            
            # Secondary stop: Wider
            if self.config.enable_multi_tier_stops:
                secondary_price = entry - (atr * self.config.atr_stop_multiplier * 1.5)
                stops.append(StopLevel(
                    price=secondary_price,
                    type=StopType.SECONDARY,
                    confidence=0.5,
                    reason="Secondary ATR stop (1.5x)",
                    distance_pct=((entry - secondary_price) / entry) * 100
                ))
                
                # Safety net: Maximum loss
                safety_price = entry * (1 - self.config.max_stop_pct / 100)
                stops.append(StopLevel(
                    price=safety_price,
                    type=StopType.SAFETY_NET,
                    confidence=1.0,
                    reason=f"Maximum {self.config.max_stop_pct}% loss protection",
                    distance_pct=self.config.max_stop_pct
                ))
        
        else:  # short
            # Primary stop: Above nearest resistance
            if resistances:
                resist_price, confidence = resistances[0]
                if resist_price > entry:
                    stop_price = resist_price + (atr * 0.2)
                    distance_pct = ((stop_price - entry) / entry) * 100
                    
                    if distance_pct <= self.config.max_stop_pct:
                        stops.append(StopLevel(
                            price=stop_price,
                            type=StopType.PRIMARY,
                            confidence=confidence,
                            reason=f"Above resistance at {resist_price:.2f}",
                            distance_pct=distance_pct
                        ))
            
            if not stops:
                stop_price = entry + (atr * self.config.atr_stop_multiplier)
                distance_pct = ((stop_price - entry) / entry) * 100
                stops.append(StopLevel(
                    price=stop_price,
                    type=StopType.PRIMARY,
                    confidence=0.6,
                    reason=f"{self.config.atr_stop_multiplier}x ATR stop",
                    distance_pct=distance_pct
                ))
            
            if self.config.enable_multi_tier_stops:
                secondary_price = entry + (atr * self.config.atr_stop_multiplier * 1.5)
                stops.append(StopLevel(
                    price=secondary_price,
                    type=StopType.SECONDARY,
                    confidence=0.5,
                    reason="Secondary ATR stop (1.5x)",
                    distance_pct=((secondary_price - entry) / entry) * 100
                ))
                
                safety_price = entry * (1 + self.config.max_stop_pct / 100)
                stops.append(StopLevel(
                    price=safety_price,
                    type=StopType.SAFETY_NET,
                    confidence=1.0,
                    reason=f"Maximum {self.config.max_stop_pct}% loss protection",
                    distance_pct=self.config.max_stop_pct
                ))
        
        return stops
    
    def _calculate_targets(
        self,
        setup: TradeSetup,
        market: MarketContext,
        supports: List[Tuple[float, float]],
        resistances: List[Tuple[float, float]],
        atr: float
    ) -> List[TargetLevel]:
        """Calculate take-profit targets with partial exit percentages."""
        targets = []
        entry = setup.entry_price
        direction = setup.direction
        exit_ratios = self.config.partial_exit_ratios
        
        # Get stop distance for R:R calculations
        primary_stop_dist = atr * self.config.atr_stop_multiplier
        
        if direction == "long":
            # Target resistances above entry
            valid_resistances = [(r, c) for r, c in resistances if r > entry]
            valid_resistances.sort(key=lambda x: x[0])  # Sort by price ascending
            
            for i, (resist_price, confidence) in enumerate(valid_resistances[:3]):
                rr = (resist_price - entry) / primary_stop_dist
                if rr >= self.config.min_rr_ratio:
                    exit_pct = exit_ratios[i] if i < len(exit_ratios) else exit_ratios[-1]
                    targets.append(TargetLevel(
                        price=resist_price,
                        type=TargetType.STRUCTURAL,
                        exit_percentage=exit_pct * 100,
                        confidence=confidence,
                        reason=f"Resistance level (R:R {rr:.1f})",
                        distance_pct=((resist_price - entry) / entry) * 100
                    ))
            
            # If no structural targets, use R multiples
            if not targets:
                for i, multiple in enumerate([2.0, 3.0, 5.0]):
                    target_price = entry + (primary_stop_dist * multiple)
                    exit_pct = exit_ratios[i] if i < len(exit_ratios) else exit_ratios[-1]
                    targets.append(TargetLevel(
                        price=target_price,
                        type=TargetType.EXTENSION,
                        exit_percentage=exit_pct * 100,
                        confidence=0.5,
                        reason=f"{multiple}R target",
                        distance_pct=((target_price - entry) / entry) * 100
                    ))
        
        else:  # short
            # Target supports below entry
            valid_supports = [(s, c) for s, c in supports if s < entry]
            valid_supports.sort(key=lambda x: x[0], reverse=True)  # Sort descending
            
            for i, (support_price, confidence) in enumerate(valid_supports[:3]):
                rr = (entry - support_price) / primary_stop_dist
                if rr >= self.config.min_rr_ratio:
                    exit_pct = exit_ratios[i] if i < len(exit_ratios) else exit_ratios[-1]
                    targets.append(TargetLevel(
                        price=support_price,
                        type=TargetType.STRUCTURAL,
                        exit_percentage=exit_pct * 100,
                        confidence=confidence,
                        reason=f"Support level (R:R {rr:.1f})",
                        distance_pct=((entry - support_price) / entry) * 100
                    ))
            
            if not targets:
                for i, multiple in enumerate([2.0, 3.0, 5.0]):
                    target_price = entry - (primary_stop_dist * multiple)
                    exit_pct = exit_ratios[i] if i < len(exit_ratios) else exit_ratios[-1]
                    targets.append(TargetLevel(
                        price=target_price,
                        type=TargetType.EXTENSION,
                        exit_percentage=exit_pct * 100,
                        confidence=0.5,
                        reason=f"{multiple}R target",
                        distance_pct=((entry - target_price) / entry) * 100
                    ))
        
        return targets
    
    def _calculate_position_size(
        self,
        setup: TradeSetup,
        risk_distance: float,
        atr_pct: float
    ) -> Tuple[float, float, float]:
        """Calculate position size based on risk parameters."""
        risk_pct = setup.risk_per_trade_pct
        
        # Volatility adjustment
        if self.config.volatility_adjusted_sizing:
            # Reduce size in high volatility
            vol_factor = 2.0 / max(atr_pct, 0.5)  # Normalize to ~2% ATR baseline
            vol_factor = max(0.5, min(2.0, vol_factor))  # Clamp between 0.5x and 2x
            risk_pct *= vol_factor
        
        # Calculate risk amount
        risk_amount = setup.account_balance * (risk_pct / 100)
        
        # Position size = Risk Amount / Risk Distance
        if risk_distance > 0:
            position_size = risk_amount / risk_distance
        else:
            position_size = 0
        
        # Position as percentage of account
        position_value = position_size * setup.entry_price
        position_pct = (position_value / setup.account_balance) * 100
        
        return position_size, position_pct, risk_amount
    
    def _calculate_rr_ratio(
        self,
        entry: float,
        stop: Optional[StopLevel],
        target: Optional[TargetLevel]
    ) -> float:
        """Calculate risk:reward ratio."""
        if not stop or not target:
            return 0.0
        
        risk = abs(entry - stop.price)
        reward = abs(target.price - entry)
        
        return reward / risk if risk > 0 else 0.0
    
    def _estimate_win_probability(
        self,
        setup: TradeSetup,
        market: MarketContext,
        rr_ratio: float
    ) -> float:
        """Estimate win probability based on market context."""
        # Base probability
        base_prob = 0.45
        
        # Adjust for R:R (higher R:R = lower prob)
        rr_adjustment = -0.05 * (rr_ratio - 2.0)
        
        # Adjust for regime
        regime_adjustment = 0.0
        if market.regime:
            if setup.direction == "long":
                if market.regime == "trending_up":
                    regime_adjustment = 0.1
                elif market.regime == "trending_down":
                    regime_adjustment = -0.1
            else:  # short
                if market.regime == "trending_down":
                    regime_adjustment = 0.1
                elif market.regime == "trending_up":
                    regime_adjustment = -0.1
        
        return max(0.2, min(0.8, base_prob + rr_adjustment + regime_adjustment))
    
    def _trail_stop(
        self,
        direction: str,
        entry: float,
        current: float,
        highest: float,
        lowest: float,
        stops: List[StopLevel]
    ) -> Optional[float]:
        """Calculate trailed stop price."""
        if not stops:
            return None
        
        primary = stops[0]
        
        if direction == "long":
            # Trail to breakeven if 1R profit
            profit_pct = (current - entry) / entry * 100
            if profit_pct >= primary.distance_pct:
                # Trail to breakeven + small buffer
                new_stop = entry * 1.001
                if new_stop > primary.price:
                    return new_stop
        else:
            profit_pct = (entry - current) / entry * 100
            if profit_pct >= primary.distance_pct:
                new_stop = entry * 0.999
                if new_stop < primary.price:
                    return new_stop
        
        return None
    
    def _is_swing_timeframe(self, timeframe: str) -> bool:
        """Check if timeframe is suitable for swing trading."""
        swing_timeframes = {"4h", "1d", "1w", "4H", "1D", "1W", "daily", "weekly"}
        return timeframe.lower() in {tf.lower() for tf in swing_timeframes}


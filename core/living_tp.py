"""
Living Take-Profit Engine
=========================

Dynamic take-profit system that adapts to market structure.
Instead of fixed targets, exits only when structure breaks.

Key Principles:
1. Don't exit just because you hit a number - exit when structure breaks
2. Scale out at confluence zones (where multiple S/R align)
3. Let winners run by adding dynamic targets as price extends
4. Trail using structural levels, not arbitrary percentages
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum


class StructureHealth(Enum):
    """Health status of supporting structure."""
    STRONG = "strong"       # Structure intact, no concerns
    WEAKENING = "weakening" # Structure showing stress
    BROKEN = "broken"       # Structure has failed


@dataclass
class StructuralTarget:
    """A target based on market structure."""
    price: float
    structure_type: str      # "resistance", "fib_extension", "volume_gap", "round_number"
    strength: float          # 0-1 strength score
    touches: int             # How many times tested
    exit_pct: float          # Percentage of position to exit here
    is_dynamic: bool = False # Was added after entry
    hit: bool = False        # Has been reached
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "price": self.price,
            "structure_type": self.structure_type,
            "strength": self.strength,
            "touches": self.touches,
            "exit_pct": self.exit_pct,
            "is_dynamic": self.is_dynamic,
            "hit": self.hit
        }


@dataclass
class SupportingStructure:
    """Structure that supports staying in the trade."""
    price: float
    structure_type: str
    health: StructureHealth
    last_tested: int         # Bars since last test
    hold_confidence: float   # 0-1 confidence to keep holding


class LivingTakeProfit:
    """
    Dynamic take-profit engine that adapts to market structure.
    
    Usage:
        ltp = LivingTakeProfit()
        targets = ltp.identify_targets(entry, direction, market_data)
        update = ltp.update_targets(current_price, current_bar, market_data)
    """
    
    def __init__(
        self,
        min_structure_strength: float = 0.3,
        confluence_bonus: float = 0.2,
        dynamic_target_threshold: float = 1.5  # Add new target at 1.5R
    ):
        self.min_structure_strength = min_structure_strength
        self.confluence_bonus = confluence_bonus
        self.dynamic_target_threshold = dynamic_target_threshold
        
        self._active_targets: List[StructuralTarget] = []
        self._supporting_structures: List[SupportingStructure] = []
        self._entry_price: float = 0
        self._direction: str = ""
        self._risk_distance: float = 0
    
    def identify_targets(
        self,
        entry_price: float,
        direction: str,
        stop_price: float,
        highs: List[float],
        lows: List[float],
        closes: List[float]
    ) -> List[StructuralTarget]:
        """
        Identify initial take-profit targets based on structure.
        
        Returns targets sorted by distance from entry.
        """
        self._entry_price = entry_price
        self._direction = direction
        self._risk_distance = abs(entry_price - stop_price)
        
        targets = []
        
        # Find structural levels
        if direction == "long":
            # Looking for resistance above entry
            resistance_levels = self._find_resistance(highs, closes, entry_price)
            for level, strength, touches in resistance_levels:
                if level > entry_price:
                    targets.append(StructuralTarget(
                        price=level,
                        structure_type="resistance",
                        strength=strength,
                        touches=touches,
                        exit_pct=0  # Will be calculated later
                    ))
        else:
            # Looking for support below entry
            support_levels = self._find_support(lows, closes, entry_price)
            for level, strength, touches in support_levels:
                if level < entry_price:
                    targets.append(StructuralTarget(
                        price=level,
                        structure_type="support",
                        strength=strength,
                        touches=touches,
                        exit_pct=0
                    ))
        
        # Add Fibonacci extension targets
        fib_targets = self._calculate_fib_targets(entry_price, stop_price, direction)
        targets.extend(fib_targets)
        
        # Add round number targets
        round_targets = self._find_round_numbers(entry_price, direction)
        targets.extend(round_targets)
        
        # Check for confluence and boost strength
        targets = self._apply_confluence(targets)
        
        # Filter by minimum strength
        targets = [t for t in targets if t.strength >= self.min_structure_strength]
        
        # Sort by distance
        if direction == "long":
            targets.sort(key=lambda t: t.price)
        else:
            targets.sort(key=lambda t: t.price, reverse=True)
        
        # Assign exit percentages
        targets = self._assign_exit_percentages(targets)
        
        self._active_targets = targets
        return targets
    
    def update_targets(
        self,
        current_price: float,
        bars_since_entry: int,
        highs: List[float],
        lows: List[float]
    ) -> Tuple[List[StructuralTarget], bool, float]:
        """
        Update targets based on current price action.
        
        Returns:
            - Updated target list
            - Whether to exit (structure broken)
            - Exit percentage if exiting
        """
        exit_signal = False
        exit_pct = 0.0
        
        # Check if any targets hit
        for target in self._active_targets:
            if target.hit:
                continue
            
            if self._direction == "long" and current_price >= target.price:
                target.hit = True
                exit_signal = True
                exit_pct = target.exit_pct
            elif self._direction == "short" and current_price <= target.price:
                target.hit = True
                exit_signal = True
                exit_pct = target.exit_pct
        
        # Add dynamic targets if price has extended
        current_r = self._calculate_r_multiple(current_price)
        highest_target_r = max(
            self._calculate_r_multiple(t.price) 
            for t in self._active_targets
        ) if self._active_targets else 0
        
        if current_r > highest_target_r * 0.8:  # Approaching highest target
            new_targets = self._add_dynamic_targets(
                current_price, highs, lows, bars_since_entry
            )
            self._active_targets.extend(new_targets)
        
        return self._active_targets, exit_signal, exit_pct
    
    def check_structure_health(
        self,
        current_price: float,
        recent_closes: List[float]
    ) -> StructureHealth:
        """
        Check if supporting structure is still intact.
        
        Used to determine if we should stay in the trade.
        """
        if len(recent_closes) < 3:
            return StructureHealth.STRONG
        
        # Check for lower lows (long) or higher highs (short)
        if self._direction == "long":
            # Is price making lower lows?
            if recent_closes[0] < recent_closes[1] < recent_closes[2]:
                return StructureHealth.WEAKENING
            
            # Big drop?
            drop = (max(recent_closes[-10:]) - current_price) / self._entry_price * 100
            if drop > 3:
                return StructureHealth.BROKEN
        
        else:  # short
            if recent_closes[0] > recent_closes[1] > recent_closes[2]:
                return StructureHealth.WEAKENING
            
            rise = (current_price - min(recent_closes[-10:])) / self._entry_price * 100
            if rise > 3:
                return StructureHealth.BROKEN
        
        return StructureHealth.STRONG
    
    def _find_resistance(
        self,
        highs: List[float],
        closes: List[float],
        current_price: float
    ) -> List[Tuple[float, float, int]]:
        """Find resistance levels above current price."""
        levels = []
        
        for i in range(2, min(len(highs) - 2, 100)):
            high = highs[i]
            if high <= current_price:
                continue
            
            # Is this a swing high?
            if high > highs[i-1] and high > highs[i-2] and \
               high > highs[i+1] and high > highs[i+2]:
                # Count touches
                touches = sum(
                    1 for h in highs[:50] 
                    if abs(h - high) / high < 0.003
                )
                strength = min(1.0, touches / 4)
                
                # Check if level has been respected
                if any(c > high for c in closes[:i]):
                    strength *= 0.7  # Reduce if broken before
                
                levels.append((high, strength, touches))
        
        return levels[:5]  # Top 5
    
    def _find_support(
        self,
        lows: List[float],
        closes: List[float],
        current_price: float
    ) -> List[Tuple[float, float, int]]:
        """Find support levels below current price."""
        levels = []
        
        for i in range(2, min(len(lows) - 2, 100)):
            low = lows[i]
            if low >= current_price:
                continue
            
            if low < lows[i-1] and low < lows[i-2] and \
               low < lows[i+1] and low < lows[i+2]:
                touches = sum(
                    1 for l in lows[:50]
                    if abs(l - low) / low < 0.003
                )
                strength = min(1.0, touches / 4)
                
                if any(c < low for c in closes[:i]):
                    strength *= 0.7
                
                levels.append((low, strength, touches))
        
        return levels[:5]
    
    def _calculate_fib_targets(
        self,
        entry: float,
        stop: float,
        direction: str
    ) -> List[StructuralTarget]:
        """Calculate Fibonacci extension targets."""
        targets = []
        risk = abs(entry - stop)
        
        fib_levels = [1.618, 2.618, 4.236]
        
        for fib in fib_levels:
            if direction == "long":
                target_price = entry + (risk * fib)
            else:
                target_price = entry - (risk * fib)
            
            targets.append(StructuralTarget(
                price=target_price,
                structure_type="fib_extension",
                strength=0.5,  # Medium strength
                touches=0,
                exit_pct=0
            ))
        
        return targets
    
    def _find_round_numbers(
        self,
        entry: float,
        direction: str
    ) -> List[StructuralTarget]:
        """Find psychological round number levels."""
        targets = []
        
        # Determine round number interval based on price
        if entry > 10000:
            interval = 1000
        elif entry > 1000:
            interval = 100
        elif entry > 100:
            interval = 10
        else:
            interval = 1
        
        # Find nearest round numbers
        base = (entry // interval) * interval
        
        for i in range(1, 6):
            if direction == "long":
                level = base + (interval * i)
                if level > entry:
                    targets.append(StructuralTarget(
                        price=level,
                        structure_type="round_number",
                        strength=0.3,
                        touches=0,
                        exit_pct=0
                    ))
            else:
                level = base - (interval * (i - 1))
                if level < entry:
                    targets.append(StructuralTarget(
                        price=level,
                        structure_type="round_number",
                        strength=0.3,
                        touches=0,
                        exit_pct=0
                    ))
        
        return targets[:3]
    
    def _apply_confluence(
        self,
        targets: List[StructuralTarget]
    ) -> List[StructuralTarget]:
        """Boost strength of levels that have confluence."""
        for i, target in enumerate(targets):
            for other in targets:
                if target == other:
                    continue
                
                # Check if within 0.5% of each other
                if abs(target.price - other.price) / target.price < 0.005:
                    target.strength = min(1.0, target.strength + self.confluence_bonus)
        
        return targets
    
    def _assign_exit_percentages(
        self,
        targets: List[StructuralTarget]
    ) -> List[StructuralTarget]:
        """Assign exit percentages based on target count and strength."""
        if not targets:
            return targets
        
        # Simple split: 33% at each of first 3 targets
        num_targets = min(len(targets), 3)
        base_pct = 100 / num_targets
        
        for i, target in enumerate(targets[:3]):
            target.exit_pct = base_pct
        
        # Any remaining targets get 0% (trailing stops will handle)
        for target in targets[3:]:
            target.exit_pct = 0
        
        return targets
    
    def _calculate_r_multiple(self, price: float) -> float:
        """Calculate R-multiple for a given price."""
        if self._risk_distance == 0:
            return 0
        
        if self._direction == "long":
            return (price - self._entry_price) / self._risk_distance
        else:
            return (self._entry_price - price) / self._risk_distance
    
    def _add_dynamic_targets(
        self,
        current_price: float,
        highs: List[float],
        lows: List[float],
        bars_since_entry: int
    ) -> List[StructuralTarget]:
        """Add new targets as price extends."""
        new_targets = []
        
        # Only add if we're past threshold
        current_r = self._calculate_r_multiple(current_price)
        if current_r < self.dynamic_target_threshold:
            return new_targets
        
        # Find structure ahead
        if self._direction == "long":
            ahead_levels = self._find_resistance(highs, [], current_price)
        else:
            ahead_levels = self._find_support(lows, [], current_price)
        
        for level, strength, touches in ahead_levels[:2]:
            # Check not already in targets
            existing_prices = {t.price for t in self._active_targets}
            if level not in existing_prices:
                new_targets.append(StructuralTarget(
                    price=level,
                    structure_type="resistance" if self._direction == "long" else "support",
                    strength=strength,
                    touches=touches,
                    exit_pct=25,  # Smaller exit at dynamic targets
                    is_dynamic=True
                ))
        
        return new_targets


"""
Guarding Line System
====================

Trailing structural stop for swing trades.
Instead of fixed trailing percentages, uses a trendline that follows structure.

Key Principles (from MCF):
1. Don't exit just because price retraces - exit when STRUCTURE breaks
2. Draw a line under the lows (long) or above the highs (short)
3. Only activate after position is in profit (delayed activation)
4. Give the trade room to breathe in the beginning
5. Tighten as the move extends

Usage:
    gl = GuardingLine(activation_bars=10)
    line = gl.calculate_initial_line(entry, direction, recent_lows)
    current_guard = gl.get_current_level(line, bars_since_entry)
    is_broken = gl.check_break(current_price, current_guard, direction)
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
import numpy as np


@dataclass
class GuardingLineState:
    """State of the guarding line for a position."""
    slope: float              # Price change per bar
    intercept: float          # Starting price level
    activation_bar: int       # Bar at which guarding activates
    is_active: bool           # Whether currently active
    current_level: float      # Current guarding price
    buffer_pct: float         # Buffer below line
    last_updated: int         # Last bar updated


class GuardingLine:
    """
    Dynamic trailing stop based on structural trendlines.
    
    Unlike fixed trailing stops, the guarding line follows the
    structure of the move, allowing for natural retracements
    while protecting against genuine structure breaks.
    """
    
    def __init__(
        self,
        activation_bars: int = 10,    # Bars before guarding activates
        buffer_pct: float = 0.3,      # Buffer below guarding line
        min_slope_pct: float = 0.01,  # Minimum slope per bar
        tightening_factor: float = 1.2 # How much to tighten as trade extends
    ):
        self.activation_bars = activation_bars
        self.buffer_pct = buffer_pct
        self.min_slope_pct = min_slope_pct
        self.tightening_factor = tightening_factor
    
    def calculate_initial_line(
        self,
        entry_price: float,
        direction: str,
        price_data: List[float],  # Lows for long, Highs for short
        lookback: int = 20
    ) -> Dict[str, float]:
        """
        Calculate the initial guarding line parameters.
        
        Uses linear regression on recent swing points to establish
        the line's slope and intercept.
        """
        if len(price_data) < 5:
            # Not enough data - use flat line at entry
            return {
                "slope": 0,
                "intercept": entry_price * (0.97 if direction == "long" else 1.03),
                "activation_bar": self.activation_bars,
                "buffer_pct": self.buffer_pct
            }
        
        # Get recent data
        recent = price_data[:min(lookback, len(price_data))]
        
        # Find swing points
        swing_points = self._find_swing_points(recent, direction)
        
        if len(swing_points) < 2:
            # Use simple linear fit on all data
            x = np.arange(len(recent))
            y = np.array(recent)
            
            # Linear regression
            slope, intercept = np.polyfit(x, y, 1)
        else:
            # Fit line through swing points
            x = np.array([p[0] for p in swing_points])
            y = np.array([p[1] for p in swing_points])
            slope, intercept = np.polyfit(x, y, 1)
        
        # Ensure slope direction is correct
        if direction == "long":
            # Guarding line should go UP (or flat) for longs
            slope = max(0, slope)
            # Add buffer below
            intercept = intercept * (1 - self.buffer_pct / 100)
        else:
            # Guarding line should go DOWN (or flat) for shorts
            slope = min(0, slope)
            # Add buffer above
            intercept = intercept * (1 + self.buffer_pct / 100)
        
        return {
            "slope": slope,
            "intercept": intercept,
            "activation_bar": self.activation_bars,
            "buffer_pct": self.buffer_pct
        }
    
    def get_current_level(
        self,
        line_params: Dict[str, float],
        bars_since_entry: int
    ) -> float:
        """
        Get the current guarding line level.
        
        Returns the price at which the guarding line sits for the current bar.
        """
        slope = line_params["slope"]
        intercept = line_params["intercept"]
        activation = line_params.get("activation_bar", self.activation_bars)
        
        if bars_since_entry < activation:
            # Not yet active - return a very wide level
            return intercept * 0.9 if slope >= 0 else intercept * 1.1
        
        # Calculate current level
        bars_active = bars_since_entry - activation
        current_level = intercept + (slope * bars_active)
        
        return current_level
    
    def update_line(
        self,
        line_params: Dict[str, float],
        direction: str,
        current_price: float,
        recent_prices: List[float],  # Recent lows (long) or highs (short)
        bars_since_entry: int
    ) -> Dict[str, float]:
        """
        Update the guarding line based on new price action.
        
        As the trade extends, the line may be adjusted to follow
        the new structure while still protecting profits.
        """
        current_level = self.get_current_level(line_params, bars_since_entry)
        
        # Only update if trade is extended and in profit
        if bars_since_entry < line_params.get("activation_bar", self.activation_bars):
            return line_params
        
        # Check if we need to tighten
        if len(recent_prices) < 5:
            return line_params
        
        recent = recent_prices[:10]
        
        if direction == "long":
            # Find recent higher lows
            recent_low = min(recent)
            
            # If recent low is above current guarding level, we can tighten
            if recent_low > current_level * 1.01:
                # Raise the line
                new_intercept = recent_low * (1 - self.buffer_pct / 100)
                return {
                    **line_params,
                    "intercept": new_intercept,
                    "slope": max(0, line_params["slope"])  # Keep or steepen
                }
        
        else:  # short
            recent_high = max(recent)
            
            if recent_high < current_level * 0.99:
                new_intercept = recent_high * (1 + self.buffer_pct / 100)
                return {
                    **line_params,
                    "intercept": new_intercept,
                    "slope": min(0, line_params["slope"])
                }
        
        return line_params
    
    def check_break(
        self,
        current_price: float,
        guarding_level: float,
        direction: str,
        require_close: bool = True
    ) -> Tuple[bool, str]:
        """
        Check if the guarding line has been broken.
        
        Args:
            current_price: Current price (close if require_close=True)
            guarding_level: Current guarding line level
            direction: "long" or "short"
            require_close: If True, requires candle CLOSE through level
        
        Returns:
            Tuple of (is_broken, reason)
        """
        if direction == "long":
            if current_price < guarding_level:
                return True, f"Price {current_price:.2f} broke below guarding at {guarding_level:.2f}"
        else:
            if current_price > guarding_level:
                return True, f"Price {current_price:.2f} broke above guarding at {guarding_level:.2f}"
        
        return False, ""
    
    def get_status(
        self,
        line_params: Dict[str, float],
        current_price: float,
        direction: str,
        bars_since_entry: int
    ) -> Dict:
        """
        Get complete status of the guarding line.
        """
        activation_bar = line_params.get("activation_bar", self.activation_bars)
        is_active = bars_since_entry >= activation_bar
        current_level = self.get_current_level(line_params, bars_since_entry)
        
        # Distance from current price
        if direction == "long":
            distance = current_price - current_level
            distance_pct = (distance / current_price) * 100
        else:
            distance = current_level - current_price
            distance_pct = (distance / current_price) * 100
        
        is_broken, break_reason = self.check_break(current_price, current_level, direction)
        
        return {
            "is_active": is_active,
            "current_level": current_level,
            "distance": distance,
            "distance_pct": distance_pct,
            "bars_until_activation": max(0, activation_bar - bars_since_entry),
            "is_broken": is_broken,
            "break_reason": break_reason,
            "slope": line_params["slope"],
            "intercept": line_params["intercept"]
        }
    
    def _find_swing_points(
        self,
        prices: List[float],
        direction: str
    ) -> List[Tuple[int, float]]:
        """Find swing lows (long) or swing highs (short)."""
        swing_points = []
        
        for i in range(2, len(prices) - 2):
            if direction == "long":
                # Find swing lows
                if prices[i] < prices[i-1] and prices[i] < prices[i-2] and \
                   prices[i] < prices[i+1] and prices[i] < prices[i+2]:
                    swing_points.append((i, prices[i]))
            else:
                # Find swing highs
                if prices[i] > prices[i-1] and prices[i] > prices[i-2] and \
                   prices[i] > prices[i+1] and prices[i] > prices[i+2]:
                    swing_points.append((i, prices[i]))
        
        return swing_points
    
    def visualize_line(
        self,
        line_params: Dict[str, float],
        num_bars: int = 50
    ) -> List[float]:
        """
        Generate guarding line values for visualization.
        
        Returns a list of price levels for each bar.
        """
        levels = []
        for bar in range(num_bars):
            level = self.get_current_level(line_params, bar)
            levels.append(level)
        return levels


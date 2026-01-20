"""
BASTION Core Module
===================

Risk management engine and supporting components.
"""

from .models import (
    StopType,
    TargetType,
    Direction,
    StopLevel,
    TargetLevel,
    RiskLevels,
    TradeSetup,
    MarketContext,
    PositionUpdate,
    RiskUpdate
)

from .engine import RiskEngine, RiskEngineConfig
from .living_tp import LivingTakeProfit, StructureHealth, StructuralTarget
from .guarding_line import GuardingLine
from .adaptive_budget import AdaptiveRiskBudget, TradeBudget, Shot, ShotStatus

__all__ = [
    # Models
    "StopType",
    "TargetType", 
    "Direction",
    "StopLevel",
    "TargetLevel",
    "RiskLevels",
    "TradeSetup",
    "MarketContext",
    "PositionUpdate",
    "RiskUpdate",
    # Engine
    "RiskEngine",
    "RiskEngineConfig",
    # Living Take-Profit
    "LivingTakeProfit",
    "StructureHealth",
    "StructuralTarget",
    # Guarding Line
    "GuardingLine",
    # Adaptive Budget
    "AdaptiveRiskBudget",
    "TradeBudget",
    "Shot",
    "ShotStatus",
]

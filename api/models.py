"""
BASTION API Models
==================

Pydantic models for request/response validation.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class CalculateRiskRequest(BaseModel):
    """Request model for /calculate endpoint."""
    
    symbol: str = Field(
        default="BTCUSDT",
        description="Trading pair symbol (e.g., BTCUSDT, ETHUSDT)"
    )
    entry_price: float = Field(
        ...,
        gt=0,
        description="Entry price for the trade"
    )
    direction: str = Field(
        ...,
        pattern="^(long|short)$",
        description="Trade direction: 'long' or 'short'"
    )
    timeframe: str = Field(
        default="4h",
        description="Candle timeframe: 1m, 5m, 15m, 1h, 4h, 1d"
    )
    account_balance: float = Field(
        default=100000,
        gt=0,
        description="Account balance in USD"
    )
    risk_per_trade_pct: float = Field(
        default=1.0,
        gt=0,
        le=10,
        description="Risk percentage per trade (0.1 - 10%)"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "symbol": "BTCUSDT",
                "entry_price": 95000,
                "direction": "long",
                "timeframe": "4h",
                "account_balance": 100000,
                "risk_per_trade_pct": 1.0
            }
        }


class StopLevelResponse(BaseModel):
    """Stop-loss level in response."""
    
    type: str = Field(description="Stop type: primary, secondary, safety_net")
    price: float = Field(description="Stop price level")
    distance_pct: float = Field(description="Distance from entry as percentage")
    reason: str = Field(description="Reason for this stop level")
    confidence: float = Field(description="Confidence score (0-1)")


class TargetLevelResponse(BaseModel):
    """Take-profit target in response."""
    
    price: float = Field(description="Target price level")
    exit_percentage: float = Field(description="Percentage of position to exit")
    distance_pct: float = Field(description="Distance from entry as percentage")
    reason: str = Field(description="Reason for this target")
    confidence: float = Field(description="Confidence score (0-1)")


class RiskLevelsResponse(BaseModel):
    """Complete risk calculation response."""
    
    symbol: str
    entry_price: float
    direction: str
    current_price: float
    
    stops: List[StopLevelResponse]
    targets: List[TargetLevelResponse]
    
    position_size: float = Field(description="Position size in base currency")
    position_size_pct: float = Field(description="Position as % of account")
    risk_amount: float = Field(description="Dollar risk amount")
    
    risk_reward_ratio: float = Field(description="R:R to first target")
    max_risk_reward_ratio: float = Field(description="R:R to final target")
    win_probability: float = Field(description="Estimated win probability")
    expected_value: float = Field(description="Expected value in R")
    
    guarding_line: Optional[dict] = Field(
        default=None,
        description="Guarding line parameters for swing trades"
    )
    
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        schema_extra = {
            "example": {
                "symbol": "BTCUSDT",
                "entry_price": 95000,
                "direction": "long",
                "current_price": 94328,
                "stops": [
                    {
                        "type": "primary",
                        "price": 92500,
                        "distance_pct": 2.6,
                        "reason": "Below support at 92800",
                        "confidence": 0.8
                    }
                ],
                "targets": [
                    {
                        "price": 98000,
                        "exit_percentage": 33,
                        "distance_pct": 3.2,
                        "reason": "Resistance level (R:R 2.5)",
                        "confidence": 0.7
                    }
                ],
                "position_size": 0.421,
                "position_size_pct": 33.3,
                "risk_amount": 1000,
                "risk_reward_ratio": 2.5,
                "max_risk_reward_ratio": 6.5,
                "win_probability": 0.52,
                "expected_value": 0.8,
                "guarding_line": None
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""
    
    error: str = Field(description="Error message")
    detail: Optional[str] = Field(default=None, description="Detailed error information")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str = Field(default="ok")
    service: str = Field(default="BASTION")
    version: str = Field(default="1.0.0-MVP")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


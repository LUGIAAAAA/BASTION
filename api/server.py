"""
BASTION API Server
==================

FastAPI application for BASTION risk management.

Endpoints:
    GET  /health   - Health check
    POST /calculate - Calculate risk levels for a trade
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
bastion_path = Path(__file__).parent.parent
sys.path.insert(0, str(bastion_path.parent))

from bastion.api.models import (
    CalculateRiskRequest,
    RiskLevelsResponse,
    ErrorResponse,
    HealthResponse,
    StopLevelResponse,
    TargetLevelResponse
)
from bastion.core.engine import RiskEngine
from bastion.core.models import TradeSetup, MarketContext
from bastion.data.fetcher import LiveDataFetcher

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="BASTION API",
    description="Proactive Risk Management Infrastructure",
    version="1.0.0-MVP",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
risk_engine = RiskEngine()
data_fetcher = LiveDataFetcher()


@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup."""
    logger.info("🏰 BASTION API starting up...")
    logger.info("Risk engine initialized")
    logger.info("Data fetcher ready")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    logger.info("🏰 BASTION API shutting down...")
    await data_fetcher.close()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc)
        ).dict()
    )


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint - redirect to docs."""
    return {
        "service": "BASTION API",
        "version": "1.0.0-MVP",
        "docs": "/docs",
        "health": "/health",
        "calculate": "/calculate"
    }


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    Health check endpoint.
    
    Returns service status and version information.
    """
    return HealthResponse(
        status="ok",
        service="BASTION",
        version="1.0.0-MVP"
    )


@app.post("/calculate", response_model=RiskLevelsResponse, tags=["Risk"])
async def calculate_risk(request: CalculateRiskRequest):
    """
    Calculate risk levels for a trade setup.
    
    Fetches market data, runs risk calculations, and returns:
    - Structural stop-loss levels
    - Dynamic take-profit targets
    - Position sizing
    - Risk metrics
    
    **Example Request:**
    ```json
    {
      "symbol": "BTCUSDT",
      "entry_price": 95000,
      "direction": "long",
      "timeframe": "4h",
      "account_balance": 100000,
      "risk_per_trade_pct": 1.0
    }
    ```
    """
    try:
        logger.info(f"Calculating risk for {request.symbol} {request.direction} @ {request.entry_price}")
        
        # Fetch market data
        try:
            df = await data_fetcher.get_ohlcv(
                symbol=request.symbol,
                interval=request.timeframe,
                limit=200
            )
            
            if df.empty:
                raise HTTPException(
                    status_code=502,
                    detail=f"Could not fetch market data for {request.symbol}"
                )
            
            logger.info(f"Fetched {len(df)} candles for {request.symbol}")
            
        except Exception as e:
            logger.error(f"Data fetch failed: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"Failed to fetch market data: {str(e)}"
            )
        
        # Prepare market context
        market = MarketContext(
            timestamps=df.index.tolist(),
            opens=df['open'].tolist(),
            highs=df['high'].tolist(),
            lows=df['low'].tolist(),
            closes=df['close'].tolist(),
            volumes=df['volume'].tolist(),
            current_price=float(df['close'].iloc[-1])
        )
        
        # Prepare trade setup
        setup = TradeSetup(
            entry_price=request.entry_price,
            direction=request.direction,
            timeframe=request.timeframe,
            symbol=request.symbol,
            account_balance=request.account_balance,
            risk_per_trade_pct=request.risk_per_trade_pct
        )
        
        # Calculate risk levels
        try:
            levels = risk_engine.calculate_risk_levels(setup, market)
            logger.info(f"Risk calculated: {len(levels.stops)} stops, {len(levels.targets)} targets")
            
        except Exception as e:
            logger.error(f"Risk calculation failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Risk calculation error: {str(e)}"
            )
        
        # Format response
        response = RiskLevelsResponse(
            symbol=request.symbol,
            entry_price=request.entry_price,
            direction=request.direction,
            current_price=market.current_price,
            stops=[
                StopLevelResponse(
                    type=s.type.value,
                    price=s.price,
                    distance_pct=s.distance_pct,
                    reason=s.reason,
                    confidence=s.confidence
                )
                for s in levels.stops
            ],
            targets=[
                TargetLevelResponse(
                    price=t.price,
                    exit_percentage=t.exit_percentage,
                    distance_pct=t.distance_pct,
                    reason=t.reason,
                    confidence=t.confidence
                )
                for t in levels.targets
            ],
            position_size=levels.position_size,
            position_size_pct=levels.position_size_pct,
            risk_amount=levels.risk_amount,
            risk_reward_ratio=levels.risk_reward_ratio,
            max_risk_reward_ratio=levels.max_risk_reward_ratio,
            win_probability=levels.win_probability,
            expected_value=levels.expected_value,
            guarding_line=levels.guarding_line
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in /calculate: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )


# Mount static files for web calculator (if web/ directory exists)
web_dir = bastion_path / "web"
if web_dir.exists():
    app.mount("/app", StaticFiles(directory=str(web_dir), html=True), name="web")
    logger.info(f"Mounted web calculator at /app")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)


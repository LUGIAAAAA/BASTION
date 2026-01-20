"""
BASTION Session API Routes
==========================

API endpoints for live trading session management.

Endpoints:
    POST   /session/create     - Create new trading session
    POST   /session/{id}/shot  - Take a shot (entry)
    POST   /session/{id}/update - Update with new bar data
    POST   /session/{id}/exit  - Execute exit
    GET    /session/{id}       - Get session state
    GET    /sessions           - List active sessions
    DELETE /session/{id}       - Close session
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

from core.session import (
    SessionManager, SessionState, SessionEntry,
    SessionUpdate, SessionStatus, ExitReason, TradePhase
)
from data.live_feed import LiveFeed

router = APIRouter(prefix="/session", tags=["Sessions"])

# Global instances (initialized in server.py)
session_manager: SessionManager = None
live_feed: LiveFeed = None


def get_manager() -> SessionManager:
    """Get the session manager instance."""
    global session_manager
    if session_manager is None:
        session_manager = SessionManager()
    return session_manager


def get_feed() -> LiveFeed:
    """Get the live feed instance."""
    return live_feed


# =============================================================================
# REQUEST MODELS
# =============================================================================

class CreateSessionRequest(BaseModel):
    """Request to create a new trading session."""
    symbol: str = Field(default="BTCUSDT", description="Trading pair")
    direction: str = Field(..., pattern="^(long|short)$", description="Trade direction")
    timeframe: str = Field(default="4h", description="Candle timeframe")
    account_balance: float = Field(default=100000, gt=0, description="Account balance USD")
    structural_support: Optional[float] = Field(None, gt=0, description="Grade 3-4 validated support level")
    structural_level: Optional[float] = Field(None, gt=0, description="Alias for structural_support")
    entry_price: Optional[float] = Field(None, gt=0, description="Entry price for first shot")
    targets: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Target levels [{price, exit_percentage, reason}]"
    )
    risk_cap_pct: float = Field(default=2.0, gt=0, le=10, description="Total risk cap %")
    max_shots: int = Field(default=3, ge=1, le=5, description="Max entries")
    timeout_hours: int = Field(default=168, ge=1, description="Session timeout hours")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "symbol": "BTCUSDT",
                "direction": "long",
                "timeframe": "4h",
                "account_balance": 100000,
                "structural_support": 93200,
                "targets": [
                    {"price": 97500, "exit_percentage": 33, "reason": "HVN mountain"},
                    {"price": 99800, "exit_percentage": 33, "reason": "Value Area High"},
                    {"price": 102000, "exit_percentage": 34, "reason": "Extension target"}
                ],
                "risk_cap_pct": 2.0,
                "max_shots": 3
            }
        }
    }


class TakeShotRequest(BaseModel):
    """Request to take a shot (entry)."""
    entry_price: float = Field(..., gt=0, description="Entry price")
    current_atr: Optional[float] = Field(None, description="Current ATR for buffer calculation")
    stop_override: Optional[float] = Field(None, description="Override stop price")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "entry_price": 94500,
                "current_atr": 600
            }
        }
    }


class UpdateSessionRequest(BaseModel):
    """Request to update session with new bar data."""
    current_price: float = Field(..., gt=0, description="Current price")
    current_bar: int = Field(..., ge=0, description="Bar number since first entry")
    recent_lows: Optional[List[float]] = Field(None, description="Recent swing lows (for guarding)")
    recent_highs: Optional[List[float]] = Field(None, description="Recent swing highs (for guarding)")
    opposing_signal: bool = Field(default=False, description="Opposite MCF signal detected")
    momentum_exhaustion: bool = Field(default=False, description="Momentum exhaustion detected")
    volume_climax: bool = Field(default=False, description="Volume climax detected")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "current_price": 95500,
                "current_bar": 12,
                "recent_lows": [94200, 94100, 94300, 94500, 94400],
                "opposing_signal": False,
                "momentum_exhaustion": False,
                "volume_climax": False
            }
        }
    }


class ExecuteExitRequest(BaseModel):
    """Request to execute an exit."""
    exit_price: Optional[float] = Field(None, gt=0, description="Exit price (uses current if not provided)")
    exit_reason: Optional[str] = Field(None, description="Reason for exit")
    reason: Optional[str] = Field(None, description="Alias for exit_reason")
    exit_percentage: float = Field(default=100, ge=0, le=100, description="% of position to exit")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "exit_price": 97500,
                "exit_reason": "target_hit",
                "exit_percentage": 33
            }
        }
    }


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class SessionResponse(BaseModel):
    """Session state response."""
    id: str
    symbol: str
    direction: str
    timeframe: str
    status: str
    phase: str
    created_at: str
    expires_at: Optional[str]
    
    shots_taken: int
    max_shots: int
    entries: List[Dict[str, Any]]
    
    position: Dict[str, float]
    risk: Dict[str, float]
    stops: Dict[str, Any]
    targets: List[Dict[str, Any]]
    targets_hit: int
    tracking: Dict[str, float]
    pnl: Dict[str, float]
    partial_exits: List[Dict[str, Any]]
    last_update: str


class SessionUpdateResponse(BaseModel):
    """Session update response."""
    session_id: str
    status: str
    phase: str
    current_price: float
    bars_in_trade: int
    current_stop: float
    guarding_level: Optional[float]
    stop_moved: bool
    exit_signal: bool
    exit_reason: Optional[str]
    exit_percentage: float
    target_hit: bool
    unrealized_pnl: float
    unrealized_pnl_pct: float
    alerts: List[str]


class ShotResponse(BaseModel):
    """Shot entry response."""
    id: str
    shot_number: int
    entry_price: float
    size: float
    risk_amount: float
    stop_price: float
    session_status: str
    total_size: float
    average_entry: float
    risk_remaining: float


class ExitResponse(BaseModel):
    """Exit execution response."""
    price: float
    size: float
    percentage: float
    reason: str
    pnl: float
    session_status: str
    remaining_size: float
    realized_pnl: float


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/create", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    """
    Create a new trading session.
    
    Creates a session with:
    - Multi-shot entry capability (default 3 shots)
    - Risk budget tracking (default 2% total cap)
    - Target levels for partial exits
    - Structural stop configuration
    - Auto-subscribes to live price feed
    - Optionally takes first shot if entry_price provided
    """
    manager = get_manager()
    feed = get_feed()
    
    # Accept either structural_support or structural_level
    structural = request.structural_support or request.structural_level
    if not structural:
        raise HTTPException(status_code=400, detail="structural_support or structural_level is required")
    
    # Generate default targets if none provided
    targets = request.targets
    if not targets and request.entry_price:
        entry = request.entry_price
        if request.direction == "long":
            targets = [
                {"price": entry * 1.03, "exit_percentage": 33, "reason": "Target 1 (3%)"},
                {"price": entry * 1.06, "exit_percentage": 33, "reason": "Target 2 (6%)"},
                {"price": entry * 1.10, "exit_percentage": 34, "reason": "Target 3 (10%)"},
            ]
        else:
            targets = [
                {"price": entry * 0.97, "exit_percentage": 33, "reason": "Target 1 (3%)"},
                {"price": entry * 0.94, "exit_percentage": 33, "reason": "Target 2 (6%)"},
                {"price": entry * 0.90, "exit_percentage": 34, "reason": "Target 3 (10%)"},
            ]
    
    session = manager.create_session(
        symbol=request.symbol,
        direction=request.direction,
        timeframe=request.timeframe,
        account_balance=request.account_balance,
        structural_support=structural,
        targets=targets,
        risk_cap_pct=request.risk_cap_pct,
        max_shots=request.max_shots,
        timeout_hours=request.timeout_hours,
    )
    
    # Auto-subscribe to live feed for this symbol
    if feed:
        try:
            await feed.subscribe(request.symbol, timeframes=[request.timeframe])
        except Exception as e:
            logger.warning(f"Could not subscribe to feed: {e}")
    
    # Take first shot if entry price provided
    if request.entry_price:
        # Estimate ATR as 2% of entry price if not provided
        est_atr = request.entry_price * 0.02
        manager.take_shot(
            session_id=session.id,
            entry_price=request.entry_price,
            current_atr=est_atr,
        )
        # Refresh session state
        session = manager.get_session(session.id)
    
    return SessionResponse(**session.to_dict())


@router.post("/{session_id}/shot", response_model=ShotResponse)
async def take_shot(session_id: str, request: TakeShotRequest):
    """
    Take a shot (entry) in the session.
    
    Multi-shot allocation:
    - Shot 1: 50% of risk budget
    - Shot 2: 30% of risk budget
    - Shot 3: 20% of risk budget
    
    Position size calculated as: risk_amount / (entry - stop)
    """
    manager = get_manager()
    
    # Estimate ATR if not provided (2% of entry price)
    atr = request.current_atr or (request.entry_price * 0.02)
    
    entry = manager.take_shot(
        session_id=session_id,
        entry_price=request.entry_price,
        current_atr=atr,
        stop_override=request.stop_override,
    )
    
    if not entry:
        raise HTTPException(status_code=400, detail="Could not take shot - check session status")
    
    session = manager.get_session(session_id)
    
    return ShotResponse(
        id=entry.id,
        shot_number=entry.shot_number,
        entry_price=entry.entry_price,
        size=entry.size,
        risk_amount=entry.risk_amount,
        stop_price=entry.stop_price,
        session_status=session.status.value,
        total_size=session.total_size,
        average_entry=session.average_entry,
        risk_remaining=session.risk_remaining,
    )


@router.post("/{session_id}/update", response_model=SessionUpdateResponse)
async def update_session(session_id: str, request: UpdateSessionRequest):
    """
    Update session with new bar data.
    
    Call this on each new bar to:
    - Track high/low and P&L
    - Transition from Phase 1 to Phase 2 (bar 10+)
    - Update guarding line
    - Check for exit signals
    
    Exit signals checked (priority order):
    1. Opposite MCF signal
    2. Guarding line broken
    3. Structural support broken
    4. Target hit
    5. Momentum exhaustion
    6. Volume climax
    """
    manager = get_manager()
    
    update = manager.update_session(
        session_id=session_id,
        current_price=request.current_price,
        current_bar=request.current_bar,
        recent_lows=request.recent_lows,
        recent_highs=request.recent_highs,
        opposing_signal=request.opposing_signal,
        momentum_exhaustion=request.momentum_exhaustion,
        volume_climax=request.volume_climax,
    )
    
    return SessionUpdateResponse(
        session_id=update.session_id,
        status=update.status.value,
        phase=update.phase.value,
        current_price=update.current_price,
        bars_in_trade=update.bars_in_trade,
        current_stop=update.current_stop,
        guarding_level=update.guarding_level,
        stop_moved=update.stop_moved,
        exit_signal=update.exit_signal,
        exit_reason=update.exit_reason.value if update.exit_reason else None,
        exit_percentage=update.exit_percentage,
        target_hit=update.target_hit,
        unrealized_pnl=update.unrealized_pnl,
        unrealized_pnl_pct=update.unrealized_pnl_pct,
        alerts=update.alerts,
    )


@router.post("/{session_id}/exit", response_model=ExitResponse)
async def execute_exit(session_id: str, request: ExecuteExitRequest):
    """
    Execute an exit (full or partial).
    
    Exit reasons:
    - target_hit: Target level reached
    - guarding_line_broken: Guarding line breached
    - structural_support_broken: Structure invalidated
    - opposite_mcf_signal: Opposing signal detected
    - momentum_exhaustion: Momentum weakening
    - volume_climax: Volume spike
    - safety_net_5pct: Max loss hit
    - manual_exit: User-initiated
    """
    manager = get_manager()
    
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Use exit_reason or reason alias
    reason_str = request.exit_reason or request.reason or "manual_exit"
    try:
        reason = ExitReason(reason_str)
    except ValueError:
        reason = ExitReason.MANUAL
    
    # Use provided exit_price or current price
    exit_price = request.exit_price or session.current_price
    if not exit_price or exit_price <= 0:
        # Try to get live price
        exit_price = session.average_entry  # Fallback to entry
    
    result = manager.execute_exit(
        session_id=session_id,
        exit_price=exit_price,
        exit_reason=reason,
        exit_percentage=request.exit_percentage,
    )
    
    if not result:
        raise HTTPException(status_code=400, detail="Could not execute exit")
    
    session = manager.get_session(session_id)
    
    return ExitResponse(
        price=result.price,
        size=result.size,
        percentage=result.percentage,
        reason=result.reason,
        pnl=result.pnl,
        session_status=session.status.value,
        remaining_size=session.remaining_size,
        realized_pnl=session.realized_pnl,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get session state by ID."""
    manager = get_manager()
    
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionResponse(**session.to_dict())


@router.get("/{session_id}/summary")
async def get_session_summary(session_id: str):
    """Get session performance summary."""
    manager = get_manager()
    
    summary = manager.get_session_summary(session_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return summary


@router.get("/", response_model=List[SessionResponse])
async def list_sessions(symbol: str = None, active_only: bool = True):
    """List sessions, optionally filtered by symbol."""
    manager = get_manager()
    
    if active_only:
        sessions = manager.get_active_sessions(symbol)
    else:
        sessions = list(manager._sessions.values())
        if symbol:
            sessions = [s for s in sessions if s.symbol == symbol]
    
    return [SessionResponse(**s.to_dict()) for s in sessions]


@router.get("/list")
async def list_sessions_alt(symbol: str = None, active_only: bool = True):
    """Alternative list endpoint for UI compatibility."""
    manager = get_manager()
    
    if active_only:
        sessions = manager.get_active_sessions(symbol)
    else:
        sessions = list(manager._sessions.values())
        if symbol:
            sessions = [s for s in sessions if s.symbol == symbol]
    
    return {"sessions": [s.to_dict() for s in sessions]}


@router.get("/{session_id}/state")
async def get_session_state(session_id: str):
    """Get full session state for UI updates."""
    manager = get_manager()
    
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    state = session.to_dict()
    
    # Add UI-friendly fields
    state['entry_price'] = session.average_entry
    state['position_size'] = session.total_size
    state['risk_amount'] = session.risk_used
    state['total_risk_budget'] = session.account_balance * (session.total_risk_cap_pct / 100)
    state['bars_in_trade'] = session.bars_in_trade
    state['avg_entry'] = session.average_entry
    state['total_size'] = session.total_size
    state['unrealized_pnl'] = session.unrealized_pnl
    state['unrealized_pnl_pct'] = session.unrealized_pnl_pct
    state['realized_pnl'] = session.realized_pnl
    state['current_price'] = session.current_price
    state['guarding_line'] = session.guarding_level
    
    return state


@router.delete("/{session_id}")
async def close_session(session_id: str):
    """Close a session (does not exit position)."""
    manager = get_manager()
    
    success = manager.close_session(session_id, reason="api_close")
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"status": "closed", "session_id": session_id}


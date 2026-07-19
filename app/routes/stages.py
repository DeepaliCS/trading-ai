from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from app.database import get_db

router = APIRouter(prefix="/stages", tags=["stages"])

class StageConfig(BaseModel):
    stage_number: int
    us500_lots: float
    gold_lots: float
    daily_loss_limit: float
    profit_target: float
    accumulated_target: float

class ProgressUpdate(BaseModel):
    account_id: int
    current_stage: int
    starting_balance: float
    tracking_start_date: str
    stages: list[StageConfig]

@router.post("/confirm")
def confirm_stages(payload: ProgressUpdate, db: Session = Depends(get_db)):
    """Save confirmed growth plan stages to the dashboard DB."""
    for stage in payload.stages:
        db.execute(text("""
            INSERT INTO dashboard_tradingstage
                (stage_number, us500_lots, gold_lots, daily_loss_limit, profit_target, accumulated_target)
            VALUES
                (:stage_number, :us500_lots, :gold_lots, :daily_loss_limit, :profit_target, :accumulated_target)
            ON CONFLICT (stage_number) DO UPDATE SET
                us500_lots = EXCLUDED.us500_lots,
                gold_lots = EXCLUDED.gold_lots,
                daily_loss_limit = EXCLUDED.daily_loss_limit,
                profit_target = EXCLUDED.profit_target,
                accumulated_target = EXCLUDED.accumulated_target
        """), stage.model_dump())

    db.execute(text("""
        INSERT INTO dashboard_tradingprogress
            (account_id, current_stage, starting_balance, tracking_start_date, accumulated_profit)
        VALUES (:account_id, :current_stage, :starting_balance, :tracking_start_date, 0)
        ON CONFLICT (account_id) DO UPDATE SET
            current_stage = EXCLUDED.current_stage,
            starting_balance = EXCLUDED.starting_balance,
            tracking_start_date = EXCLUDED.tracking_start_date
    """), {
        "account_id": payload.account_id,
        "current_stage": payload.current_stage,
        "starting_balance": payload.starting_balance,
        "tracking_start_date": payload.tracking_start_date,
    })
    db.commit()
    return {"status": "ok", "stages_saved": len(payload.stages)}

@router.get("/get/{account_id}")
def get_stages(account_id: int, db: Session = Depends(get_db)):
    """Get all stages and current progress for an account."""
    stages = db.execute(text("""
        SELECT * FROM dashboard_tradingstage ORDER BY stage_number
    """)).fetchall()

    progress = db.execute(text("""
        SELECT * FROM dashboard_tradingprogress WHERE account_id = :account_id
    """), {"account_id": account_id}).fetchone()

    return {
        "stages": [dict(s._mapping) for s in stages],
        "progress": dict(progress._mapping) if progress else None,
    }

@router.post("/embed/{account_id}")
def embed_account_trades(account_id: int, db: Session = Depends(get_db)):
    """Embed all trades for an account into pgvector for RAG."""
    from app.services.embeddings import embed_trades
    from app.database import init_pgvector
    init_pgvector(db)
    count = embed_trades(db=db, account_id=account_id)
    return {"status": "ok", "trades_embedded": count}

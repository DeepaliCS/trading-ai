from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import json
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
    for stage in payload.stages:
        db.execute(text(
            "INSERT INTO dashboard_tradingstage "
            "(stage_number, us500_lots, gold_lots, daily_loss_limit, profit_target, accumulated_target) "
            "VALUES (:stage_number, :us500_lots, :gold_lots, :daily_loss_limit, :profit_target, :accumulated_target) "
            "ON CONFLICT (stage_number) DO UPDATE SET "
            "us500_lots = EXCLUDED.us500_lots, gold_lots = EXCLUDED.gold_lots, "
            "daily_loss_limit = EXCLUDED.daily_loss_limit, profit_target = EXCLUDED.profit_target, "
            "accumulated_target = EXCLUDED.accumulated_target"
        ), stage.model_dump())

    db.execute(text(
        "INSERT INTO dashboard_tradingprogress "
        "(account_id, current_stage, starting_balance, tracking_start_date, accumulated_profit, started_at, updated_at) "
        "VALUES (:account_id, :current_stage, :starting_balance, :tracking_start_date, 0, NOW(), NOW()) "
        "ON CONFLICT (account_id) DO UPDATE SET "
        "current_stage = EXCLUDED.current_stage, starting_balance = EXCLUDED.starting_balance, "
        "tracking_start_date = EXCLUDED.tracking_start_date, updated_at = NOW()"
    ), {
        "account_id": payload.account_id,
        "current_stage": payload.current_stage,
        "starting_balance": payload.starting_balance,
        "tracking_start_date": payload.tracking_start_date,
    })

    last_version = db.execute(text(
        "SELECT COALESCE(MAX(version), 0) FROM dashboard_growthplansnapshot WHERE account_id = :aid"
    ), {"aid": payload.account_id}).scalar()

    db.execute(text(
        "INSERT INTO dashboard_growthplansnapshot "
        "(account_id, version, label, stages_json, current_stage, starting_balance, tracking_start_date, created_at) "
        "VALUES (:account_id, :version, :label, CAST(:stages_json AS jsonb), :current_stage, :starting_balance, :tracking_start_date, NOW())"
    ), {
        "account_id": payload.account_id,
        "version": last_version + 1,
        "label": "Plan v" + str(last_version + 1),
        "stages_json": json.dumps([s.model_dump() for s in payload.stages]),
        "current_stage": payload.current_stage,
        "starting_balance": payload.starting_balance,
        "tracking_start_date": payload.tracking_start_date,
    })

    db.commit()
    return {"status": "ok", "stages_saved": len(payload.stages), "snapshot_version": last_version + 1}

@router.get("/get/{account_id}")
def get_stages(account_id: int, db: Session = Depends(get_db)):
    stages = db.execute(text("SELECT * FROM dashboard_tradingstage ORDER BY stage_number")).fetchall()
    progress = db.execute(text("SELECT * FROM dashboard_tradingprogress WHERE account_id = :aid"), {"aid": account_id}).fetchone()
    snapshots = db.execute(text(
        "SELECT id, version, label, created_at FROM dashboard_growthplansnapshot WHERE account_id = :aid ORDER BY version DESC"
    ), {"aid": account_id}).fetchall()
    return {
        "stages": [dict(s._mapping) for s in stages],
        "progress": dict(progress._mapping) if progress else None,
        "snapshots": [dict(s._mapping) for s in snapshots],
    }

@router.get("/snapshots/{account_id}")
def get_snapshots(account_id: int, db: Session = Depends(get_db)):
    snapshots = db.execute(text(
        "SELECT * FROM dashboard_growthplansnapshot WHERE account_id = :aid ORDER BY version DESC"
    ), {"aid": account_id}).fetchall()
    return {"snapshots": [dict(s._mapping) for s in snapshots]}

@router.post("/embed/{account_id}")
def embed_account_trades(account_id: int, db: Session = Depends(get_db)):
    from app.services.embeddings import embed_trades
    from app.database import init_pgvector
    init_pgvector(db)
    count = embed_trades(db=db, account_id=account_id)
    return {"status": "ok", "trades_embedded": count}

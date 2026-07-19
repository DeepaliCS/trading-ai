from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from app.database import get_db
from app.services.rag import query_trades, growth_plan_chat

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    account_id: int
    message: str
    mode: str = "auto"  # "auto", "trade_analysis", "growth_plan"
    history: list[ChatMessage] = []

class ChatResponse(BaseModel):
    answer: str
    mode_used: str
    sources: list[dict] = []

def detect_mode(message: str) -> str:
    growth_keywords = ["stage", "growth", "plan", "lot size", "daily loss", "progress", "target", "next stage", "progression"]
    if any(kw in message.lower() for kw in growth_keywords):
        return "growth_plan"
    return "trade_analysis"

@router.post("/ask", response_model=ChatResponse)
def ask(request: ChatRequest, db: Session = Depends(get_db)):
    mode = request.mode if request.mode != "auto" else detect_mode(request.message)

    if mode == "growth_plan":
        # Get account context
        progress = db.execute(text("""
            SELECT current_stage, accumulated_profit, starting_balance, tracking_start_date
            FROM dashboard_tradingprogress
            WHERE account_id = :account_id
        """), {"account_id": request.account_id}).fetchone()

        trade_count = db.execute(text("""
            SELECT COUNT(*) FROM dashboard_accounttrade WHERE account_id = :account_id
        """), {"account_id": request.account_id}).scalar()

        account_context = {
            "current_stage": progress.current_stage if progress else None,
            "accumulated_profit": float(progress.accumulated_profit) if progress else 0,
            "starting_balance": float(progress.starting_balance) if progress else 2000,
            "tracking_start_date": str(progress.tracking_start_date) if progress else None,
            "trade_count": trade_count,
        }

        answer = growth_plan_chat(
            messages_history=[m.model_dump() for m in request.history],
            user_message=request.message,
            account_context=account_context,
        )
        return ChatResponse(answer=answer, mode_used="growth_plan")

    else:
        result = query_trades(db=db, account_id=request.account_id, question=request.message)
        return ChatResponse(
            answer=result["answer"],
            mode_used="trade_analysis",
            sources=result.get("sources", []),
        )

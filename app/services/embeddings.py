import os
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from sqlalchemy import text
import json

model = SentenceTransformer("all-MiniLM-L6-v2")

def embed_text(txt: str) -> list:
    return model.encode(txt).tolist()

def trade_to_text(trade: dict) -> str:
    exec_time = trade["execution_time"]
    date_str = exec_time.strftime("%Y-%m-%d") if hasattr(exec_time, "strftime") else str(exec_time)[:10]
    net = float(trade["profit"]) - abs(float(trade["commission"] or 0)) - abs(float(trade["swap"] or 0))
    direction = trade["direction"]
    symbol = trade["symbol_name"]
    volume = trade["volume"]
    return f"{direction} {symbol} profit={round(net,2)} date={date_str} volume={volume}"

def embed_trades(db: Session, account_id: int) -> int:
    rows = db.execute(text("""
        SELECT id, symbol_name, direction, profit, commission, swap,
               volume, execution_time, entry_time, execution_price
        FROM dashboard_accounttrade
        WHERE account_id = :account_id
        ORDER BY execution_time DESC
    """), {"account_id": account_id}).fetchall()

    count = 0
    for row in rows:
        trade = dict(row._mapping)
        summary = trade_to_text(trade)
        embedding = embed_text(summary)
        emb_str = str(embedding)
        net = float(trade["profit"]) - abs(float(trade["commission"] or 0)) - abs(float(trade["swap"] or 0))
        meta = json.dumps({"trade_id": trade["id"], "symbol": trade["symbol_name"], "direction": trade["direction"], "net_profit": round(net,2)})
        sql = "INSERT INTO trade_embeddings (account_id, trade_summary, embedding, metadata) VALUES (:account_id, :summary, '" + emb_str + "'::vector, :metadata) ON CONFLICT DO NOTHING"
        db.execute(text(sql), {"account_id": account_id, "summary": summary, "metadata": meta})
        count += 1

    db.commit()
    return count

def similarity_search(db: Session, query: str, account_id: int, limit: int = 5) -> list:
    query_embedding = embed_text(query)
    emb_str = str(query_embedding)
    sql = "SELECT trade_summary, metadata, 1 - (embedding <=> '" + emb_str + "'::vector) AS similarity FROM trade_embeddings WHERE account_id = :account_id ORDER BY embedding <=> '" + emb_str + "'::vector LIMIT :limit"
    results = db.execute(text(sql), {"account_id": account_id, "limit": limit}).fetchall()
    return [dict(r._mapping) for r in results]

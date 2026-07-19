import os
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from sqlalchemy import text

model = SentenceTransformer("all-MiniLM-L6-v2")

def embed_text(text: str) -> list[float]:
    return model.encode(text).tolist()

def trade_to_text(trade: dict) -> str:
    return (
        f"{trade['direction']} {trade['symbol_name']} "
        f"profit={trade['net_profit']} "
        f"date={trade['execution_time'].strftime('%Y-%m-%d') if hasattr(trade['execution_time'], 'strftime') else trade['execution_time']} "
        f"volume={trade['volume']}"
    )

def embed_trades(db: Session, account_id: int):
    """Embed all trades for an account into pgvector."""
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
        net_profit = float(trade["profit"]) - abs(float(trade["commission"] or 0)) - abs(float(trade["swap"] or 0))
        trade["net_profit"] = round(net_profit, 2)
        summary = trade_to_text(trade)
        embedding = embed_text(summary)

        db.execute(text("""
            INSERT INTO trade_embeddings (account_id, trade_summary, embedding, metadata)
            VALUES (:account_id, :summary, :embedding, :metadata)
            ON CONFLICT DO NOTHING
        """), {
            "account_id": account_id,
            "summary": summary,
            "embedding": str(embedding),
            "metadata": f'{{"trade_id": {trade["id"]}, "symbol": "{trade["symbol_name"]}", "direction": "{trade["direction"]}", "net_profit": {trade["net_profit"]}}}',
        })
        count += 1

    db.commit()
    return count

def similarity_search(db: Session, query: str, account_id: int, limit: int = 5) -> list[dict]:
    """Find most relevant trades for a query."""
    query_embedding = embed_text(query)
    results = db.execute(text("""
        SELECT trade_summary, metadata,
               1 - (embedding <=> :embedding::vector) AS similarity
        FROM trade_embeddings
        WHERE account_id = :account_id
        ORDER BY embedding <=> :embedding::vector
        LIMIT :limit
    """), {
        "embedding": str(query_embedding),
        "account_id": account_id,
        "limit": limit,
    }).fetchall()
    return [dict(r._mapping) for r in results]

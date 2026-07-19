import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/trading_dashboard")

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_pgvector(db):
    """Enable pgvector extension if not already enabled."""
    db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS trade_embeddings (
            id SERIAL PRIMARY KEY,
            account_id BIGINT NOT NULL,
            trade_summary TEXT NOT NULL,
            embedding vector(384),
            metadata JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS trade_embeddings_idx 
        ON trade_embeddings USING ivfflat (embedding vector_cosine_ops)
    """))
    db.commit()

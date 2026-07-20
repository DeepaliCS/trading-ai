# trading-ai

AI-powered trade analysis and growth plan chat service for the Trading Dashboard.

## What it does

trading-ai is a FastAPI microservice that sits alongside the trading dashboard and provides two main features:

**1. Trade Analysis Chat**
Ask natural language questions about your trading performance and get answers backed by your actual trade data pulled directly from the database.

Examples:
- "What is my win rate on US500 vs gold?"
- "Show me my best and worst trading days"
- "Give me a full breakdown of my performance by symbol"
- "How do my buys compare to my sells?"

**2. Growth Plan Chat**
An interactive chat to help you build and refine a structured stage-based trading progression framework. Define lot sizes, daily loss limits, and profit targets for each stage of your trading journey.

## How it works

### Trade Analysis
Rather than using pure RAG (which only retrieves a small sample of trades), the service queries the PostgreSQL database directly for aggregated statistics across all trades. These stats are then passed to a Groq LLM (llama-3.1-8b-instant) which answers your question in natural language with proper markdown formatting.

This means answers are always accurate and based on your complete trade history, not a small sample.

### Growth Plan
Uses a larger Groq model (llama-3.3-70b-versatile) with your account context (current stage, accumulated profit, starting balance) to have a multi-turn conversation about building your trading progression plan. Once confirmed, the plan is saved to the dashboard database and reflected in the PnL calendar stage tracker.

### RAG (for future use)
Trade embeddings are stored in pgvector for semantic similarity search. This is used for pattern-based questions and will be expanded for strategy refinement features such as finding trades similar to your best days or identifying patterns in losing streaks.

## Architecture

```
trading-dashboard (port 8000)
        |
        | HTTP calls
        v
trading-ai (port 8002)
        |
        |--- PostgreSQL (shared DB with dashboard)
        |--- pgvector (trade embeddings)
        |--- Groq API (LLM)
```

## Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | /api/v1/chat/ask | Main chat endpoint — trade analysis or growth plan |
| GET | /api/v1/stages/get/{account_id} | Get stages and progress for an account |
| POST | /api/v1/stages/confirm | Save confirmed growth plan stages to DB |
| POST | /api/v1/stages/embed/{account_id} | Embed all trades into pgvector for RAG |
| GET | /docs | Interactive API docs (Swagger UI) |
| GET | /health | Health check |

### Chat request format

```json
{
  "account_id": 42310075,
  "message": "What is my win rate on US500?",
  "mode": "trade_analysis",
  "history": []
}
```

Mode options:
- `trade_analysis` — queries DB stats and answers with LLM
- `growth_plan` — multi-turn growth plan chat with account context
- `auto` — detects intent from the message

## Setup

### Prerequisites
- Docker and docker-compose
- trading-dashboard running with PostgreSQL
- pgvector extension enabled on PostgreSQL
- Groq API key (free at console.groq.com)

### Environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```
DATABASE_URL=postgresql://postgres:postgres@db:5432/trading_dashboard
GROQ_API_KEY=your_groq_api_key_here
```

### Running with docker-compose

This service is part of the unified docker-compose in the upwork-projects root:

```bash
cd ~/projects/upwork-projects
./start-trading.sh
```

Or start just this service:

```bash
docker-compose up -d trading-ai
```

### First time setup

After starting the service, embed your trades into pgvector:

```bash
curl -X POST http://localhost:8002/api/v1/stages/embed/{your_account_id}
```

This only needs to be done once, or after a large sync of new trades.

## Tech stack

- FastAPI
- SQLAlchemy + psycopg2 (PostgreSQL)
- pgvector (semantic search)
- sentence-transformers (all-MiniLM-L6-v2 for embeddings)
- LangChain + Groq (llama-3.1-8b-instant / llama-3.3-70b-versatile)

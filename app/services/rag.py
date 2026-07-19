from sqlalchemy.orm import Session
from sqlalchemy import text
from langchain_core.messages import HumanMessage, SystemMessage
from app.services.embeddings import similarity_search
from app.services.llm import get_fast_llm, get_capable_llm

TRADE_SYSTEM_PROMPT = """You are an expert trading coach analysing a trader's actual trade history.
You answer questions about their trading performance based on their real trade data.
Be specific, reference actual trades, and give actionable insights.
If the data doesn't contain enough to answer, say so clearly.
Never make up trades or outcomes not in the provided data."""

GROWTH_PLAN_SYSTEM_PROMPT = """You are an expert trading coach helping a trader build a structured growth plan.
You help them define trading stages with lot sizes, daily loss limits, and profit targets.
Be practical, specific, and motivating. Ask clarifying questions if needed.
When the trader is happy with their plan, summarise it clearly in a structured format they can confirm."""

def query_trades(db: Session, account_id: int, question: str, num_results: int = 8) -> dict:
    """RAG pipeline over actual trade data."""
    relevant = similarity_search(db=db, query=question, account_id=account_id, limit=num_results)

    if not relevant:
        return {
            "answer": "No trade data found. Please sync your trades first.",
            "sources": [],
            "model_used": "none",
        }

    context = "\n---\n".join([
        f"Trade: {r['trade_summary']} (similarity: {round(float(r['similarity']), 3)})"
        for r in relevant
    ])

    llm = get_fast_llm()
    messages = [
        SystemMessage(content=TRADE_SYSTEM_PROMPT),
        HumanMessage(content=f"""
Here are the most relevant trades from this trader's history:

{context}

Question: {question}

Provide a specific, actionable answer based only on the trade data above.
"""),
    ]
    response = llm.invoke(messages)
    return {
        "answer": response.content,
        "sources": relevant,
        "model_used": "llama-3.1-8b-instant",
    }

def growth_plan_chat(messages_history: list, user_message: str, account_context: dict) -> str:
    """Chat for building growth plan — uses Groq LLM."""
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
    llm = get_capable_llm()

    system_content = f"""{GROWTH_PLAN_SYSTEM_PROMPT}

Trader context:
- Starting balance: £{account_context.get("starting_balance", "unknown")}
- Tracking since: {account_context.get("tracking_start_date", "unknown")}
- Current stage: {account_context.get("current_stage", "not set")}
- Accumulated profit: £{account_context.get("accumulated_profit", 0)}
- Total trades: {account_context.get("trade_count", 0)}
"""

    messages = [SystemMessage(content=system_content)]
    for m in messages_history:
        if m["role"] == "user":
            messages.append(HumanMessage(content=m["content"]))
        elif m["role"] == "assistant":
            messages.append(AIMessage(content=m["content"]))
    messages.append(HumanMessage(content=user_message))

    response = llm.invoke(messages)
    return response.content

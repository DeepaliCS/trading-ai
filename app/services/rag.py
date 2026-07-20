from sqlalchemy.orm import Session
from sqlalchemy import text
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from app.services.embeddings import similarity_search
from app.services.llm import get_fast_llm, get_capable_llm

TRADE_SYSTEM_PROMPT = ('You are an expert trading coach analysing actual trade history. '
    'Answer based only on the exact statistics provided. Be concise and specific. '
    'Format tables in proper markdown. Never make up data.')

GROWTH_PLAN_SYSTEM_PROMPT = ('You are an expert trading coach helping a trader '
    'build a structured growth plan with stages, lot sizes, daily loss limits and profit targets.')

def get_stats_from_db(db, account_id, question):
    stats = db.execute(text('SELECT COUNT(*) as total_trades, SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins, SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses, ROUND(SUM(profit - ABS(commission) - ABS(swap))::numeric, 2) as net_profit, ROUND(AVG(profit - ABS(commission) - ABS(swap))::numeric, 2) as avg_profit, ROUND(MAX(profit)::numeric, 2) as best_trade, ROUND(MIN(profit)::numeric, 2) as worst_trade FROM dashboard_accounttrade WHERE account_id = :aid'), {'aid': account_id}).fetchone()
    symbol_stats = db.execute(text('SELECT symbol_name, COUNT(*) as trades, SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins, ROUND(SUM(profit - ABS(commission) - ABS(swap))::numeric, 2) as net_profit, ROUND(100.0 * SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) / COUNT(*)::numeric, 1) as win_rate FROM dashboard_accounttrade WHERE account_id = :aid GROUP BY symbol_name ORDER BY trades DESC'), {'aid': account_id}).fetchall()
    dir_stats = db.execute(text('SELECT direction, COUNT(*) as trades, SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins, ROUND(SUM(profit - ABS(commission) - ABS(swap))::numeric, 2) as net_profit, ROUND(100.0 * SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) / COUNT(*)::numeric, 1) as win_rate FROM dashboard_accounttrade WHERE account_id = :aid GROUP BY direction'), {'aid': account_id}).fetchall()
    best_days = db.execute(text('SELECT DATE(execution_time) as day, COUNT(*) as trades, ROUND(SUM(profit - ABS(commission) - ABS(swap))::numeric, 2) as net_profit FROM dashboard_accounttrade WHERE account_id = :aid GROUP BY DATE(execution_time) ORDER BY net_profit DESC LIMIT 5'), {'aid': account_id}).fetchall()
    worst_days = db.execute(text('SELECT DATE(execution_time) as day, COUNT(*) as trades, ROUND(SUM(profit - ABS(commission) - ABS(swap))::numeric, 2) as net_profit FROM dashboard_accounttrade WHERE account_id = :aid GROUP BY DATE(execution_time) ORDER BY net_profit ASC LIMIT 5'), {'aid': account_id}).fetchall()
    total = stats.total_trades or 1
    win_rate = round(100 * stats.wins / total, 1)
    out = []
    out.append('TRADING STATISTICS:')
    out.append(f'Total trades: {stats.total_trades}')
    out.append(f'Wins: {stats.wins} | Losses: {stats.losses}')
    out.append(f'Overall win rate: {win_rate}%')
    out.append(f'Net profit: GBP {stats.net_profit}')
    out.append(f'Avg profit per trade: GBP {stats.avg_profit}')
    out.append(f'Best trade: GBP {stats.best_trade}')
    out.append(f'Worst trade: GBP {stats.worst_trade}')
    out.append('By Symbol:')
    for r in symbol_stats:
        out.append(f'  {r.symbol_name}: {r.trades} trades, {r.win_rate}% win rate, GBP {r.net_profit}')
    out.append('By Direction:')
    for r in dir_stats:
        out.append(f'  {r.direction}: {r.trades} trades, {r.win_rate}% win rate, GBP {r.net_profit}')
    out.append('Best Days:')
    for r in best_days:
        out.append(f'  {r.day}: {r.trades} trades, GBP {r.net_profit}')
    out.append('Worst Days:')
    for r in worst_days:
        out.append(f'  {r.day}: {r.trades} trades, GBP {r.net_profit}')
    return chr(10).join(out)

def query_trades(db, account_id, question, num_results=8):
    context = get_stats_from_db(db, account_id, question)
    prompt = context + chr(10) + chr(10) + 'Question: ' + question + chr(10) + chr(10) + 'Answer specifically based on the data above.'
    llm = get_fast_llm()
    messages = [SystemMessage(content=TRADE_SYSTEM_PROMPT), HumanMessage(content=prompt)]
    response = llm.invoke(messages)
    return {'answer': response.content, 'sources': [], 'model_used': 'llama-3.1-8b-instant'}

def growth_plan_chat(messages_history, user_message, account_context):
    llm = get_capable_llm()
    sys = GROWTH_PLAN_SYSTEM_PROMPT + chr(10) + 'Trader context:' + chr(10)
    sys += f'Starting balance: GBP {account_context.get("starting_balance", "unknown")}' + chr(10)
    sys += f'Current stage: {account_context.get("current_stage", "not set")}' + chr(10)
    sys += f'Accumulated profit: GBP {account_context.get("accumulated_profit", 0)}' + chr(10)
    sys += f'Total trades: {account_context.get("trade_count", 0)}' + chr(10)
    messages = [SystemMessage(content=sys)]
    for m in messages_history:
        if m['role'] == 'user':
            messages.append(HumanMessage(content=m['content']))
        elif m['role'] == 'assistant':
            messages.append(AIMessage(content=m['content']))
    messages.append(HumanMessage(content=user_message))
    response = llm.invoke(messages)
    return response.content

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(
    title="Trading AI",
    description="RAG-powered trade analysis and growth plan chat for the trading dashboard.",
    version="0.1.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routes.chat import router as chat_router
from app.routes.stages import router as stages_router

app.include_router(chat_router, prefix="/api/v1")
app.include_router(stages_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"service": "trading-ai", "version": "0.1.0", "status": "ok"}

@app.get("/health")
def health():
    return {"status": "ok"}

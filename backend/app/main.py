"""PandaNews API — FastAPI.

Fase 1: CRUD de blogs, configurações (keys mascaradas), teste de LLM,
dashboard com métricas/onboarding, notícias e logs. SQLite local criado
automaticamente no startup (init_db). CORS liberado para a UI local.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers import blogs, configuracoes, dashboard, llm, logs, noticias
from backend.core.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="PandaNews API", version="0.2.1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(blogs.router, prefix="/api/v1")
app.include_router(configuracoes.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(llm.router, prefix="/api/v1")
app.include_router(noticias.router, prefix="/api/v1")
app.include_router(logs.router, prefix="/api/v1")


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "service": "pandanews", "version": app.version}

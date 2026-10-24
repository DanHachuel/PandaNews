"""PandaNews API — FastAPI.

Fases 1, 3 e 5: CRUD de blogs, configurações (keys mascaradas), teste de LLM,
dashboard, notícias (com geração via pipeline), imagens, logs, automação com
scheduler ativo por blog. SQLite local criado automaticamente no startup.
CORS liberado para a UI local (localhost em qualquer porta).
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers import automacao, blogs, configuracoes, dashboard, imagens, llm, logs, noticias
from backend.core.database import SessionLocal, init_db
from backend.core.llm_router import get_config


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    from backend.core import scheduler

    db = SessionLocal()
    try:
        if get_config(db, "scheduler_ativo", "true") == "true":
            scheduler.iniciar()
            scheduler.recarregar()
    finally:
        db.close()
    yield
    scheduler.parar()


app = FastAPI(title="PandaNews API", version="0.3.0", lifespan=lifespan)

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
app.include_router(imagens.router, prefix="/api/v1")
app.include_router(automacao.router, prefix="/api/v1")
app.include_router(logs.router, prefix="/api/v1")


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "service": "pandanews", "version": app.version}


@app.get("/health")
def health_root() -> dict:
    """Alias na raiz para clientes que esperam /health (extensões, monitores)."""
    return {"status": "ok", "service": "pandanews", "version": app.version}

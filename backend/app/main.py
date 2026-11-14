"""PandaNews API — FastAPI.

Fases 1, 3 e 5: CRUD de blogs, configurações (keys mascaradas), teste de LLM,
dashboard, notícias (com geração via pipeline), imagens, logs, automação com
scheduler ativo por blog. SQLite local criado automaticamente no startup.
CORS liberado para a UI local (localhost em qualquer porta).
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers import auth, automacao, blogs, configuracoes, dashboard, imagens, legal, llm, logs, noticias, wordpress
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


app = FastAPI(title="PandaNews API", version="0.5.6", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")  # login é público

# Rotas de dados: exigem token JWT. A dependência vai no `dependencies` do
# `include_router` (a forma suportada pelo FastAPI) — aplica-se a TODAS as
# rotas do router, então nenhuma fica de fora por esquecimento.
from fastapi import Depends as _Depends  # noqa: E402

from backend.app.routers.auth import usuario_atual as _usuario_atual  # noqa: E402

_PROTEGIDOS = (
    blogs.router,
    configuracoes.router,
    dashboard.router,
    llm.router,
    noticias.router,
    imagens.router,
    automacao.router,
    logs.router,
    wordpress.router,
)
for _router in _PROTEGIDOS:
    app.include_router(_router, prefix="/api/v1", dependencies=[_Depends(_usuario_atual)])

app.include_router(legal.router)  # /legal/* na raiz (URLs de verificação)


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "service": "pandanews", "version": app.version}


@app.get("/health")
def health_root() -> dict:
    """Alias na raiz para clientes que esperam /health (extensões, monitores)."""
    return {"status": "ok", "service": "pandanews", "version": app.version}

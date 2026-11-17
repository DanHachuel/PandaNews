"""Dashboard (/api/v1/dashboard): métricas, onboarding e últimos erros."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.routers.auth import user_id_de, usuario_atual
from backend.core.database import Blog, Log, Noticia, Usuario, get_db
from backend.core.llm_router import get_config

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def estatisticas(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
) -> dict:
    uid = user_id_de(usuario)
    agora = datetime.now(timezone.utc)
    inicio_hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0)

    # Log não tem user_id: os erros são contados pelos blogs do utilizador.
    blogs_do_utilizador = select(Blog.id).where(Blog.user_id == uid)

    blogs_total = db.scalar(select(func.count(Blog.id)).where(Blog.user_id == uid)) or 0
    blogs_ativos = (
        db.scalar(select(func.count(Blog.id)).where(Blog.user_id == uid, Blog.status == "ativo")) or 0
    )
    noticias_total = db.scalar(select(func.count(Noticia.id)).where(Noticia.user_id == uid)) or 0
    noticias_hoje = (
        db.scalar(
            select(func.count(Noticia.id)).where(Noticia.user_id == uid, Noticia.created_at >= inicio_hoje)
        )
        or 0
    )
    noticias_pendentes = (
        db.scalar(select(func.count(Noticia.id)).where(Noticia.user_id == uid, Noticia.status == "rascunho")) or 0
    )
    erros_total = (
        db.scalar(select(func.count(Log.id)).where(Log.status == "erro", Log.blog_id.in_(blogs_do_utilizador))) or 0
    )

    geracao: list[dict] = []
    for offset in range(6, -1, -1):
        dia = (agora - timedelta(days=offset)).replace(hour=0, minute=0, second=0, microsecond=0)
        dia_fim = dia + timedelta(days=1)
        total = (
            db.scalar(
                select(func.count(Noticia.id)).where(
                    Noticia.user_id == uid, Noticia.created_at >= dia, Noticia.created_at < dia_fim
                )
            )
            or 0
        )
        geracao.append({"data": dia.date().isoformat(), "total": total})

    ultimos_erros = [
        {"id": e.id, "blog_id": e.blog_id, "etapa": e.etapa, "mensagem": e.mensagem, "created_at": e.created_at}
        for e in db.scalars(
            select(Log)
            .where(Log.status == "erro", Log.blog_id.in_(blogs_do_utilizador))
            .order_by(Log.created_at.desc())
            .limit(5)
        ).all()
    ]

    llm_configurado = bool(
        get_config(db, "nvidia_api_key", user_id=uid) or get_config(db, "google_api_key", user_id=uid)
    )
    onboarding = {
        "llm_configurado": llm_configurado,
        "tem_blog": blogs_total > 0,
        "tem_noticia": noticias_total > 0,
    }
    onboarding["concluidos"] = sum(1 for v in onboarding.values() if v)

    meta = int(get_config(db, "meta_diaria", "3", user_id=uid) or 3)
    faltam_meta = max(0, meta - noticias_hoje)

    return {
        "blogs_total": blogs_total,
        "blogs_ativos": blogs_ativos,
        "noticias_total": noticias_total,
        "noticias_hoje": noticias_hoje,
        "noticias_pendentes": noticias_pendentes,
        "erros_total": erros_total,
        "scheduler_ativo": get_config(db, "scheduler_ativo", "true", user_id=uid) == "true",
        "meta_diaria": meta,
        "faltam_meta": faltam_meta,
        "geracao_7dias": geracao,
        "ultimos_erros": ultimos_erros,
        "onboarding": onboarding,
    }
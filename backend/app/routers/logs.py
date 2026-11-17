"""Logs de execução (/api/v1/logs)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.routers.auth import user_id_de, usuario_atual
from backend.core.database import Blog, Log, Usuario, get_db

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("")
def listar_logs(
    blog_id: int | None = None,
    etapa: str | None = None,
    status: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
) -> list[dict]:
    uid = user_id_de(usuario)
    # Log não tem user_id: o dono vem do blog a que pertence. A subquery
    # garante que nenhum log de outro utilizador aparece (IDOR).
    blogs_do_utilizador = select(Blog.id).where(Blog.user_id == uid)
    query = select(Log).where(Log.blog_id.in_(blogs_do_utilizador)).order_by(Log.created_at.desc()).limit(min(limit, 1000))
    if blog_id is not None:
        query = query.where(Log.blog_id == blog_id)
    if etapa:
        query = query.where(Log.etapa == etapa)
    if status:
        query = query.where(Log.status == status)
    return [
        {
            "id": l.id,
            "blog_id": l.blog_id,
            "etapa": l.etapa,
            "status": l.status,
            "mensagem": l.mensagem,
            "created_at": l.created_at,
        }
        for l in db.scalars(query).all()
    ]
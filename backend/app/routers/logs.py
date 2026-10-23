"""Logs de execução (/api/v1/logs)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.database import Log, get_db

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("")
def listar_logs(
    blog_id: int | None = None,
    etapa: str | None = None,
    status: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[dict]:
    query = select(Log).order_by(Log.created_at.desc()).limit(min(limit, 1000))
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

"""Notícias (/api/v1/noticias): listagem, filtros e revisão humana."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.schemas import NoticiaPatch, STATUS_NOTICIA
from backend.core.database import Noticia, get_db

router = APIRouter(prefix="/noticias", tags=["noticias"])


@router.get("")
def listar_noticias(
    blog_id: int | None = None,
    status: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[dict]:
    query = select(Noticia).order_by(Noticia.created_at.desc()).limit(min(limit, 500))
    if blog_id is not None:
        query = query.where(Noticia.blog_id == blog_id)
    if status:
        query = query.where(Noticia.status == status)
    noticias = db.scalars(query).all()
    return [
        {
            "id": n.id,
            "blog_id": n.blog_id,
            "titulo": n.titulo,
            "corpo": n.corpo,
            "resumo": n.resumo,
            "imagem_url": n.imagem_url,
            "status": n.status,
            "llm_provider": n.llm_provider,
            "created_at": n.created_at,
        }
        for n in noticias
    ]


@router.patch("/{noticia_id}")
def atualizar_noticia(noticia_id: int, payload: NoticiaPatch, db: Session = Depends(get_db)) -> dict:
    noticia = db.get(Noticia, noticia_id)
    if noticia is None:
        raise HTTPException(status_code=404, detail="Notícia não encontrada")
    data = payload.model_dump(exclude_none=True)
    if "status" in data and data["status"] not in STATUS_NOTICIA:
        raise HTTPException(status_code=422, detail=f"Status inválido. Use: {', '.join(STATUS_NOTICIA)}")
    for key, value in data.items():
        setattr(noticia, key, value)
    db.commit()
    db.refresh(noticia)
    return {
        "id": noticia.id,
        "blog_id": noticia.blog_id,
        "titulo": noticia.titulo,
        "corpo": noticia.corpo,
        "resumo": noticia.resumo,
        "imagem_url": noticia.imagem_url,
        "status": noticia.status,
        "llm_provider": noticia.llm_provider,
        "created_at": noticia.created_at,
    }

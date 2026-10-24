"""Automação (/api/v1/automacao): estado do scheduler e execução imediata."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core import scheduler
from backend.core.database import Blog, get_db

router = APIRouter(prefix="/automacao", tags=["automacao"])


class BlogIdIn(BaseModel):
    blog_id: int


@router.get("/status")
def status(db: Session = Depends(get_db)) -> dict:
    jobs = {job["blog_id"]: job["proxima_execucao"] for job in scheduler.jobs()}
    blogs = db.scalars(select(Blog).where(Blog.status == "ativo")).all()
    return {
        "ativo": scheduler.esta_ativo(),
        "jobs": [
            {
                "blog_id": blog.id,
                "nome": blog.nome,
                "frequencia_horas": blog.frequencia_horas,
                "proxima_execucao": jobs.get(blog.id),
            }
            for blog in blogs
        ],
    }


@router.post("/executar")
def executar_agora(payload: BlogIdIn) -> dict:
    from backend.core import pipeline

    noticia = pipeline.gerar_noticia(payload.blog_id)
    if noticia is None:
        return {
            "ok": False,
            "detail": "Nenhuma notícia nova: sem itens nas fontes, todos já utilizados ou erro na geração — verifique os Logs.",
        }
    return {"ok": True, "noticia_id": noticia.id, "titulo": noticia.titulo}

"""Automação (/api/v1/automacao): estado do scheduler e execução imediata."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.routers.auth import user_id_de, usuario_atual
from backend.core import scheduler
from backend.core.database import Blog, Usuario, get_db

router = APIRouter(prefix="/automacao", tags=["automacao"])


class BlogIdIn(BaseModel):
    blog_id: int


@router.get("/status")
def status(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
) -> dict:
    uid = user_id_de(usuario)
    jobs = {job["blog_id"]: job["proxima_execucao"] for job in scheduler.jobs()}
    blogs = db.scalars(select(Blog).where(Blog.status == "ativo", Blog.user_id == uid)).all()
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
def executar_agora(
    payload: BlogIdIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
) -> dict:
    from backend.core import pipeline

    # o blog tem de ser do utilizador antes de disparar o pipeline
    blog = db.scalars(
        select(Blog).where(Blog.id == payload.blog_id, Blog.user_id == user_id_de(usuario))
    ).first()
    if blog is None:
        raise HTTPException(status_code=404, detail="Blog não encontrado")
    noticia = pipeline.gerar_noticia(payload.blog_id)
    if noticia is None:
        return {
            "ok": False,
            "detail": "Nenhuma notícia nova: sem itens nas fontes, todos já utilizados ou erro na geração — verifique os Logs.",
        }
    return {"ok": True, "noticia_id": noticia.id, "titulo": noticia.titulo}
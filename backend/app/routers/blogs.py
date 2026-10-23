"""CRUD de blogs (/api/v1/blogs)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.schemas import BlogIn, BlogPatch
from backend.core.database import Blog, Log, get_db

router = APIRouter(prefix="/blogs", tags=["blogs"])


def blog_to_dict(b: Blog) -> dict:
    return {
        "id": b.id,
        "nome": b.nome,
        "tema": b.tema,
        "regiao": b.regiao,
        "fontes_rss": json.loads(b.fontes_rss or "[]"),
        "estilo_editorial": b.estilo_editorial,
        "frequencia_horas": b.frequencia_horas,
        "status": b.status,
        "created_at": b.created_at,
    }


@router.get("")
def listar_blogs(db: Session = Depends(get_db)) -> list[dict]:
    blogs = db.scalars(select(Blog).order_by(Blog.created_at.desc())).all()
    return [blog_to_dict(b) for b in blogs]


@router.get("/{blog_id}")
def obter_blog(blog_id: int, db: Session = Depends(get_db)) -> dict:
    blog = db.get(Blog, blog_id)
    if blog is None:
        raise HTTPException(status_code=404, detail="Blog não encontrado")
    return blog_to_dict(blog)


@router.post("", status_code=201)
def criar_blog(payload: BlogIn, db: Session = Depends(get_db)) -> dict:
    blog = Blog(
        nome=payload.nome,
        tema=payload.tema,
        regiao=payload.regiao,
        fontes_rss=json.dumps([u.strip() for u in payload.fontes_rss if u.strip()]),
        estilo_editorial=payload.estilo_editorial,
        frequencia_horas=payload.frequencia_horas,
        status=payload.status,
    )
    db.add(blog)
    db.add(Log(etapa="blog", status="sucesso", mensagem=f"Blog criado: {payload.nome}"))
    db.commit()
    db.refresh(blog)
    return blog_to_dict(blog)


@router.patch("/{blog_id}")
def atualizar_blog(blog_id: int, payload: BlogPatch, db: Session = Depends(get_db)) -> dict:
    blog = db.get(Blog, blog_id)
    if blog is None:
        raise HTTPException(status_code=404, detail="Blog não encontrado")
    data = payload.model_dump(exclude_none=True)
    if "fontes_rss" in data:
        blog.fontes_rss = json.dumps([u.strip() for u in data.pop("fontes_rss") if u.strip()])
    for key, value in data.items():
        setattr(blog, key, value)
    db.commit()
    db.refresh(blog)
    return blog_to_dict(blog)


@router.delete("/{blog_id}", status_code=204)
def excluir_blog(blog_id: int, db: Session = Depends(get_db)) -> None:
    from backend.core.database import Noticia

    blog = db.get(Blog, blog_id)
    if blog is None:
        raise HTTPException(status_code=404, detail="Blog não encontrado")
    db.query(Noticia).filter(Noticia.blog_id == blog_id).delete()
    db.delete(blog)
    db.add(Log(etapa="blog", status="sucesso", mensagem=f"Blog excluído: {blog.nome}"))
    db.commit()

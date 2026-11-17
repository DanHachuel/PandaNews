"""CRUD de blogs (/api/v1/blogs)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.routers.auth import user_id_de, usuario_atual
from backend.app.schemas import BlogIn, BlogPatch
from backend.core.database import Blog, Log, Usuario, get_db

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
def listar_blogs(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
) -> list[dict]:
    uid = user_id_de(usuario)
    blogs = db.scalars(
        select(Blog).where(Blog.user_id == uid).order_by(Blog.created_at.desc())
    ).all()
    return [blog_to_dict(b) for b in blogs]


@router.get("/{blog_id}")
def obter_blog(
    blog_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
) -> dict:
    uid = user_id_de(usuario)
    blog = db.scalars(select(Blog).where(Blog.id == blog_id, Blog.user_id == uid)).first()
    if blog is None:
        raise HTTPException(status_code=404, detail="Blog não encontrado")
    return blog_to_dict(blog)


def _sync_scheduler() -> None:
    from backend.core import scheduler

    if scheduler.esta_ativo():
        scheduler.recarregar()


@router.post("", status_code=201)
def criar_blog(
    payload: BlogIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
) -> dict:
    uid = user_id_de(usuario)
    blog = Blog(
        user_id=uid,
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
    _sync_scheduler()
    return blog_to_dict(blog)


@router.patch("/{blog_id}")
def atualizar_blog(
    blog_id: int,
    payload: BlogPatch,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
) -> dict:
    uid = user_id_de(usuario)
    blog = db.scalars(select(Blog).where(Blog.id == blog_id, Blog.user_id == uid)).first()
    if blog is None:
        raise HTTPException(status_code=404, detail="Blog não encontrado")
    data = payload.model_dump(exclude_none=True)
    if "fontes_rss" in data:
        blog.fontes_rss = json.dumps([u.strip() for u in data.pop("fontes_rss") if u.strip()])
    for key, value in data.items():
        # user_id nunca vem do payload: muda de dono é privilégio do servidor
        if key != "user_id":
            setattr(blog, key, value)
    db.commit()
    db.refresh(blog)
    _sync_scheduler()
    return blog_to_dict(blog)


@router.delete("/{blog_id}", status_code=204)
def excluir_blog(
    blog_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
) -> None:
    from backend.core.database import Noticia

    uid = user_id_de(usuario)
    blog = db.scalars(select(Blog).where(Blog.id == blog_id, Blog.user_id == uid)).first()
    if blog is None:
        raise HTTPException(status_code=404, detail="Blog não encontrado")
    # apaga também em cadeia, mas SÓ do dono (nunca por blog_id solto)
    db.query(Noticia).filter(Noticia.blog_id == blog_id, Noticia.user_id == uid).delete()
    db.delete(blog)
    db.add(Log(etapa="blog", status="sucesso", mensagem=f"Blog excluído: {blog.nome}"))
    db.commit()
    _sync_scheduler()
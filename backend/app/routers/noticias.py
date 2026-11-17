"""Notícias (/api/v1/noticias): listagem, filtros e revisão humana."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.routers.auth import user_id_de, usuario_atual
from backend.app.schemas import NoticiaPatch, STATUS_NOTICIA
from backend.core.database import Blog, Log, Noticia, Usuario, get_db

router = APIRouter(prefix="/noticias", tags=["noticias"])


class GerarIn(BaseModel):
    blog_id: int


def _serializar(n: Noticia) -> dict:
    return {
        "id": n.id,
        "blog_id": n.blog_id,
        "titulo": n.titulo,
        "corpo": n.corpo,
        "resumo": n.resumo,
        "imagem_url": n.imagem_url,
        "status": n.status,
        "llm_provider": n.llm_provider,
        "wordpress_post_id": n.wordpress_post_id,
        "fonte_url": n.fonte_url,
        "fonte_titulo": n.fonte_titulo,
        "created_at": n.created_at,
    }


@router.post("/gerar", status_code=201)
def gerar_noticia(
    payload: GerarIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
) -> dict:
    from backend.core import pipeline

    # o blog tem de ser do utilizador: gerar noutro blog seria IDOR
    blog = db.scalars(
        select(Blog).where(Blog.id == payload.blog_id, Blog.user_id == user_id_de(usuario))
    ).first()
    if blog is None:
        raise HTTPException(status_code=404, detail="Blog não encontrado")
    noticia = pipeline.gerar_noticia(payload.blog_id)
    if noticia is None:
        raise HTTPException(
            status_code=409,
            detail="Nenhuma notícia nova: sem itens nas fontes, todos já utilizados ou erro na geração — verifique os Logs.",
        )
    return _serializar(noticia)


@router.post("/{noticia_id}/publicar")
def publicar_noticia(
    noticia_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
) -> dict:
    """Publica a notícia no WordPress configurado (imagem + categoria)."""
    from backend.core import wordpress_publisher

    uid = user_id_de(usuario)
    noticia = db.scalars(select(Noticia).where(Noticia.id == noticia_id, Noticia.user_id == uid)).first()
    if noticia is None:
        raise HTTPException(status_code=404, detail="Notícia não encontrada")
    if noticia.wordpress_post_id:
        raise HTTPException(status_code=400, detail="Já publicado no WordPress.")
    palavras = wordpress_publisher.contar_palavras(noticia.corpo)
    if palavras < wordpress_publisher.MINIMO_PALAVRAS_PUBLICACAO:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Texto com {palavras} palavras — mínimo de "
                f"{wordpress_publisher.MINIMO_PALAVRAS_PUBLICACAO} para publicar (diretriz AdSense). "
                "Regere a notícia ou edite o corpo antes de publicar."
            ),
        )
    try:
        resultado = wordpress_publisher.publish_to_wordpress(db, noticia, uid)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    noticia.status = "publicado"
    noticia.wordpress_post_id = resultado["post_id"]
    db.add(
        Log(
            blog_id=noticia.blog_id,
            etapa="publicacao",
            status="sucesso",
            mensagem=f"Publicado no WordPress (post {resultado['post_id']}): {resultado['link']}",
        )
    )
    db.commit()
    db.refresh(noticia)
    return {"ok": True, "post_id": resultado["post_id"], "link": resultado["link"], "noticia": _serializar(noticia)}


@router.post("/{noticia_id}/regenerar")
def regenerar_noticia(
    noticia_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
) -> dict:
    from backend.core import pipeline

    uid = user_id_de(usuario)
    dono = db.scalars(select(Noticia).where(Noticia.id == noticia_id, Noticia.user_id == uid)).first()
    if dono is None:
        raise HTTPException(status_code=404, detail="Notícia não encontrada")
    noticia = pipeline.regenerar_noticia(noticia_id)
    if noticia is None:
        raise HTTPException(status_code=404, detail="Notícia (ou blog/fonte) não encontrada")
    if not noticia.fonte_titulo and not noticia.fonte_url:
        raise HTTPException(status_code=422, detail="Notícia sem fonte associada — use Gerar notícia para criar uma nova")
    return _serializar(noticia)


@router.get("")
def listar_noticias(
    blog_id: int | None = None,
    status: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
) -> list[dict]:
    uid = user_id_de(usuario)
    query = select(Noticia).where(Noticia.user_id == uid).order_by(Noticia.created_at.desc()).limit(min(limit, 500))
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
def atualizar_noticia(
    noticia_id: int,
    payload: NoticiaPatch,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
) -> dict:
    uid = user_id_de(usuario)
    noticia = db.scalars(select(Noticia).where(Noticia.id == noticia_id, Noticia.user_id == uid)).first()
    if noticia is None:
        raise HTTPException(status_code=404, detail="Notícia não encontrada")
    data = payload.model_dump(exclude_none=True)
    if "status" in data and data["status"] not in STATUS_NOTICIA:
        raise HTTPException(status_code=422, detail=f"Status inválido. Use: {', '.join(STATUS_NOTICIA)}")
    for key, value in data.items():
        # user_id nunca vem do payload: muda de dono é privilégio do servidor
        if key != "user_id":
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
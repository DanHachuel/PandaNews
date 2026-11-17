"""Imagens (/api/v1/imagens): galeria, arquivo e geração manual."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.routers.auth import user_id_de, usuario_atual
from backend.core.config import IMAGES_DIR
from backend.core.database import Noticia, Usuario, get_db

router = APIRouter(prefix="/imagens", tags=["imagens"])


class PromptIn(BaseModel):
    prompt: str


@router.get("")
def listar_imagens(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
) -> list[dict]:
    uid = user_id_de(usuario)
    noticias = db.scalars(
        select(Noticia)
        .where(Noticia.user_id == uid, Noticia.imagem_url != "")
        .order_by(Noticia.created_at.desc())
        .limit(100)
    ).all()
    return [
        {"noticia_id": n.id, "url": n.imagem_url, "titulo": n.titulo, "created_at": n.created_at}
        for n in noticias
    ]


@router.get("/{nome}")
def servir_imagem(nome: str, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)) -> FileResponse:
    if "/" in nome or "\\" in nome or ".." in nome or not nome.endswith(".png"):
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido")
    # IDOR: `<id>.png` é a capa de uma notícia — só serve se for do dono.
    # `manual-*.png` não tem notícia associada (gerada a pedido do utilizador).
    if nome.split(".")[0].isdigit():
        dono = db.scalars(
            select(Noticia.user_id).where(Noticia.id == int(nome.split(".")[0]))
        ).first()
        if dono is None or dono != user_id_de(usuario):
            raise HTTPException(status_code=404, detail="Imagem não encontrada")
    caminho = IMAGES_DIR / nome
    if not caminho.exists():
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    return FileResponse(caminho, media_type="image/png")


@router.post("/gerar")
def gerar_imagem_manual(payload: PromptIn, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)) -> dict:
    from backend.core import image_gen

    try:
        # a chave do Gemini e o destino (disco ou Supabase Storage) são do dono
        url = image_gen.imagem_manual(db, payload.prompt.strip(), user_id_de(usuario))
        return {"ok": True, "url": url}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": str(exc)}
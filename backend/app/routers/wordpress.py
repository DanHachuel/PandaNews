"""WordPress (/api/v1/wordpress): teste de conexão e estado das credenciais."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.routers.auth import user_id_de, usuario_atual
from backend.core import wordpress_publisher
from backend.core.database import Usuario, get_db

router = APIRouter(prefix="/wordpress", tags=["wordpress"])


@router.get("/status")
def status(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
) -> dict:
    # credenciais são do utilizador (cada conta tem o seu próprio WordPress)
    return wordpress_publisher.credenciais_presentes(db, user_id_de(usuario))


@router.post("/testar")
def testar(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
) -> dict:
    uid = user_id_de(usuario)
    estado = wordpress_publisher.credenciais_presentes(db, uid)
    if not estado["configurado"]:
        return {"ok": False, "detail": "Credenciais não configuradas — informe URL, usuário e Senha de Aplicativo abaixo."}
    return {**wordpress_publisher.testar_conexao(db, uid), **estado}
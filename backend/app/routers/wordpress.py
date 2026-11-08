"""WordPress (/api/v1/wordpress): teste de conexão e estado das credenciais."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core import wordpress_publisher
from backend.core.database import get_db

router = APIRouter(prefix="/wordpress", tags=["wordpress"])


@router.get("/status")
def status(db: Session = Depends(get_db)) -> dict:
    return wordpress_publisher.credenciais_presentes(db)


@router.post("/testar")
def testar(db: Session = Depends(get_db)) -> dict:
    estado = wordpress_publisher.credenciais_presentes(db)
    if not estado["configurado"]:
        return {"ok": False, "detail": "Credenciais não configuradas — informe URL, usuário e Senha de Aplicativo abaixo."}
    return {**wordpress_publisher.testar_conexao(db), **estado}

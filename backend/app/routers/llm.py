"""Teste de conexão LLM (/api/v1/llm/test) — por provedor, sem travas."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.routers.auth import user_id_de, usuario_atual
from backend.app.schemas import LlmTestIn
from backend.core.database import Usuario, get_db
from backend.core.llm_router import test_provider

router = APIRouter(prefix="/llm", tags=["llm"])


@router.post("/test")
def testar_llm(
    payload: LlmTestIn,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
) -> dict:
    # testa com as chaves DO UTILIZADOR, não com as de outro
    return test_provider(db, payload.provider.strip().lower(), user_id_de(usuario))
"""Teste de conexão LLM (/api/v1/llm/test) — por provedor, sem travas."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.schemas import LlmTestIn
from backend.core.database import get_db
from backend.core.llm_router import test_provider

router = APIRouter(prefix="/llm", tags=["llm"])


@router.post("/test")
def testar_llm(payload: LlmTestIn, db: Session = Depends(get_db)) -> dict:
    return test_provider(db, payload.provider.strip().lower())

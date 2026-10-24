"""Configurações (/api/v1/configuracoes) — API keys mascaradas, sem travas."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.schemas import ConfiguracoesPatch
from backend.core.config import DEFAULT_LLM_BASE_URLS, DEFAULT_LLM_MODELS, SUPABASE_URL
from backend.core.database import Configuracao, get_db
from backend.core.llm_router import get_config

router = APIRouter(prefix="/configuracoes", tags=["configuracoes"])

SECRET_KEYS = ("nvidia_api_key", "google_api_key", "supabase_service_role_key")


def _mask(value: str) -> dict:
    if not value:
        return {"configured": False, "preview": ""}
    if len(value) <= 8:
        return {"configured": True, "preview": "••••"}
    return {"configured": True, "preview": f"{value[:4]}••••{value[-4:]}"}


@router.get("")
def obter_configuracoes(db: Session = Depends(get_db)) -> dict:
    return {
        "nvidia_api_key": _mask(get_config(db, "nvidia_api_key")),
        "nvidia_base_url": get_config(db, "nvidia_base_url", DEFAULT_LLM_BASE_URLS["nvidia"]),
        "nvidia_model": get_config(db, "nvidia_model", DEFAULT_LLM_MODELS["nvidia"]),
        "google_api_key": _mask(get_config(db, "google_api_key")),
        "google_base_url": get_config(db, "google_base_url", DEFAULT_LLM_BASE_URLS["google"]),
        "google_model": get_config(db, "google_model", DEFAULT_LLM_MODELS["google"]),
        "llm_fallback_ordem": get_config(db, "llm_fallback_ordem", "nvidia,google"),
        "db_backend": get_config(db, "db_backend", "supabase" if SUPABASE_URL else "sqlite"),
        "supabase_url": SUPABASE_URL,
        "supabase_service_role_key": _mask(get_config(db, "supabase_service_role_key")),
        "scheduler_ativo": get_config(db, "scheduler_ativo", "true") == "true",
        "intervalo_padrao_horas": int(get_config(db, "intervalo_padrao_horas", "6") or 6),
    }


@router.put("")
def salvar_configuracoes(payload: ConfiguracoesPatch, db: Session = Depends(get_db)) -> dict:
    data = payload.model_dump(exclude_none=True)
    for chave, valor in data.items():
        if chave in SECRET_KEYS and isinstance(valor, str) and valor.strip() == "":
            continue  # vazio não apaga segredo existente (UX sem travas)
        if isinstance(valor, bool):
            valor = "true" if valor else "false"
        row = db.get(Configuracao, chave)
        if row is None:
            row = Configuracao(chave=chave, valor=str(valor))
            db.add(row)
        else:
            row.valor = str(valor)
    db.commit()
    if "scheduler_ativo" in data:
        from backend.core import scheduler

        bruto = data["scheduler_ativo"]
        ligado = bruto if isinstance(bruto, bool) else str(bruto).lower() == "true"
        if ligado and not scheduler.esta_ativo():
            scheduler.iniciar()
            scheduler.recarregar()
        elif ligado:
            scheduler.recarregar()
        else:
            scheduler.parar()
    return obter_configuracoes(db)

"""Configurações (/api/v1/configuracoes) — API keys mascaradas, sem travas."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
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
        "meta_diaria": int(get_config(db, "meta_diaria", "3") or 3),
        "supabase_detectado": bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)
        or bool(get_config(db, "supabase_url") and get_config(db, "supabase_service_role_key")),
    }


@router.get("/llm/nvidia/models")
def listar_modelos_nvidia(db: Session = Depends(get_db)) -> dict:
    """Lista os modelos NVIDIA NIM disponíveis para a chave configurada.

    Proxy: a API key fica no banco local e nunca é exposta ao frontend.
    Retorna 400 sem chave; 502 em falha de consulta.
    """
    import httpx

    from backend.core.llm_router import provider_config

    cfg = provider_config(db, "nvidia")
    if not cfg["api_key"]:
        raise HTTPException(status_code=400, detail="API Key da NVIDIA não configurada — adicione-a antes de listar os modelos.")
    url = cfg["base_url"].rstrip("/") + "/models"
    try:
        resposta = httpx.get(url, headers={"Authorization": f"Bearer {cfg['api_key']}"}, timeout=20.0)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar a NVIDIA: {exc}") from exc
    if resposta.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"NVIDIA respondeu {resposta.status_code}: {resposta.text[:200]}",
        )
    ids = sorted(str(m.get("id")) for m in resposta.json().get("data", []) if m.get("id"))
    return {"models": ids, "modelo_atual": cfg["model"], "base_url": cfg["base_url"]}


@router.post("/testar-supabase")
def testar_supabase() -> dict:
    from backend.core import supabase_db

    try:
        cred = supabase_db.obter_credenciais()
        return {**supabase_db.testar_conexao(), "credencial_em": cred["origem"]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": str(exc)[:400]}


@router.get("/schema-supabase")
def schema_supabase() -> dict:
    from backend.core import supabase_db

    return {"sql": supabase_db.SCHEMA_SQL}


@router.post("/migrar-supabase")
def migrar_supabase() -> dict:
    from backend.core import supabase_db

    try:
        return supabase_db.migrar_do_sqlite()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": str(exc)[:400]}


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

"""Configurações (/api/v1/configuracoes) — API keys mascaradas, sem travas."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.schemas import ConfiguracoesPatch
from backend.core.config import DEFAULT_LLM_BASE_URLS, DEFAULT_LLM_MODELS, SUPABASE_URL
from backend.core.database import Configuracao, get_db
from backend.core.llm_router import get_config, limpar_nome_modelo

router = APIRouter(prefix="/configuracoes", tags=["configuracoes"])

SECRET_KEYS = ("nvidia_api_key", "google_api_key", "supabase_service_role_key")

# Chaves de configuração que guardam id de modelo — passam pela sanitização
# do prefixo de proxy (`nvidia_nim/`) tanto na leitura quanto na escrita.
CHAVES_MODELO = ("nvidia_model", "google_model")


def _mask(value: str) -> dict:
    if not value:
        return {"configured": False, "preview": ""}
    if len(value) <= 8:
        return {"configured": True, "preview": "••••"}
    return {"configured": True, "preview": f"{value[:4]}••••{value[-4:]}"}


def _listar_backups() -> list[dict]:
    """Backups do SQLite em data/backups (mais recente primeiro)."""
    from backend.core.config import DATA_DIR

    pasta = DATA_DIR / "backups"
    if not pasta.exists():
        return []
    arquivos = sorted(pasta.glob("pandanews_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {
            "nome": p.name,
            "tamanho_bytes": p.stat().st_size,
            "criado_em": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
        }
        for p in arquivos[:10]
    ]


def _status_banco(db: Session) -> dict:
    """Estado do banco activo para a UI — 'SQLite local' ou 'Supabase conectado'."""
    from backend.core import supabase_db

    cred = supabase_db.obter_credenciais()
    detectado = bool(cred["url"] and cred["key"])
    em_uso = get_config(db, "db_backend", "supabase" if cred["url"] and cred["key"] else "sqlite")
    migrado = get_config(db, "supabase_migrado", "") == "true"

    if em_uso == "supabase" and detectado:
        return {
            "backend": "supabase",
            "rotulo": "Supabase conectado",
            "detectado": True,
            "migrado": migrado,
            "backups": _listar_backups(),
            "detalhe": f"Projeto: {cred['url'].split('//')[-1].split('.')[0]} (credencial em: {cred['origem']})",
        }
    return {
        "backend": "sqlite",
        "rotulo": "SQLite local",
        "detectado": detectado,
        "migrado": migrado,
        "backups": _listar_backups(),
        "detalhe": "Dados em data/pandanews.db nesta máquina" + (
            " (credenciais Supabase disponíveis para migrar)" if detectado else ""
        ),
    }


@router.get("")
def obter_configuracoes(db: Session = Depends(get_db)) -> dict:
    return {
        "nvidia_api_key": _mask(get_config(db, "nvidia_api_key")),
        "nvidia_base_url": get_config(db, "nvidia_base_url", DEFAULT_LLM_BASE_URLS["nvidia"]),
        "nvidia_model": limpar_nome_modelo(get_config(db, "nvidia_model", DEFAULT_LLM_MODELS["nvidia"])),
        "google_api_key": _mask(get_config(db, "google_api_key")),
        "google_base_url": get_config(db, "google_base_url", DEFAULT_LLM_BASE_URLS["google"]),
        "google_model": limpar_nome_modelo(get_config(db, "google_model", DEFAULT_LLM_MODELS["google"])),
        "llm_fallback_ordem": get_config(db, "llm_fallback_ordem", "nvidia,google"),
        "db_backend": get_config(db, "db_backend", "supabase" if SUPABASE_URL else "sqlite"),
        "supabase_url": SUPABASE_URL,
        "supabase_service_role_key": _mask(get_config(db, "supabase_service_role_key")),
        "scheduler_ativo": get_config(db, "scheduler_ativo", "true") == "true",
        "intervalo_padrao_horas": int(get_config(db, "intervalo_padrao_horas", "6") or 6),
        "meta_diaria": int(get_config(db, "meta_diaria", "3") or 3),
        "supabase_detectado": bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)
        or bool(get_config(db, "supabase_url") and get_config(db, "supabase_service_role_key")),
        "banco": _status_banco(db),
    }


@router.get("/llm/nvidia/models")
def listar_modelos_nvidia(db: Session = Depends(get_db)) -> dict:
    """Lista os modelos NVIDIA NIM disponíveis para a chave configurada.

    Proxy: a API key fica no banco local e nunca é exposta ao frontend.
    Retorna 400 sem chave; 502 em falha de consulta. A Base URL é normalizada
    pelo mesmo helper do Thunderbolt, então ``/v1``, ``/v1/models`` e
    ``/v1/chat/completions`` são aceitos sem duplicar o sufixo.

    HOTFIX 0.5.03: os ids voltam **limpos** — sem o prefixo ``nvidia_nim/``
    de convenção do LiteLLM. O frontend só exibe (e só pode salvar) o id que
    a API da NVIDIA aceita no ``/chat/completions``.
    """
    import httpx

    from backend.core.llm_router import _normalizar_base_url, provider_config

    cfg = provider_config(db, "nvidia")
    if not cfg["api_key"]:
        raise HTTPException(status_code=400, detail="API Key da NVIDIA não configurada — adicione-a antes de listar os modelos.")
    base = _normalizar_base_url(cfg["base_url"])
    if not base:
        raise HTTPException(status_code=400, detail=f"Base URL da NVIDIA inválida: {cfg['base_url']!r}")
    url = f"{base}/models"
    try:
        resposta = httpx.get(
            url,
            headers={"Accept": "application/json", "Authorization": f"Bearer {cfg['api_key']}"},
            timeout=20.0,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar a NVIDIA: {exc}") from exc
    if resposta.status_code in (401, 403):
        raise HTTPException(
            status_code=502,
            detail=f"A NVIDIA recusou a API key (HTTP {resposta.status_code}). Verifique a chave em Configurações.",
        )
    if resposta.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"NVIDIA respondeu {resposta.status_code}: {resposta.text[:200]}",
        )
    try:
        dados = resposta.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="A NVIDIA devolveu uma resposta que não é JSON.") from exc
    # Ids limpos: `nvidia_nim/` (convenção LiteLLM) fora, `fornecedor/modelo` intacto.
    ids = sorted({limpar_nome_modelo(m.get("id")) for m in (dados.get("data") or []) if m.get("id")})
    if not ids:
        raise HTTPException(status_code=502, detail="A NVIDIA não devolveu nenhum modelo para esta chave.")
    modelo_atual = limpar_nome_modelo(cfg["model"])
    return {
        "models": ids,
        "modelo_atual": modelo_atual,
        "base_url": cfg["base_url"],
        "modelo_atual_disponivel": modelo_atual in ids,
    }


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
        if chave in CHAVES_MODELO and isinstance(valor, str):
            # HOTFIX 0.5.03: grava só o id limpo — `nvidia_nim/` nunca entra
            # no banco, então a UI e a próxima chamada já nascem corretas.
            valor = limpar_nome_modelo(valor)
            if not valor:
                continue  # string vazia após limpeza não apaga o modelo atual
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

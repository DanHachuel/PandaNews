"""Router de LLM do PandaNews: fallback ordenado NVIDIA NIM -> Google Gemini.

Roteamento por prioridade com llmswitch-client (circuit breaker embutido).
O provedor que responde é devolvido junto com o texto para registrar em
noticias.llm_provider. Teste por provedor via httpx direto no endpoint
chat/completions (compatível com OpenAI) dos dois provedores.
"""
from __future__ import annotations

import time

import httpx

from backend.core.config import DEFAULT_LLM_BASE_URLS, DEFAULT_LLM_MODELS

PROVEDORES = ("nvidia", "google")


def get_config(db, chave: str, padrao: str = "") -> str:
    from backend.core.database import Configuracao

    row = db.get(Configuracao, chave)
    return row.valor if row is not None and row.valor else padrao


def provider_config(db, provider: str) -> dict:
    return {
        "api_key": get_config(db, f"{provider}_api_key"),
        "base_url": get_config(db, f"{provider}_base_url", DEFAULT_LLM_BASE_URLS[provider]),
        "model": get_config(db, f"{provider}_model", DEFAULT_LLM_MODELS[provider]),
    }


def test_provider(db, provider: str) -> dict:
    """Ping real ao endpoint chat/completions do provedor (1 token)."""
    if provider not in PROVEDORES:
        return {"ok": False, "detail": f"Provedor desconhecido: {provider}"}
    cfg = provider_config(db, provider)
    if not cfg["api_key"]:
        return {"ok": False, "detail": "API key não configurada — adicione em Configurações."}
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": "Responda apenas: ok"}],
        "max_tokens": 5,
    }
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    started = time.perf_counter()
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=20.0)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if resp.status_code == 200:
            return {"ok": True, "status": 200, "latency_ms": elapsed_ms, "model": cfg["model"], "base_url": cfg["base_url"]}
        return {"ok": False, "status": resp.status_code, "detail": resp.text[:400]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}


def gerar_texto(db, prompt: str, max_tokens: int = 1024) -> tuple[str, str]:
    """Gera texto com fallback ordenado. Retorna (texto, provedor_que_respondeu)."""
    from llmswitch import Client, Endpoint, LLMSwitchConfig

    ordem = [p.strip() for p in get_config(db, "llm_fallback_ordem", "nvidia,google").split(",") if p.strip()]
    endpoints = []
    for provider in ordem:
        if provider not in PROVEDORES:
            continue
        cfg = provider_config(db, provider)
        if cfg["api_key"]:
            endpoints.append(
                Endpoint(provider=provider, base_url=cfg["base_url"], api_key=cfg["api_key"], model=cfg["model"])
            )
    if not endpoints:
        raise RuntimeError("Nenhum provedor de LLM configurado. Adicione uma API key em Configurações.")

    config = LLMSwitchConfig(alias="pandanews", endpoints=endpoints)
    client = Client(configs=config)
    resp = client.chat.completions.create(
        model="pandanews",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    texto = resp.choices[0].message.content or ""
    model = getattr(resp, "model", "") or ""
    if "llama" in model or "nvidia" in model:
        provedor = "nvidia"
    elif "gemini" in model:
        provedor = "google"
    else:
        provedor = endpoints[0].provider if endpoints else "desconhecido"
    return texto, provedor

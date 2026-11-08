"""Router de LLM do PandaNews: fallback ordenado e à prova de falhas.

Roteamento explícito, provedor por provedor, na ordem configurada
(padrão: NVIDIA NIM → Google Gemini). Qualquer erro HTTP do provedor atual
(4xx/5xx — incluindo 404/410 de modelos descontinuados) é registrado e o
próximo provedor é acionado imediatamente. A função devolve (texto, provedor)
para registrar em noticias.llm_provider.
"""
from __future__ import annotations

import logging
import time

import httpx
from openai import APIStatusError, OpenAI

from backend.core.config import DEFAULT_LLM_BASE_URLS, DEFAULT_LLM_MODELS

PROVEDORES = ("nvidia", "google")

# Logger filho do uvicorn.error: mensagens vão para o backend.log (e stderr),
# com a disciplina de logs do servidor.
logger = logging.getLogger("uvicorn.error.pandanews")


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


def _chamar_provedor(db, provider: str, prompt: str, max_tokens: int) -> tuple[str, str]:
    """Uma chamada de chat completion no provedor. Levanta em caso de erro."""
    cfg = provider_config(db, provider)
    client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], timeout=60.0)
    resposta = client.chat.completions.create(
        model=cfg["model"],
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    texto = resposta.choices[0].message.content or ""
    modelo = str(getattr(resposta, "model", "") or cfg["model"])
    return texto, modelo


def gerar_texto(db, prompt: str, max_tokens: int = 1024) -> tuple[str, str]:
    """Gera texto com fallback ordenado. Retorna (texto, provedor_que_respondeu).

    Se um provedor falhar por qualquer erro HTTP, registra o incidente e
    aciona o próximo da lista. Só levanta erro quando TODOS falham.
    """
    ordem = [p.strip() for p in get_config(db, "llm_fallback_ordem", "nvidia,google").split(",") if p.strip()]
    disponiveis = [p for p in ordem if p in PROVEDORES and provider_config(db, p)["api_key"]]
    if not disponiveis:
        raise RuntimeError("Nenhum provedor de LLM configurado. Adicione uma API key em Configurações.")

    ultimo_erro: Exception | None = None
    for indice, provider in enumerate(disponiveis):
        proximo = disponiveis[indice + 1] if indice + 1 < len(disponiveis) else None
        try:
            texto, modelo = _chamar_provedor(db, provider, prompt, max_tokens)
            logger.info("LLM: %s respondeu (modelo %s)", provider, modelo)
            return texto, provider
        except APIStatusError as exc:
            status = exc.status_code
            ultimo_erro = exc
            logger.warning("LLM: %s falhou com HTTP %s (%s)", provider, status, str(exc)[:300])
            if status in (404, 410):
                destino = proximo or "nenhum"
                logger.warning(
                    "Modelo %s indisponível (Status %s). Acionando fallback para %s.",
                    provider,
                    status,
                    destino,
                )
        except Exception as exc:  # noqa: BLE001 — timeouts, rede, auth: tenta o próximo
            ultimo_erro = exc
            logger.warning("LLM: %s falhou (%s): %s", provider, type(exc).__name__, str(exc)[:300])
        if proximo:
            continue
    raise RuntimeError(f"Todos os provedores de LLM falharam ({', '.join(disponiveis)}). Último erro: {ultimo_erro}")


def test_provider(db, provider: str) -> dict:
    """Chamada real e curta (POST /chat/completions) para validar a chave.

    404/410 → 'degraded': a chave pode funcionar, mas o modelo endpoint está
    indisponível — o pipeline segue pelo fallback. A UI distingue os estados.
    """
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
        if resp.status_code in (404, 410):
            return {
                "ok": False,
                "degraded": True,
                "status": resp.status_code,
                "detail": (
                    f"Sua chave da NVIDIA retornou erro {resp.status_code}. "
                    "O sistema usará o Gemini (fallback) para gerar as notícias."
                    if provider == "nvidia"
                    else f"Endpoint do Gemini retornou {resp.status_code}. O sistema usará a NVIDIA (primário) para gerar as notícias."
                ),
            }
        return {"ok": False, "status": resp.status_code, "detail": resp.text[:400]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}

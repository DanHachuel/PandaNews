"""Router de LLM do PandaNews — réplica da integração NVIDIA do Thunderbolt.

O projeto Thunderbolt (referência que funciona) fala com provedores
OpenAI-compatible — NVIDIA NIM, Gemini etc. — por **HTTP direto**:

    POST {base_url}/chat/completions
    Authorization: Bearer <api_key>
    Content-Type:  application/json
    {"model": ..., "messages": [...], "max_tokens": ..., "temperature": 0}

Este módulo copia essa estrutura exata, trocando `requests` por `httpx` (já
dependência do PandaNews). Nenhum SDK novo é necessário — em particular a
biblioteca `openai` **não** é usada: ela não está declarada em
requirements.txt, então instalá-la quebraria o backend com ImportError em
toda instalação nova (foi exatamente o que derrubou o fluxo antes).

Fallback implacável: qualquer exceção — HTTP 4xx/5xx (inclusive 404/410 de
modelo descontinuado), timeout, erro de rede ou JSON inválido — é registrada e
o próximo provedor da lista é acionado imediatamente. Nada escapa.
"""
from __future__ import annotations

import logging
from urllib.parse import urlsplit, urlunsplit

import httpx

from backend.core.config import DEFAULT_LLM_BASE_URLS, DEFAULT_LLM_MODELS

PROVEDORES = ("nvidia", "google")

# Nomes exibidos no log — a mensagem de fallback usa estes rótulos.
NOMES_PROVEDORES = {"nvidia": "NVIDIA", "google": "Google Gemini"}

TIMEOUT_SEGUNDOS = 60.0

# Prefixos de convenção de proxy (LiteLLM e correlatos). A API da NVIDIA NIM
# recebe o id "cru" do modelo — `mistralai/mistral-large-4-1t-a52b` — e não
# reconhece `nvidia_nim/` na frente: devolve 404/400 de "model not found".
# A barra dentro do id (`fornecedor/modelo`) é legítima e NÃO é removida;
# apenas o prefixo de proxy é.
PREFIXOS_PROXY = ("nvidia_nim/",)


def limpar_nome_modelo(modelo: str) -> str:
    """Remove o prefixo de proxy (``nvidia_nim/``) do id do modelo.

    Ids salvos por outra ferramenta (ou colados de documentação do LiteLLM)
    podem chegar como ``nvidia_nim/mistralai/mistral-large-4-1t-a52b``. Como
    o PandaNews faz HTTP direto para a NVIDIA, esse prefixo precisa sair
    antes de montar o payload. A remoção é repetida (prefixo colado duas
    vezes) e insensível a maiúsculas/espaços; um id sem prefixo volta
    intacto — em particular `fornecedor/modelo` não é tocado.
    """
    nome = str(modelo or "").strip()
    while nome:
        for prefixo in PREFIXOS_PROXY:
            if nome[: len(prefixo)].lower() == prefixo:
                nome = nome[len(prefixo) :].lstrip()
                break
        else:
            return nome
    return nome

# Logger filho do uvicorn.error: mensagens vão para o backend.log (e stderr),
# com a disciplina de logs do servidor.
logger = logging.getLogger("uvicorn.error.pandanews")


# --------------------------------------------------------------- endpoints

def _normalizar_base_url(base_url: str) -> str:
    """Mantém apenas esquema/host/path da Base URL (como o Thunderbolt).

    Aceita tanto ``https://host/v1`` quanto ``https://host/v1/models`` ou
    ``https://host/v1/chat/completions`` — o sufixo é descartado/refeito,
    evitando o ``/chat/completions`` duplicado que provocaria 404.
    """
    raw = str(base_url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return raw.rstrip("/")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return raw.rstrip("/")
    path = parsed.path.rstrip("/")
    for sufixo in ("/chat/completions", "/models"):
        if path.endswith(sufixo):
            path = path[: -len(sufixo)]
            break
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def chat_completions_endpoint(base_url: str) -> str:
    """Endpoint de Chat Completions — igual ao do Thunderbolt."""
    base = _normalizar_base_url(base_url)
    return f"{base}/chat/completions" if base else ""


def _headers(api_key: str) -> dict:
    """Cabeçalhos OpenAI-compatible do Thunderbolt (Accept incluído)."""
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


# ------------------------------------------------------------- acesso a config

def get_config(db, chave: str, padrao: str = "") -> str:
    from backend.core.database import Configuracao

    row = db.get(Configuracao, chave)
    return row.valor if row is not None and row.valor else padrao


def provider_config(db, provider: str) -> dict:
    return {
        "api_key": get_config(db, f"{provider}_api_key"),
        "base_url": get_config(db, f"{provider}_base_url", DEFAULT_LLM_BASE_URLS[provider]),
        # O id sai do banco já limpo: nada de `nvidia_nim/` no payload HTTP.
        "model": limpar_nome_modelo(get_config(db, f"{provider}_model", DEFAULT_LLM_MODELS[provider])),
    }


# ---------------------------------------------------------- chamada ao provedor

def chamar_provedor(db, provider: str, prompt: str, max_tokens: int) -> tuple[str, str]:
    """Uma chamada de chat completion no provedor. Levanta em caso de erro.

    Cópia da estrutura do Thunderbolt: POST HTTP direto no endpoint
    ``{base_url}/chat/completions`` com Bearer token. Qualquer resposta >= 400
    levanta ``httpx.HTTPStatusError`` — capturada pelo fallback em
    ``gerar_texto``.
    """
    cfg = provider_config(db, provider)
    if not cfg["api_key"]:
        raise RuntimeError(f"{NOMES_PROVEDORES.get(provider, provider)}: API key não configurada.")
    if not cfg["model"]:
        raise RuntimeError(f"{NOMES_PROVEDORES.get(provider, provider)}: nenhum modelo configurado.")

    endpoint = chat_completions_endpoint(cfg["base_url"])
    if not endpoint:
        raise RuntimeError(f"{NOMES_PROVEDORES.get(provider, provider)}: Base URL inválida ({cfg['base_url']!r}).")

    # HOTFIX 0.5.03: `nvidia_nim/` é convenção do LiteLLM, não da API da
    # NVIDIA. O prefixo sai aqui — antes do POST — para o `model` do JSON
    # ser exatamente o id do catálogo (`mistralai/...`).
    modelo = limpar_nome_modelo(cfg["model"])
    payload = {
        "model": modelo,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": max_tokens,
    }

    with httpx.Client(timeout=TIMEOUT_SEGUNDOS) as client:
        resposta = client.post(endpoint, headers=_headers(cfg["api_key"]), json=payload)
        resposta.raise_for_status()
        dados = resposta.json()

    texto = ""
    escolhas = dados.get("choices") or []
    if escolhas:
        texto = (escolhas[0].get("message") or {}).get("content") or ""
    if not texto:
        raise RuntimeError(f"{NOMES_PROVEDORES.get(provider, provider)}: resposta sem conteúdo.")

    return texto, modelo or str(dados.get("model") or cfg["model"])


def gerar_texto(db, prompt: str, max_tokens: int = 1024) -> tuple[str, str]:
    """Gera texto com fallback ordenado. Retorna (texto, provedor_que_respondeu).

    Fallback implacável: capture ``Exception`` — não importa se é HTTP 404/410
    (modelo descontinuado), 500, timeout ou queda de rede. O incidente é
    registrado e o próximo provedor é acionado na mesma iteração.
    """
    ordem = [p.strip() for p in get_config(db, "llm_fallback_ordem", "nvidia,google").split(",") if p.strip()]
    disponiveis = [p for p in ordem if p in PROVEDORES and provider_config(db, p)["api_key"]]
    if not disponiveis:
        raise RuntimeError("Nenhum provedor de LLM configurado. Adicione uma API key em Configurações.")

    ultimo_erro: Exception | None = None
    for indice, provider in enumerate(disponiveis):
        nome = NOMES_PROVEDORES.get(provider, provider)
        proximo = disponiveis[indice + 1] if indice + 1 < len(disponiveis) else None
        nome_proximo = NOMES_PROVEDORES.get(proximo, proximo) if proximo else "nenhum provedor"

        try:
            texto, modelo = chamar_provedor(db, provider, prompt, max_tokens)
            logger.info("LLM: %s respondeu (modelo %s)", nome, modelo)
            # Banco/UI rotulam o provedor do Gemini como "gemini" (id de exibição,
            # não o id interno "google") — mantido desde a 0.4.05.
            return texto, "gemini" if provider == "google" else provider

        except Exception as exc:  # noqa: BLE001 — fallback implacável: TUDO troca de provedor
            ultimo_erro = exc
            if proximo:
                logger.warning("Erro na %s (%s). Acionando %s...", nome, exc, nome_proximo)
            else:
                logger.warning("Erro na %s (%s). Sem provedor restante no fallback.", nome, exc)

    raise RuntimeError(
        f"Todos os provedores de LLM falharam ({', '.join(disponiveis)}). Último erro: {ultimo_erro}"
    )


# ------------------------------------------------------------ teste de conexão

def test_provider(db, provider: str) -> dict:
    """Teste REAL de conexão: uma chamada de inferência com 1 token.

    Igual ao ``validate_openai_compatible_api_key`` do Thunderbolt — não lista
    modelos, executa um POST mínimo em ``/chat/completions``. A string de erro
    do provedor volta no JSON para o frontend exibir na tela.

    404/410 → ``degraded``: a chave pode ser válida, mas o modelo saiu do
    catálogo — o pipeline segue pelo fallback sem travar a tela.
    """
    if provider not in PROVEDORES:
        return {"ok": False, "detail": f"Provedor desconhecido: {provider}"}
    cfg = provider_config(db, provider)
    if not cfg["api_key"]:
        return {"ok": False, "detail": "API key não configurada — adicione em Configurações."}
    if not cfg["model"]:
        return {"ok": False, "detail": "Nenhum modelo configurado — selecione um antes de testar."}

    endpoint = chat_completions_endpoint(cfg["base_url"])
    if not endpoint:
        return {"ok": False, "detail": f"Base URL inválida: {cfg['base_url']!r}"}

    # Mesma sanitização da chamada real: o teste tem de provar o mesmo
    # `model` que a geração de notícias envia.
    modelo = limpar_nome_modelo(cfg["model"])
    payload = {
        "model": modelo,
        "messages": [{"role": "user", "content": "Responda apenas OK."}],
        "max_tokens": 1,
        "temperature": 0,
    }

    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(endpoint, headers=_headers(cfg["api_key"]), json=payload)
    except httpx.HTTPError as exc:
        return {"ok": False, "detail": f"Não foi possível testar {endpoint}: {exc}"}

    elapsed_ms = int(resp.elapsed.total_seconds() * 1000)

    if resp.status_code in (401, 403):
        return {
            "ok": False,
            "status": resp.status_code,
            "detail": f"O endpoint recusou a API key (HTTP {resp.status_code}). Verifique a chave em Configurações.",
        }
    if resp.status_code in (404, 410):
        return {
            "ok": False,
            "degraded": True,
            "status": resp.status_code,
            "detail": (
                f"Modelo '{modelo}' indisponível na NVIDIA (HTTP {resp.status_code}): "
                f"{resp.text[:200]} — use o botão ↻ para escolher um modelo do catálogo. "
                "As notícias seguem sendo geradas pelo Gemini (fallback)."
                if provider == "nvidia"
                else (
                    f"Modelo '{modelo}' indisponível no Gemini (HTTP {resp.status_code}): "
                    f"{resp.text[:200]} — as notícias seguem sendo geradas pela NVIDIA (primário)."
                )
            ),
        }
    if resp.status_code >= 400:
        return {
            "ok": False,
            "status": resp.status_code,
            "detail": f"O endpoint de teste devolveu HTTP {resp.status_code}: {resp.text[:400]}",
        }

    return {
        "ok": True,
        "status": 200,
        "latency_ms": elapsed_ms,
        "model": modelo,
        "base_url": cfg["base_url"],
        "endpoint": endpoint,
    }

"""Geração de imagens do PandaNews (Gemini Image).

Extrai palavras-chave do título/resumo da notícia (TF simples), monta um
prompt fotojornalístico e chama a Gemini Image API. A imagem é salva em
<home>/data/imagens/ e servida por /api/v1/imagens/{nome}. Se a geração
falhar, a notícia segue sem imagem (sinalizada na UI) — o pipeline não para.
"""
from __future__ import annotations

import base64
import logging
import re
from datetime import datetime, timezone

import httpx

from backend.core.config import IMAGES_DIR
from backend.core.llm_router import get_config

logger = logging.getLogger("uvicorn.error.pandanews")

IMAGE_MODEL_DEFAULT = "gemini-3.1-flash-image"

STOPWORDS = set(
    "a o e de da do das dos em no na nos nas um uma com para por que se ao aos "
    "as os mais como onde quando após sobre entre sua seu suas seus pelo pela "
    "isso esse essa isto este esta foi ser ter pela pelos".split()
)


def extrair_palavras_chave(texto: str, max_palavras: int = 10) -> list[str]:
    palavras = re.findall(r"[a-záàâãéêíóôõúüç]{4,}", (texto or "").lower())
    contagem: dict[str, int] = {}
    for palavra in palavras:
        if palavra in STOPWORDS:
            continue
        contagem[palavra] = contagem.get(palavra, 0) + 1
    ordenadas = sorted(contagem, key=contagem.get, reverse=True)
    return ordenadas[:max_palavras]


def gerar_imagem(db, prompt_visual: str, user_id: str = "") -> bytes:
    """Chama a Gemini Image API e devolve os bytes da imagem."""
    api_key = get_config(db, "google_api_key", user_id=user_id)
    if not api_key:
        raise RuntimeError("API key do Google Gemini não configurada — adicione em Configurações para gerar imagens.")
    modelo = get_config(db, "google_image_model", IMAGE_MODEL_DEFAULT, user_id)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt_visual}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }
    resposta = httpx.post(url, json=payload, headers={"x-goog-api-key": api_key}, timeout=180.0)
    if resposta.status_code != 200:
        raise RuntimeError(f"Gemini Image respondeu {resposta.status_code}: {resposta.text[:300]}")
    dados = resposta.json()
    for candidato in dados.get("candidates", []):
        for parte in candidato.get("content", {}).get("parts", []):
            inline = parte.get("inlineData") or parte.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    raise RuntimeError("Gemini Image não retornou imagem — verifique o modelo configurado em Configurações.")


# ------------------------------------------------------------------ storage
#
# Multi-tenant e cross-platform: em modo Supabase a imagem vai para o bucket
# `pandanews-imagens` e passa a ser servida pela URL do Storage; em modo local
# continua em <home>/data/imagens. A escolha nunca quebra o pipeline: se o
# upload falhar, cai para o disco local (a notícia fica sem imagem, não sem
# texto).

BUCKET_IMAGENS = "pandanews-imagens"


def _supabase_activado(user_id: str = "", db=None) -> bool:
    """Modo Supabase: credenciais no ambiente ou nas settings do utilizador."""
    from backend.core.config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        return True
    if db is not None and user_id:
        return bool(
            get_config(db, "supabase_url", user_id=user_id)
            and get_config(db, "supabase_service_role_key", user_id=user_id)
        )
    return False


def _upload_supabase(dados: bytes, nome: str) -> str | None:
    """Envia a imagem para o bucket; devolve a URL pública (ou None a falhar)."""
    try:
        from backend.core import supabase_db

        client = supabase_db._client()
        client.storage.from_(BUCKET_IMAGENS).upload(nome, dados, {"content-type": "image/png"})
        return client.storage.from_(BUCKET_IMAGENS).get_public_url(nome)
    except Exception as exc:  # noqa: BLE001 — upload falho não pode travar o pipeline
        logger.warning("Supabase Storage: upload de %s falhou (%s) — a usar disco local", nome, exc)
        return None


def _salvar(dados: bytes, nome: str, db=None, user_id: str = "") -> str:
    # `nome` nunca tem separador de caminho e a URL usa sempre "/" — o mesmo
    # valor no Windows e no Linux.
    if _supabase_activado(user_id, db):
        url = _upload_supabase(dados, nome)
        if url:
            return url
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    (IMAGES_DIR / nome).write_bytes(dados)
    return f"/api/v1/imagens/{nome}"


def imagem_para_noticia(db, noticia) -> str:
    """Gera a imagem de capa de uma notícia (estilo fotojornalístico)."""
    chaves = extrair_palavras_chave(f"{noticia.titulo} {noticia.resumo}")
    prompt = (
        "Fotografia jornalística profissional, iluminação natural, realista, "
        "sem texto ou marca d'água, retratando: "
        f"{', '.join(chaves) if chaves else (noticia.titulo or 'notícias gerais')}"
    )
    dono = getattr(noticia, "user_id", "") or ""
    dados = gerar_imagem(db, prompt, dono)
    return _salvar(dados, f"{noticia.id}.png", db, dono)


def imagem_manual(db, prompt: str, user_id: str = "") -> str:
    """Gera uma imagem a partir de prompt livre (página Imagens)."""
    dados = gerar_imagem(db, prompt, user_id)
    nome = f"manual-{int(datetime.now(timezone.utc).timestamp() * 1000)}.png"
    return _salvar(dados, nome, db, user_id)

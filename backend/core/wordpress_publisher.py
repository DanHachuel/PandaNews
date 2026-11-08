"""Publicador WordPress (Fase 0.5.00).

Envia notícias aprovadas para um blog WordPress via REST API usando Basic Auth
(usuário + Senha de Aplicativo gerada no painel do WP). Fluxo em 2 etapas:
upload da imagem para /wp-json/wp/v2/media → criação do post em
/wp-json/wp/v2/posts com featured_media e categoria.
"""
from __future__ import annotations

import logging
from pathlib import Path

import httpx

from backend.core.config import IMAGES_DIR
from backend.core.database import Blog
from backend.core.llm_router import get_config

logger = logging.getLogger("uvicorn.error.pandanews")

MINIMO_PALAVRAS_PUBLICACAO = 300


def _credenciais(db) -> dict:
    url = get_config(db, "wordpress_url").rstrip("/")
    user = get_config(db, "wordpress_user")
    app_password = get_config(db, "wordpress_app_password")
    if not (url and user and app_password):
        raise RuntimeError(
            "WordPress não configurado — informe URL, usuário e Senha de Aplicativo em Configurações → Integração WordPress."
        )
    return {"url": url, "user": user, "password": app_password}


def credenciais_presentes(db) -> dict:
    """Estado das credenciais para a UI (sem expor segredos)."""
    url = get_config(db, "wordpress_url").rstrip("/")
    user = get_config(db, "wordpress_user")
    password = get_config(db, "wordpress_app_password")
    return {
        "configurado": bool(url and user and password),
        "url": url,
        "user": user,
        "password_configured": bool(password),
    }


def testar_conexao(db) -> dict:
    """GET /wp-json/wp/v2/users/me — valida URL + credenciais."""
    cred = _credenciais(db)
    try:
        resp = httpx.get(
            f"{cred['url']}/wp-json/wp/v2/users/me",
            auth=(cred["user"], cred["password"]),
            timeout=20.0,
        )
    except httpx.HTTPError as exc:
        return {"ok": False, "detail": f"Não foi possível conectar: {exc}"}
    if resp.status_code == 200:
        nome = resp.json().get("name", cred["user"])
        return {"ok": True, "detail": f"Autenticado como {nome}.", "user": nome}
    return {"ok": False, "detail": f"WP respondeu {resp.status_code}: {resp.text[:200]}"}


def _imagem_local(imagem_url: str) -> Path | None:
    nome = (imagem_url or "").rsplit("/", 1)[-1]
    if not nome:
        return None
    caminho = IMAGES_DIR / nome
    return caminho if caminho.exists() else None


def _upload_midia(cred: dict, caminho: Path) -> int | None:
    """Envia a imagem para a biblioteca de mídia; devolve o media ID."""
    with open(caminho, "rb") as arquivo:
        dados = arquivo.read()
    resp = httpx.post(
        f"{cred['url']}/wp-json/wp/v2/media",
        content=dados,
        headers={
            "Content-Disposition": f'attachment; filename="{caminho.name}"',
            "Content-Type": "image/png",
        },
        auth=(cred["user"], cred["password"]),
        timeout=120.0,
    )
    if resp.status_code in (200, 201):
        media_id = resp.json().get("id")
        if media_id:
            return int(media_id)
    logger.warning("WordPress: upload de mídia falhou (%s): %s", resp.status_code, resp.text[:200])
    return None


def resolver_categoria(cred: dict, nome_tema: str) -> int | None:
    """Categoria WP pelo nome do tema do blog — busca ou cria."""
    if not nome_tema:
        return None
    try:
        resp = httpx.get(
            f"{cred['url']}/wp-json/wp/v2/categories",
            params={"search": nome_tema, "per_page": 20},
            auth=(cred["user"], cred["password"]),
            timeout=20.0,
        )
        if resp.status_code == 200:
            for categoria in resp.json():
                if str(categoria.get("name", "")).lower() == nome_tema.lower():
                    return int(categoria["id"])
        resp = httpx.post(
            f"{cred['url']}/wp-json/wp/v2/categories",
            json={"name": nome_tema.title()},
            auth=(cred["user"], cred["password"]),
            timeout=20.0,
        )
        if resp.status_code in (200, 201) and resp.json().get("id"):
            return int(resp.json()["id"])
    except httpx.HTTPError as exc:
        logger.warning("WordPress: falha ao resolver categoria (%s)", exc)
    return None


def contar_palavras(texto: str) -> int:
    return len((texto or "").split())


def publish_to_wordpress(db, noticia) -> dict:
    """Publica a notícia completa. Retorna {"post_id": int, "link": str}."""
    cred = _credenciais(db)
    palavras = contar_palavras(noticia.corpo)
    if palavras < MINIMO_PALAVRAS_PUBLICACAO:
        raise RuntimeError(
            f"Texto com {palavras} palavras — mínimo de {MINIMO_PALAVRAS_PUBLICACAO} para publicar (diretriz AdSense)."
        )

    blog = db.get(Blog, noticia.blog_id)
    categoria_id = resolver_categoria(cred, blog.tema if blog else "")

    featured_media = None
    if noticia.imagem_url:
        caminho = _imagem_local(noticia.imagem_url)
        if caminho:
            featured_media = _upload_midia(cred, caminho)

    payload: dict = {
        "title": noticia.titulo,
        "content": noticia.corpo,
        "status": "publish",
    }
    if categoria_id:
        payload["categories"] = [categoria_id]
    if featured_media:
        payload["featured_media"] = featured_media

    resp = httpx.post(
        f"{cred['url']}/wp-json/wp/v2/posts",
        json=payload,
        auth=(cred["user"], cred["password"]),
        timeout=60.0,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"WP respondeu {resp.status_code}: {resp.text[:300]}")
    dados = resp.json()
    post_id = int(dados["id"])
    link = dados.get("link") or f"{cred['url']}/?p={post_id}"
    logger.info("WordPress: post %s publicado (%s)", post_id, link)
    return {"post_id": post_id, "link": link}

"""Pipeline de notícias do PandaNews.

Coleta RSS → filtragem por relevância (palavras-chave do tema/região) →
rascunho via LLM (fallback ordenado NVIDIA → Gemini) → imagem
fotojornalística via Gemini → status rascunho. Cada etapa registra logs
(sucesso/erro) por blog; itens já utilizados são deduplicados (tabela vistos).
"""
from __future__ import annotations

import json
import re

import feedparser
from sqlalchemy import select

from backend.core import image_gen, llm_router
from backend.core.database import Blog, Log, Noticia, SessionLocal, Visto

TEMAS_PALAVRAS: dict[str, list[str]] = {
    "esporte": [
        "futebol", "jogo", "time", "campeonato", "gol", "partida", "atleta",
        "seleção", "torcida", "liga", "olimpíadas", "campeão", "vitória",
    ],
    "politica": [
        "governo", "presidente", "congresso", "eleição", "eleições", "deputado",
        "senado", "senador", "ministro", "partido", "prefeito", "reforma", "voto",
    ],
    "economia": [
        "mercado", "dólar", "inflação", "juros", "bolsa", "pib", "economia",
        "impostos", "emprego", "salário", "banco central", "câmbio",
    ],
    "tecnologia": [
        "tecnologia", "inteligência artificial", "app", "startup", "software",
        "chip", "smartphone", "internet", "dados", "robô", "algoritmo",
    ],
    "geral": [],
}


def _log(db, blog_id: int | None, etapa: str, status: str, mensagem: str) -> None:
    db.add(Log(blog_id=blog_id, etapa=etapa, status=status, mensagem=mensagem[:2000]))
    db.commit()


def _limpar(texto: str, limite: int) -> str:
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    return " ".join(texto.split())[:limite]


def coletar_itens(db, blog: Blog, fontes: list[str]) -> list[dict]:
    itens: list[dict] = []
    for url in fontes:
        try:
            feed = feedparser.parse(url)
            if getattr(feed, "bozo", 0) and not feed.entries:
                erro = getattr(feed, "bozo_exception", "formato inválido")
                _log(db, blog.id, "coleta", "erro", f"Falha ao ler feed {url}: {erro}")
                continue
            for entrada in feed.entries[:15]:
                itens.append(
                    {
                        "titulo": _limpar(getattr(entrada, "title", ""), 300),
                        "link": getattr(entrada, "link", "") or "",
                        "resumo": _limpar(getattr(entrada, "summary", ""), 600),
                    }
                )
            _log(db, blog.id, "coleta", "sucesso", f"{len(feed.entries)} itens coletados de {url}")
        except Exception as exc:  # noqa: BLE001
            _log(db, blog.id, "coleta", "erro", f"Exceção ao ler {url}: {exc}")
    return itens


def score_relevancia(item: dict, blog: Blog) -> float:
    texto = f"{item['titulo']} {item['resumo']}".lower()
    pontos = 0.0
    for palavra in TEMAS_PALAVRAS.get(blog.tema, []):
        if palavra in texto:
            pontos += 1.0
    regiao = (blog.regiao or "").strip().lower()
    if regiao and regiao in texto:
        pontos += 2.0
    return pontos


def _prompt_redacao(blog: Blog, item: dict) -> str:
    estilo = (blog.estilo_editorial or "").strip() or "jornalismo claro e direto em português do Brasil"
    return (
        "Você é editor-chefe de um blog de notícias. Escreva uma notícia ORIGINAL em "
        "português do Brasil a partir da fonte abaixo.\n"
        f"Blog: {blog.nome} — tema: {blog.tema} — região: {blog.regiao}\n"
        f"Estilo editorial: {estilo}\n"
        f"Fonte: \"{item['titulo']}\"\n"
        f"Resumo da fonte: {item['resumo']}\n"
        "Regras: reescreva com palavras próprias; não invente fatos que não estejam "
        "na fonte; 3 a 5 parágrafos.\n"
        'Responda SOMENTE com JSON válido no formato: {"titulo": "...", "resumo": "...", "corpo": "..."}'
    )


def _parse_resposta_llm(texto: str) -> dict:
    bruto = (texto or "").strip()
    bruto = re.sub(r"^```(json)?\s*|\s*```$", "", bruto)
    try:
        return json.loads(bruto)
    except Exception:  # noqa: BLE001
        casado = re.search(r"\{.*\}", bruto, re.DOTALL)
        if casado:
            try:
                return json.loads(casado.group(0))
            except Exception:  # noqa: BLE001
                pass
    return {"titulo": "", "resumo": "", "corpo": bruto}


def gerar_noticia(blog_id: int) -> Noticia | None:
    """Pipeline completo para um blog. Retorna a notícia criada ou None."""
    db = SessionLocal()
    try:
        blog = db.get(Blog, blog_id)
        if blog is None:
            _log(db, None, "pipeline", "erro", f"Blog {blog_id} não encontrado")
            return None
        fontes = json.loads(blog.fontes_rss or "[]")
        if not fontes:
            _log(db, blog.id, "coleta", "erro", "Blog sem fontes RSS configuradas")
            return None

        # 1. Coleta
        itens = coletar_itens(db, blog, fontes)
        if not itens:
            _log(db, blog.id, "coleta", "erro", "Nenhum item coletado nas fontes")
            return None

        # 2. Dedup + relevância
        vistos = {v.url for v in db.scalars(select(Visto).where(Visto.blog_id == blog.id)).all()}
        novos = [i for i in itens if i["link"] and i["link"] not in vistos]
        if not novos:
            _log(db, blog.id, "coleta", "sucesso", "Todos os itens das fontes já haviam sido utilizados")
            return None
        novos.sort(key=lambda i: score_relevancia(i, blog), reverse=True)
        item = novos[0]

        # 3. Redação via LLM (fallback NVIDIA -> Gemini)
        try:
            resposta, provedor = llm_router.gerar_texto(db, _prompt_redacao(blog, item), max_tokens=1600)
        except Exception as exc:  # noqa: BLE001
            _log(db, blog.id, "redacao", "erro", f"Falha na redação: {exc}")
            return None
        dados = _parse_resposta_llm(resposta)
        titulo = str(dados.get("titulo") or item["titulo"]).strip()
        resumo = str(dados.get("resumo") or _limpar(item["resumo"], 240)).strip()
        corpo = str(dados.get("corpo") or resposta).strip()
        _log(db, blog.id, "redacao", "sucesso", f"Notícia redigida via {provedor}: {titulo}")

        noticia = Noticia(
            blog_id=blog.id,
            titulo=titulo,
            resumo=resumo,
            corpo=corpo,
            status="rascunho",
            llm_provider=provedor,
            fonte_url=item["link"],
            fonte_titulo=item["titulo"],
        )
        db.add(noticia)
        db.add(Visto(blog_id=blog.id, url=item["link"]))
        db.commit()
        db.refresh(noticia)

        # 4. Imagem (falha não bloqueia: notícia fica sinalizada "sem imagem")
        try:
            caminho = image_gen.imagem_para_noticia(db, noticia)
            noticia.imagem_url = caminho
            db.commit()
            _log(db, blog.id, "imagem", "sucesso", f"Imagem gerada: {caminho}")
        except Exception as exc:  # noqa: BLE001
            _log(db, blog.id, "imagem", "erro", f"Imagem não gerada: {exc}")

        return noticia
    finally:
        db.close()


def regenerar_noticia(noticia_id: int) -> Noticia | None:
    """Re-roda a redação de uma notícia existente a partir da fonte original."""
    db = SessionLocal()
    try:
        noticia = db.get(Noticia, noticia_id)
        if noticia is None:
            return None
        blog = db.get(Blog, noticia.blog_id)
        if blog is None:
            return None
        if not noticia.fonte_titulo and not noticia.fonte_url:
            _log(db, blog.id, "redacao", "erro", f"Notícia {noticia_id} sem fonte associada")
            return noticia
        prompt = _prompt_redacao(
            blog,
            {"titulo": noticia.fonte_titulo, "resumo": noticia.resumo or noticia.corpo[:300], "link": noticia.fonte_url},
        )
        resposta, provedor = llm_router.gerar_texto(db, prompt, max_tokens=1600)
        dados = _parse_resposta_llm(resposta)
        if dados.get("titulo"):
            noticia.titulo = str(dados["titulo"]).strip()
        if dados.get("resumo"):
            noticia.resumo = str(dados["resumo"]).strip()
        noticia.corpo = str(dados.get("corpo") or resposta).strip()
        noticia.llm_provider = provedor
        db.commit()
        db.refresh(noticia)
        _log(db, blog.id, "redacao", "sucesso", f"Notícia {noticia_id} regenerada via {provedor}")
        return noticia
    finally:
        db.close()

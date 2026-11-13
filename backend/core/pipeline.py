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


TITULO_MAX = 60
META_DESCRIPTION_MAX = 140


def _limpar_titulo(titulo: str) -> str:
    """Título chamativo e dentro do limite de 60 caracteres (SEO)."""
    limpo = " ".join((titulo or "").split())
    if len(limpo) <= TITULO_MAX:
        return limpo
    # corta na última palavra inteira antes do limite, sem reticências no meio
    corte = limpo[:TITULO_MAX]
    if " " in corte:
        corte = corte[: corte.rfind(" ")]
    return corte.rstrip(" ,;:.-")


def _limpar_meta_description(resumo: str) -> str:
    """Meta description sem tags HTML e dentro de 140 caracteres."""
    limpo = re.sub(r"<[^>]+>", " ", resumo or "")
    limpo = " ".join(limpo.split())
    return limpo[:META_DESCRIPTION_MAX].rstrip(" ,;:.-")


def conteudo_publicavel(corpo: str) -> dict:
    """Valida a estrutura HTML semântica exigida pelo AdSense.

    Regra de bloqueio: o corpo precisa ter pelo menos um ``<h2>`` e um ``<p>``.
    Sem isso o post fica sem estrutura de artigo e é recusado na revisão do
    AdSense — então a publicação é bloqueada e a regeneração é orientada.
    """
    texto = corpo or ""
    tem_h2 = bool(re.search(r"<h2[\s>]", texto, re.IGNORECASE))
    tem_p = bool(re.search(r"<p[\s>]", texto, re.IGNORECASE))
    problemas: list[str] = []
    if not tem_h2:
        problemas.append("nenhuma seção <h2>")
    if not tem_p:
        problemas.append("nenhum parágrafo <p>")
    return {
        "ok": tem_h2 and tem_p,
        "problemas": problemas,
        "detalhe": (
            "Conteúdo sem estrutura semântica suficiente para publicar: "
            + "; ".join(problemas)
            + ". Regenere a notícia (o prompt exige <h2>, <p> e conclusão)."
            if problemas
            else ""
        ),
    }


def _prompt_redacao(blog: Blog, item: dict) -> str:
    estilo = (blog.estilo_editorial or "").strip() or "jornalismo claro e direto em português do Brasil"
    return (
        "Você é editor-chefe de um blog de notícias. Escreva uma notícia ORIGINAL em "
        "português do Brasil a partir da fonte abaixo.\n"
        f"Blog: {blog.nome} — tema: {blog.tema} — região: {blog.regiao}\n"
        f"Estilo editorial: {estilo}\n"
        f"Fonte: \"{item['titulo']}\"\n"
        f"Resumo da fonte: {item['resumo']}\n"
        "\n"
        "ESTRUTURA OBRIGATÓRIA (diretriz Google AdSense — artigo profundo e semântico):\n"
        "- Título: chamativo, com NO MÁXIMO 60 caracteres.\n"
        "- Corpo: NO MÍNIMO 1500 palavras. Expanda contexto, implicações e detalhes. "
        "Nunca gere menos de 1000 palavras.\n"
        "- Use tags HTML semânticas no corpo:\n"
        "    <h2> para as seções principais (pelo menos dois);\n"
        "    <h3> para subseções, quando fizer sentido;\n"
        "    <p> para cada parágrafo, com 2 a 3 frases cada;\n"
        "    <ul> ou <ol> para listas, quando couber.\n"
        "- Introdução: 2 parágrafos.\n"
        "- Conclusão: 1 parágrafo explícito, fechando o artigo.\n"
        "- NÃO use <h1>: o título já é o <h1> da página.\n"
        "- NÃO invente fatos que não estejam na fonte.\n"
        "\n"
        "Resposta: SOMENTE JSON válido, sem texto fora dele, no formato\n"
        '  {"titulo": "...", "resumo": "...", "corpo": "<h2>...</h2><p>...</p>"}\n'
        "O campo \"resumo\" é a META DESCRIPTION: até 140 caracteres, sem tags HTML.\n"
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

        # 3. Redação via LLM (fallback NVIDIA -> Gemini) — teto alto p/ diretriz
        # AdSense (mínimo 1500 palavras)
        try:
            resposta, provedor = llm_router.gerar_texto(db, _prompt_redacao(blog, item), max_tokens=4000)
        except Exception as exc:  # noqa: BLE001
            _log(db, blog.id, "redacao", "erro", f"Falha na redação: {exc}")
            return None
        dados = _parse_resposta_llm(resposta)
        titulo = _limpar_titulo(str(dados.get("titulo") or item["titulo"]))
        resumo = _limpar_meta_description(str(dados.get("resumo") or dados.get("meta_description") or item["resumo"]))
        corpo = str(dados.get("corpo") or resposta).strip()

        # Estrutura semântica (diretriz AdSense): bloqueia conteúdo raso
        validacao = conteudo_publicavel(corpo)
        if not validacao["ok"]:
            _log(db, blog.id, "redacao", "erro", validacao["detalhe"])
            return None

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
        resposta, provedor = llm_router.gerar_texto(db, prompt, max_tokens=4000)
        dados = _parse_resposta_llm(resposta)

        titulo = _limpar_titulo(str(dados.get("titulo") or noticia.fonte_titulo or ""))
        resumo = _limpar_meta_description(str(dados.get("resumo") or dados.get("meta_description") or noticia.resumo or ""))
        corpo = str(dados.get("corpo") or resposta).strip()

        validacao = conteudo_publicavel(corpo)
        if not validacao["ok"]:
            _log(db, blog.id, "redacao", "erro", validacao["detalhe"])
            return noticia

        if dados.get("titulo"):
            noticia.titulo = titulo
        if dados.get("resumo") or dados.get("meta_description"):
            noticia.resumo = resumo
        noticia.corpo = corpo
        noticia.llm_provider = provedor
        db.commit()
        db.refresh(noticia)
        _log(db, blog.id, "redacao", "sucesso", f"Notícia {noticia_id} regenerada via {provedor}")
        return noticia
    finally:
        db.close()

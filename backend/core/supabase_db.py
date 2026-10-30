"""Backend opcional Supabase (Fase 6).

Detecção automática de credenciais em SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY
(ambiente — verificação de plataformas) ou na tabela configuracoes (chaves
supabase_url / supabase_service_role_key). Oferece teste de conexão, schema SQL
para o painel do Supabase e migração dos dados locais (SQLite → Supabase).
Serviços opcionais nunca bloqueiam o funcionamento local do app.
"""
from __future__ import annotations

from sqlalchemy import select

TABELAS_ESPERADAS = ("blogs", "noticias", "configuracoes", "logs")

SCHEMA_SQL = """-- PandaNews — schema para Supabase (execute no SQL Editor do painel)
create table if not exists public.blogs (
  id bigint primary key generated always as identity,
  nome text not null,
  tema text not null default 'geral',
  regiao text not null default 'Brasil',
  fontes_rss text not null default '[]',
  estilo_editorial text not null default '',
  frequencia_horas integer not null default 6,
  status text not null default 'ativo',
  created_at timestamptz not null default now()
);

create table if not exists public.noticias (
  id bigint primary key generated always as identity,
  blog_id bigint not null references public.blogs(id) on delete cascade,
  titulo text not null default '',
  corpo text not null default '',
  resumo text not null default '',
  imagem_url text not null default '',
  status text not null default 'rascunho',
  llm_provider text not null default '',
  fonte_url text not null default '',
  fonte_titulo text not null default '',
  created_at timestamptz not null default now()
);

create table if not exists public.configuracoes (
  chave text primary key,
  valor text not null default ''
);

create table if not exists public.logs (
  id bigint primary key generated always as identity,
  blog_id bigint references public.blogs(id) on delete cascade,
  etapa text not null default '',
  status text not null default '',
  mensagem text not null default '',
  created_at timestamptz not null default now()
);
"""


def obter_credenciais() -> dict:
    """Credenciais do Supabase: ambiente tem prioridade; senão, configuracoes."""
    import os

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if url and key:
        return {"url": url, "key": key, "origem": "ambiente"}
    from backend.core.database import Configuracao, SessionLocal

    db = SessionLocal()
    try:
        row_url = db.get(Configuracao, "supabase_url")
        row_key = db.get(Configuracao, "supabase_service_role_key")
        if row_url and row_url.valor and row_key and row_key.valor:
            return {"url": row_url.valor, "key": row_key.valor, "origem": "configuracoes"}
    finally:
        db.close()
    return {"url": "", "key": "", "origem": ""}


def _client():
    from supabase import create_client

    cred = obter_credenciais()
    if not (cred["url"] and cred["key"]):
        raise RuntimeError(
            "Credenciais do Supabase não encontradas. Defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY "
            "no ambiente ou informe-as em Configurações → Banco de dados."
        )
    return create_client(cred["url"], cred["key"])


def _tabela_existe(client, tabela: str) -> bool:
    try:
        client.table(tabela).select("*").limit(1).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "relation" in msg or "does not exist" in msg or "pgrst205" in msg:
            return False
        raise


def testar_conexao() -> dict:
    """Testa a conexão e a existência do schema (sem criar nada sozinho)."""
    client = _client()
    faltando = [t for t in TABELAS_ESPERADAS if not _tabela_existe(client, t)]
    if faltando:
        return {
            "ok": False,
            "detail": f"Conexão ok, mas faltam as tabelas: {', '.join(faltando)}. Execute o schema SQL no painel do Supabase (botão 'Ver schema SQL').",
            "faltando": faltando,
        }
    return {"ok": True, "detail": "Conexão ok e schema encontrado."}


def migrar_do_sqlite() -> dict:
    """Copia blogs, notícias, configurações e logs do SQLite para o Supabase."""
    from backend.core.database import Blog, Configuracao, Log, Noticia, SessionLocal

    client = _client()
    faltando = [t for t in TABELAS_ESPERADAS if not _tabela_existe(client, t)]
    if faltando:
        raise RuntimeError(
            f"Faltam as tabelas no Supabase: {', '.join(faltando)} — execute o schema SQL antes de migrar."
        )

    db = SessionLocal()
    migrados: dict[str, int] = {}
    try:
        blogs = db.scalars(select(Blog)).all()
        if blogs:
            client.table("blogs").upsert(
                [
                    {
                        "id": b.id,
                        "nome": b.nome,
                        "tema": b.tema,
                        "regiao": b.regiao,
                        "fontes_rss": b.fontes_rss,
                        "estilo_editorial": b.estilo_editorial,
                        "frequencia_horas": b.frequencia_horas,
                        "status": b.status,
                        "created_at": b.created_at.isoformat() if b.created_at else None,
                    }
                    for b in blogs
                ]
            ).execute()
        migrados["blogs"] = len(blogs)

        noticias = db.scalars(select(Noticia)).all()
        if noticias:
            client.table("noticias").upsert(
                [
                    {
                        "id": n.id,
                        "blog_id": n.blog_id,
                        "titulo": n.titulo,
                        "corpo": n.corpo,
                        "resumo": n.resumo,
                        "imagem_url": n.imagem_url,
                        "status": n.status,
                        "llm_provider": n.llm_provider,
                        "fonte_url": n.fonte_url or "",
                        "fonte_titulo": n.fonte_titulo or "",
                        "created_at": n.created_at.isoformat() if n.created_at else None,
                    }
                    for n in noticias
                ]
            ).execute()
        migrados["noticias"] = len(noticias)

        confs = db.scalars(select(Configuracao)).all()
        if confs:
            client.table("configuracoes").upsert([{"chave": c.chave, "valor": c.valor} for c in confs]).execute()
        migrados["configuracoes"] = len(confs)

        logs = db.scalars(select(Log).order_by(Log.created_at.desc()).limit(200)).all()
        if logs:
            client.table("logs").upsert(
                [
                    {
                        "id": l.id,
                        "blog_id": l.blog_id,
                        "etapa": l.etapa,
                        "status": l.status,
                        "mensagem": l.mensagem,
                        "created_at": l.created_at.isoformat() if l.created_at else None,
                    }
                    for l in logs
                ]
            ).execute()
        migrados["logs"] = len(logs)
    finally:
        db.close()
    return {"ok": True, "migrados": migrados}

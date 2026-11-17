"""Camada de dados do PandaNews.

SQLite local por padrão (data/pandanews.db) via SQLAlchemy 2.0. Supabase é
detectado via SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY (integração completa na
Fase 6). Tabelas: blogs, noticias, configuracoes, logs.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from backend.core.config import DB_PATH, DB_URL

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_engine_kwargs: dict = {}
if DB_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DB_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Blog(Base):
    __tablename__ = "blogs"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Multi-tenancy: dono do registo (e-mail do utilizador = `sub` do JWT).
    user_id: Mapped[str] = mapped_column(String(200), default="", index=True)
    nome: Mapped[str] = mapped_column(String(200))
    tema: Mapped[str] = mapped_column(String(50), default="geral")
    regiao: Mapped[str] = mapped_column(String(100), default="Brasil")
    fontes_rss: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    estilo_editorial: Mapped[str] = mapped_column(Text, default="")
    frequencia_horas: Mapped[int] = mapped_column(default=6)
    status: Mapped[str] = mapped_column(String(20), default="ativo")  # ativo | pausado
    created_at: Mapped[datetime] = mapped_column(default=_now)


class Noticia(Base):
    __tablename__ = "noticias"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(200), default="", index=True)
    blog_id: Mapped[int] = mapped_column(ForeignKey("blogs.id"), index=True)
    titulo: Mapped[str] = mapped_column(String(300), default="")
    corpo: Mapped[str] = mapped_column(Text, default="")
    resumo: Mapped[str] = mapped_column(Text, default="")
    imagem_url: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="rascunho", index=True)
    llm_provider: Mapped[str] = mapped_column(String(50), default="")
    wordpress_post_id: Mapped[int | None] = mapped_column(nullable=True)
    fonte_url: Mapped[str] = mapped_column(String(600), default="")
    fonte_titulo: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)


class Visto(Base):
    """Itens de feed já utilizados por blog (dedup do pipeline)."""

    __tablename__ = "vistos"

    id: Mapped[int] = mapped_column(primary_key=True)
    blog_id: Mapped[int] = mapped_column(ForeignKey("blogs.id"), index=True)
    url: Mapped[str] = mapped_column(String(600))
    created_at: Mapped[datetime] = mapped_column(default=_now)


class Configuracao(Base):
    __tablename__ = "configuracoes"

    # Chave composta: cada utilizador tem o seu próprio conjunto de settings.
    user_id: Mapped[str] = mapped_column(String(200), primary_key=True, default="")
    chave: Mapped[str] = mapped_column(String(100), primary_key=True)
    valor: Mapped[str] = mapped_column(Text, default="")


class Usuario(Base):
    """Utilizador local do painel (login por e-mail + senha).

    A senha nunca é guardada em texto plano: só o hash bcrypt. O utilizador
    padrão é criado no primeiro arranque (ver ``init_db``).
    """

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(Text, default="")
    criado_em: Mapped[datetime] = mapped_column(default=_now)


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    blog_id: Mapped[int | None] = mapped_column(ForeignKey("blogs.id"), nullable=True, index=True)
    etapa: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)  # sucesso | erro
    mensagem: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    # o utilizador padrão tem de existir ANTES da migração: os dados antigos
    # são atribuídos ao primeiro utilizador (regra de multi-tenancy).
    _criar_usuario_padrao()
    _migrate()


# Utilizador local padrão — criado só no primeiro arranque. A senha inicial
# vem do ambiente (PANDANEWS_SENHA_INICIAL) e, em falta dela, do default
# documentado; o hash bcrypt é gerado aqui e a plaintecido nunca é guardada.
USUARIO_PADRAO_EMAIL = "dan.hachuel@gmail.com"
USUARIO_PADRAO_SENHA = "123456"


def _criar_usuario_padrao() -> None:
    import os

    from sqlalchemy import select

    import bcrypt

    db = SessionLocal()
    try:
        if db.scalars(select(Usuario)).first() is not None:
            return
        senha_inicial = os.environ.get("PANDANEWS_SENHA_INICIAL") or USUARIO_PADRAO_SENHA
        hash_ = bcrypt.hashpw(senha_inicial.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        db.add(Usuario(email=USUARIO_PADRAO_EMAIL, senha_hash=hash_))
        db.commit()
    finally:
        db.close()


def _primeiro_utilizador_email() -> str:
    """E-mail do primeiro utilizador — dono dos dados anteriores ao multi-tenant."""
    from sqlalchemy import select

    db = SessionLocal()
    try:
        usuario = db.scalars(select(Usuario).order_by(Usuario.id)).first()
        return usuario.email if usuario is not None else USUARIO_PADRAO_EMAIL
    finally:
        db.close()


def _migrate() -> None:
    """Migrações leves para bancos existentes (SQLite).

    Multi-tenancy: adiciona ``user_id`` a blogs/noticias e transforma a PK de
    ``configuracoes`` em composta ``(user_id, chave)`` — o SQLite não permite
    ``ALTER TABLE ADD COLUMN ... PRIMARY KEY``, por isso a tabela é
    reconstruída. No fim, os registos antigos são atribuídos ao primeiro
    utilizador, para que ninguém perca o histórico ao actualizar.
    """
    if not DB_URL.startswith("sqlite"):
        return
    from sqlalchemy import text

    dono = _primeiro_utilizador_email()

    with engine.connect() as conn:
        # --- noticias: colunas antigas + user_id ---
        colunas = [row[1] for row in conn.execute(text("PRAGMA table_info(noticias)"))]
        for coluna, ddl in (
            ("fonte_url", "VARCHAR(600) DEFAULT ''"),
            ("fonte_titulo", "TEXT DEFAULT ''"),
            ("wordpress_post_id", "INTEGER"),
        ):
            if coluna not in colunas:
                conn.execute(text(f"ALTER TABLE noticias ADD COLUMN {coluna} {ddl}"))
        if "user_id" not in colunas:
            conn.execute(text("ALTER TABLE noticias ADD COLUMN user_id VARCHAR(200) DEFAULT ''"))
        conn.execute(text("UPDATE noticias SET user_id = :dono WHERE user_id = '' OR user_id IS NULL"), {"dono": dono})

        # --- blogs: user_id ---
        colunas_blogs = [row[1] for row in conn.execute(text("PRAGMA table_info(blogs)"))]
        if "user_id" not in colunas_blogs:
            conn.execute(text("ALTER TABLE blogs ADD COLUMN user_id VARCHAR(200) DEFAULT ''"))
        conn.execute(text("UPDATE blogs SET user_id = :dono WHERE user_id = '' OR user_id IS NULL"), {"dono": dono})

        # --- configuracoes: PK composta (user_id, chave) ---
        colunas_conf = [row[1] for row in conn.execute(text("PRAGMA table_info(configuracoes)"))]
        if "user_id" not in colunas_conf:
            conn.execute(text(
                "CREATE TABLE configuracoes_nova ("
                "user_id VARCHAR(200) NOT NULL DEFAULT '', "
                "chave VARCHAR(100) NOT NULL, "
                "valor TEXT DEFAULT '', "
                "PRIMARY KEY (user_id, chave))"
            ))
            conn.execute(text(
                "INSERT INTO configuracoes_nova (user_id, chave, valor) "
                "SELECT :dono, chave, valor FROM configuracoes"
            ), {"dono": dono})
            conn.execute(text("DROP TABLE configuracoes"))
            conn.execute(text("ALTER TABLE configuracoes_nova RENAME TO configuracoes"))

        conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

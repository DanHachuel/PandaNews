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
    blog_id: Mapped[int] = mapped_column(ForeignKey("blogs.id"), index=True)
    titulo: Mapped[str] = mapped_column(String(300), default="")
    corpo: Mapped[str] = mapped_column(Text, default="")
    resumo: Mapped[str] = mapped_column(Text, default="")
    imagem_url: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="rascunho", index=True)
    llm_provider: Mapped[str] = mapped_column(String(50), default="")
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

    chave: Mapped[str] = mapped_column(String(100), primary_key=True)
    valor: Mapped[str] = mapped_column(Text, default="")


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
    _migrate()


def _migrate() -> None:
    """Migrações leves para bancos existentes (SQLite)."""
    if not DB_URL.startswith("sqlite"):
        return
    from sqlalchemy import text

    with engine.connect() as conn:
        colunas = [row[1] for row in conn.execute(text("PRAGMA table_info(noticias)"))]
        for coluna, ddl in (
            ("fonte_url", "VARCHAR(600) DEFAULT ''"),
            ("fonte_titulo", "TEXT DEFAULT ''"),
        ):
            if coluna not in colunas:
                conn.execute(text(f"ALTER TABLE noticias ADD COLUMN {coluna} {ddl}"))
        conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

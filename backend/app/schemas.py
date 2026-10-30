"""Schemas Pydantic do PandaNews (entrada e saída das rotas)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

TEMAS = ["geral", "esporte", "politica", "economia", "tecnologia"]
STATUS_BLOG = ["ativo", "pausado"]
STATUS_NOTICIA = ["rascunho", "aprovado", "rejeitado", "publicado"]


class BlogIn(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    tema: str = "geral"
    regiao: str = "Brasil"
    fontes_rss: List[str] = []
    estilo_editorial: str = ""
    frequencia_horas: int = Field(default=6, ge=1, le=168)
    status: str = "ativo"


class BlogPatch(BaseModel):
    nome: Optional[str] = None
    tema: Optional[str] = None
    regiao: Optional[str] = None
    fontes_rss: Optional[List[str]] = None
    estilo_editorial: Optional[str] = None
    frequencia_horas: Optional[int] = Field(default=None, ge=1, le=168)
    status: Optional[str] = None


class NoticiaPatch(BaseModel):
    titulo: Optional[str] = None
    corpo: Optional[str] = None
    resumo: Optional[str] = None
    status: Optional[str] = None


class ConfiguracoesPatch(BaseModel):
    nvidia_api_key: Optional[str] = None
    nvidia_base_url: Optional[str] = None
    nvidia_model: Optional[str] = None
    google_api_key: Optional[str] = None
    google_base_url: Optional[str] = None
    google_model: Optional[str] = None
    llm_fallback_ordem: Optional[str] = None
    supabase_url: Optional[str] = None
    supabase_service_role_key: Optional[str] = None
    db_backend: Optional[str] = None
    scheduler_ativo: Optional[bool] = None
    intervalo_padrao_horas: Optional[int] = Field(default=None, ge=1, le=168)
    meta_diaria: Optional[int] = Field(default=None, ge=0, le=100)


class LlmTestIn(BaseModel):
    provider: str  # nvidia | google


class BlogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    tema: str
    regiao: str
    fontes_rss: List[str]
    estilo_editorial: str
    frequencia_horas: int
    status: str
    created_at: datetime

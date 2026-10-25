"""Páginas legais e de verificação (/legal) — estáticas.

Servem como URL de verificação do app junto aos provedores de API
(Google Gemini, NVIDIA NIM, Supabase) e como documentos legais oficiais.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.core.config import LEGAL_DIR

router = APIRouter(prefix="/legal", tags=["legal"])

ARQUIVOS_PERMITIDOS = {"index.html", "terms.html", "privacy.html"}


def _servir(nome: str) -> FileResponse:
    if nome not in ARQUIVOS_PERMITIDOS:
        raise HTTPException(status_code=404, detail="Página não encontrada")
    caminho = LEGAL_DIR / nome
    if not caminho.exists():
        raise HTTPException(status_code=404, detail="Página não encontrada")
    return FileResponse(caminho, media_type="text/html; charset=utf-8")


@router.get("")
@router.get("/")
def legal_index() -> FileResponse:
    return _servir("index.html")


@router.get("/{nome}")
def legal_pagina(nome: str) -> FileResponse:
    return _servir(nome)

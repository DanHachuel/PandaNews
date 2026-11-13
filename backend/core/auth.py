"""Autenticação local do painel PandaNews (login por e-mail + senha).

Sem provedor externo e sem travas de pré-registo: o primeiro arranque cria o
utilizador padrão e o login valida a senha contra o hash bcrypt. O token é um
JWT assinado localmente (HS256) com validade de 24h — o painel é single-user
e roda em 127.0.0.1.

A chave de assinatura vive em ``~/.pandanews/data/jwt.secret``: gerada no
primeiro arranque, com permissão restrita, e NUNCA versionada. Trocar a chave
invalida tokens emitidos antes — para um painel local, o utilizador apenas
entra de novo.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import jwt

from backend.core.config import DATA_DIR

logger = logging.getLogger("uvicorn.error.pandanews")

TOKEN_HORAS = 24
ALGORITMO = "HS256"
SECRET_FILE = "jwt.secret"

# Chave de assinatura: gerida uma vez e guardada fora do código.
_secret_cache: str | None = None


def _secret_path() -> Path:
    return DATA_DIR / SECRET_FILE


def _secret() -> str:
    global _secret_cache
    if _secret_cache:
        return _secret_cache
    path = _secret_path()
    if path.exists():
        secreto = path.read_text(encoding="utf8").strip()
        if secreto:
            _secret_cache = secreto
            return secreto
    # primeiro arranque: gera e guarda com permissão restrita
    secreto = bcrypt.gensalt(24).hex() + bcrypt.gensalt(24).hex()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(secreto, encoding="utf8")
    try:
        os.chmod(path, 0o600)
    except OSError as exc:  # Windows pode não suportar chmod
        logger.warning("auth: nao foi possivel restringir %s (%s)", path, exc)
    _secret_cache = secreto
    return secreto


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def senha_confere(senha: str, hash_: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), (hash_ or "").encode("utf-8"))
    except (ValueError, TypeError):
        return False


def gerar_token(email: str) -> str:
    expira = datetime.now(timezone.utc) + timedelta(hours=TOKEN_HORAS)
    payload = {"sub": email, "exp": expira, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, _secret(), algorithm=ALGORITMO)


def email_do_token(token: str) -> str | None:
    """Devolve o e-mail do token, ou None se inválido/expirado."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, _secret(), algorithms=[ALGORITMO])
    except jwt.ExpiredSignatureError:
        logger.info("auth: token expirado")
        return None
    except jwt.InvalidTokenError:
        return None
    email = payload.get("sub")
    return str(email) if email else None

"""Autenticação (/api/v1/auth): login e troca de senha do painel local."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core import auth as auth_core
from backend.core.database import Usuario, get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    senha: str = Field(min_length=1, max_length=200)


class SenhaIn(BaseModel):
    senha_atual: str = Field(min_length=1, max_length=200)
    senha_nova: str = Field(min_length=6, max_length=200, description="mínimo 6 caracteres")


class RegistroIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    senha: str = Field(min_length=6, max_length=200, description="mínimo 6 caracteres")


def usuario_atual(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Usuario:
    """Dependência de rota protegida: 401 sem token válido."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Token não informado.")
    esquema, _, token = authorization.partition(" ")
    if esquema.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Cabeçalho Authorization inválido.")
    email = auth_core.email_do_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Sessão expirada ou inválida — entre novamente.")
    usuario = db.scalars(select(Usuario).where(Usuario.email == email)).first()
    if usuario is None:
        raise HTTPException(status_code=401, detail="Utilizador não encontrado.")
    return usuario


def user_id_de(usuario: Usuario) -> str:
    """`user_id` do dono dos dados = o e-mail (o `sub` do JWT).

    Usado por todos os endpoints protegidos para filtrar as consultas:
    nenhum utilizador vê dados de outro (prevenção de IDOR).
    """
    return usuario.email


@router.get("/status")
def status(db: Session = Depends(get_db)) -> dict:
    """Estado da sessão — usado pelo frontend para validar um token guardado."""
    total = len(db.scalars(select(Usuario)).all())
    return {"autenticado": False, "usuarios": total, "exige_login": total > 0}


@router.post("/login")
def login(payload: LoginIn, db: Session = Depends(get_db)) -> dict:
    usuario = db.scalars(
        select(Usuario).where(Usuario.email == payload.email.strip().lower())
    ).first()
    # mensagem genérica: não revela se o e-mail existe
    if usuario is None or not auth_core.senha_confere(payload.senha, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")
    return {"ok": True, "token": auth_core.gerar_token(usuario.email), "email": usuario.email}


@router.post("/registro")
def registro(payload: RegistroIn, db: Session = Depends(get_db)) -> dict:
    """Cria uma conta nova (SaaS multi-tenant) e devolve o token de sessão.

    Cada conta passa a ver apenas os dados dela: o `user_id` usado no banco é
    o próprio e-mail (o `sub` do JWT).
    """
    email = payload.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Informe um e-mail válido.")
    existente = db.scalars(select(Usuario).where(Usuario.email == email)).first()
    if existente is not None:
        raise HTTPException(status_code=409, detail="Este e-mail já tem uma conta — entre com ela.")
    usuario = Usuario(email=email, senha_hash=auth_core.hash_senha(payload.senha))
    db.add(usuario)
    db.commit()
    return {"ok": True, "token": auth_core.gerar_token(email), "email": email}


@router.get("/eu")
def eu(usuario: Usuario = Depends(usuario_atual)) -> dict:
    return {"email": usuario.email, "criado_em": usuario.criado_em.isoformat() if usuario.criado_em else None}


@router.post("/alterar-senha")
def alterar_senha(
    payload: SenhaIn,
    usuario: Usuario = Depends(usuario_atual),
    db: Session = Depends(get_db),
) -> dict:
    if not auth_core.senha_confere(payload.senha_atual, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="Senha atual incorreta.")
    if payload.senha_nova == payload.senha_atual:
        raise HTTPException(status_code=400, detail="A nova senha precisa ser diferente da atual.")
    usuario.senha_hash = auth_core.hash_senha(payload.senha_nova)
    db.commit()
    return {"ok": True, "detail": "Senha alterada."}

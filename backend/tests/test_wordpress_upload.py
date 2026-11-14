"""Teste do upload de imagem em 2 etapas do WordPress (stub).

Roda sem pytest e sem servidor: `python backend/tests/test_wordpress_upload.py`.

Objectivo (a implementar): validar o contrato REST do publicador
(`backend/core/wordpress_publisher.py`) contra um `httpx` interceptado:

  1. `POST /wp-json/wp/v2/media` recebe o **binário** da imagem (corpo em bytes,
     Content-Type do arquivo) e devolve um `id`;
  2. `POST /wp-json/wp/v2/posts` usa `featured_media` com exactamente o `id`
     devolvido pela etapa 1 — nunca um id inventado;
  3. `status: 'publish'` e a categoria resolvida pelo tema do blog (busca ou
     cria) estão no payload;
  4. republicação é bloqueada antes de qualquer chamada HTTP;
  5. autenticação por Basic Auth com Application Password — a senha de login
     do admin nunca é usada.

A cobertura actual do payload WordPress vive em `backend/tests/test_seo_auth.py`;
este stub existe para o contrato de upload de mídia ter arquivo próprio.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Stub do módulo de banco: credenciais WordPress são lidas via `get_config`,
# que não precisa de SQLAlchemy a correr.
if "backend.core.database" not in sys.modules:
    import types

    _stub = types.ModuleType("backend.core.database")
    _stub.Configuracao = type("Configuracao", (), {})
    _stub.get_db = lambda: None
    sys.modules["backend.core.database"] = _stub

falhas: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(f"{'PASS' if cond else 'FAIL'} — {msg}")
    if not cond:
        falhas.append(msg)


# ------------------------------------------------------------- veredicto

print()
if falhas:
    print(f"Upload WordPress: {len(falhas)} verificação(ões) falharam.")
    sys.exit(1)
print("Upload WordPress: stub sem verificações (cobertura actual em backend/tests/test_seo_auth.py).")
sys.exit(0)
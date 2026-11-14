"""Teste de keepalive do runtime Windows (stub).

Roda sem pytest e sem servidor: `python backend/tests/test_windows_keepalive.py`.

Objectivo (a implementar): provar que o launcher mantém o backend vivo sem abrir
janela de console e sem perder o lock global em `~/.pandanews/pandanews.pid`:

  1. o lock global regista launcher, backend e porta, e sobrevive à atualização
     do pacote npm (fora da pasta do cache do `npx`);
  2. `matarInstanciasAntigas` encerra o PID anterior antes do novo bind e nunca
     mata o próprio `process.pid`;
  3. nenhum `spawn`/`spawnSync` do launcher nasce sem `windowsHide: true`;
  4. o watchdog tem teto duro de reinícios (`MAX_REINICIOS`) e sai com `exit(1)`
     em vez de empilhar processos.

Enquanto este arquivo é stub, a barreira automática equivalente é
`scripts/test-start-isolation.mjs` (51 verificações, rodado no CI). Este stub
existe para a cobertura Python do ciclo de vida não ser esquecida.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Stub do módulo de banco: o ciclo de vida do launcher é Node.js — este teste
# não precisa de SQLAlchemy a correr.
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
    print(f"Keepalive do runtime Windows: {len(falhas)} verificação(ões) falharam.")
    sys.exit(1)
print("Keepalive do runtime Windows: stub sem verificações (cobertura em scripts/test-start-isolation.mjs).")
sys.exit(0)
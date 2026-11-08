"""Teste funcional do fallback implacável do router de LLM.

Roda sem pytest e sem servidor: `python backend/tests/test_llm_fallback.py`.

Cobre exatamente o que a correção promete:
  1. NVIDIA devolve HTTP 410 (modelo em fim de vida) -> o Gemini assume,
     sem exceção vazando para o pipeline.
  2. A mensagem de log é a pedida: "Erro na NVIDIA (...). Acionando Google
     Gemini..."
  3. Todos os provedores falhando -> RuntimeError clara (não silenciosa).
  4. `test_provider` devolve a string de erro do provedor ( HTTP 410/404 ),
     marcando `degraded`, para o frontend exibir.
"""
from __future__ import annotations

import logging
import sys
from datetime import timedelta as _timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# O teste não precisa de banco: `llm_router.get_config` importa
# `backend.core.database` de forma preguiçosa (dentro da função), o que
# exigiria SQLAlchemy só para rodar os assertions. Um stub do módulo mantém
# o teste autônomo — sem servidor, sem pytest, sem dependências extras.
import types  # noqa: E402

if "backend.core.database" not in sys.modules:
    _stub = types.ModuleType("backend.core.database")

    class _ConfiguracaoStub:  # noqa: D401 - apenas um marcador para o .get()
        """Stub: o FakeDB abaixo responde ao `.get()` sem tocar no ORM."""

    _stub.Configuracao = _ConfiguracaoStub
    sys.modules["backend.core.database"] = _stub

from backend.core import llm_router  # noqa: E402


class _Row:
    def __init__(self, valor: str) -> None:
        self.valor = valor


class FakeDB:
    """Banco mínimo: só o que provider_config()/get_config() precisam."""

    def __init__(self, valores: dict[str, str]) -> None:
        self.valores = valores

    def get(self, _modelo, chave: str):
        return _Row(self.valores[chave]) if chave in self.valores else None


def _db_com_chaves() -> FakeDB:
    return FakeDB(
        {
            "nvidia_api_key": "nv-test",
            "nvidia_model": "meta/llama-3.3-70b-instruct",  # EOL de propósito
            "google_api_key": "go-test",
            "google_model": "gemini-3.8-flash",
            "llm_fallback_ordem": "nvidia,google",
        }
    )


falhas: list[str] = []


def check(condicao: bool, mensagem: str) -> None:
    print(f"{'PASS' if condicao else 'FAIL'} — {mensagem}")
    if not condicao:
        falhas.append(mensagem)


# ------------------------------------------------------- 1) fallback no 410

class _Resposta410:
    """Simula httpx.HTTPStatusError do raise_for_status() num 410."""

    status_code = 410


def _chamar_nvidia_410(db, provider, prompt, max_tokens):
    if provider == "nvidia":
        raise RuntimeError("410 Gone: modelo 'meta/llama-3.3-70b-instruct' chegou ao fim da vida")
    return "noticia gerada pelo gemini", "gemini-3.8-flash"


original_chamar = llm_router.chamar_provedor
llm_router.chamar_provedor = _chamar_nvidia_410

registros: list[str] = []


class _Capturador(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        registros.append(record.getMessage())


llm_router.logger.addHandler(_Capturador())
llm_router.logger.setLevel(logging.INFO)

texto, provedor = llm_router.gerar_texto(_db_com_chaves(), "escreva uma noticia")

check(provedor == "google", "NVIDIA com 410 -> o Gemini assume (provedor devolvido: google)")
check("noticia gerada pelo gemini" in texto, "o texto devolvido é o do Gemini, não uma exceção")

mensagem_esperada = "Erro na NVIDIA (410 Gone"
check(
    any(mensagem_esperada in m and "Acionando Google Gemini" in m for m in registros),
    f"log no formato pedido: 'Erro na NVIDIA ({{e}}). Acionando Google Gemini...' — obtido: {registros}",
)

# --------------------------------------------- 2) todos falham -> erro claro

def _chamar_todos_falham(db, provider, prompt, max_tokens):
    raise RuntimeError(f"{provider} fora do ar")


llm_router.chamar_provedor = _chamar_todos_falham
try:
    llm_router.gerar_texto(_db_com_chaves(), "prompt")
    check(False, "todos os provedores falhando devolve RuntimeError")
except RuntimeError as exc:
    check(
        "Todos os provedores de LLM falharam" in str(exc),
        "todos os provedores falhando -> RuntimeError clara (sem silêncio)",
    )

llm_router.chamar_provedor = original_chamar

# ------------------------------------------- 3) test_provider devolve o erro

class _FakeResponse:
    def __init__(self, status_code: int, texto: str) -> None:
        self.status_code = status_code
        self.text = texto
        self.elapsed = _timedelta(milliseconds=42)


def _testar_com_resposta(status_code: int, texto: str) -> dict:
    class _ClientFake:
        def __init__(self, *a, **k) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            return _FakeResponse(status_code, texto)

    llm_router.httpx.Client = _ClientFake
    return llm_router.test_provider(_db_com_chaves(), "nvidia")


resultado_410 = _testar_com_resposta(
    410, '{"detail":"The model has reached its end of life"}'
)
check(resultado_410["ok"] is False, "test_provider: HTTP 410 -> ok=False")
check(resultado_410.get("degraded") is True, "test_provider: HTTP 410 -> degraded=True (fallback avisa)")
check(
    "fim da vida" in resultado_410["detail"] or "410" in resultado_410["detail"],
    "test_provider: a string de erro do provedor volta no JSON para a tela",
)

resultado_401 = _testar_com_resposta(401, "unauthorized")
check(
    "recusou a API key" in resultado_401["detail"],
    "test_provider: HTTP 401 -> mensagem de credencial explícita",
)

resultado_500 = _testar_com_resposta(500, "internal error")
check(
    "HTTP 500" in resultado_500["detail"],
    "test_provider: HTTP 500 -> código e corpo devolvidos ao frontend",
)

# ------------------------------------------- 4) endpoint replicado do Thunderbolt

check(
    llm_router.chat_completions_endpoint("https://integrate.api.nvidia.com/v1")
    == "https://integrate.api.nvidia.com/v1/chat/completions",
    "endpoint: base '/v1' -> '/v1/chat/completions' (igual ao Thunderbolt)",
)
check(
    llm_router.chat_completions_endpoint("https://integrate.api.nvidia.com/v1/models")
    == "https://integrate.api.nvidia.com/v1/chat/completions",
    "endpoint: base com '/models' não duplica o sufixo (evita 404)",
)
check(
    llm_router.chat_completions_endpoint("https://integrate.api.nvidia.com/v1/chat/completions")
    == "https://integrate.api.nvidia.com/v1/chat/completions",
    "endpoint: base já com '/chat/completions' não duplica (evita 404)",
)
headers = llm_router._headers("chave-abc")
check(
    headers.get("Authorization") == "Bearer chave-abc"
    and headers.get("Content-Type") == "application/json"
    and headers.get("Accept") == "application/json",
    "headers OpenAI-compatible: Bearer + Content-Type + Accept (como o Thunderbolt)",
)

# ------------------------------------------------------------- veredicto

print()
if falhas:
    print(f"Fallback do router LLM: {len(falhas)} verificação(ões) falharam.")
    sys.exit(1)
print("Fallback do router LLM: todas as verificações passaram.")
sys.exit(0)

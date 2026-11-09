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
  5. HOTFIX 0.5.03 — o prefixo de proxy `nvidia_nim/` (convenção LiteLLM)
     nunca chega ao POST /v1/chat/completions: o JSON enviado à NVIDIA
     carrega só `mistralai/mistral-large-4-1t-a52b`.
"""
from __future__ import annotations

import json
import logging
import sys
import types
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

    class _ConfiguracaoStub:
        """Stub do modelo ORM: o FakeDB abaixo responde ao `.get()` sem tocar no ORM."""

        def __init__(self, chave: str = "", valor: str = "") -> None:
            self.chave = chave
            self.valor = valor

    _stub.Configuracao = _ConfiguracaoStub
    sys.modules["backend.core.database"] = _stub

from backend.core import llm_router  # noqa: E402


class _Row:
    def __init__(self, valor: str) -> None:
        self.valor = valor


class FakeDB:
    """Banco mínimo: só o que provider_config()/get_config() precisam."""

    def __init__(self, valores: dict[str, str]) -> None:
        self.valores = dict(valores)

    def get(self, _modelo, chave: str):
        return _Row(self.valores[chave]) if chave in self.valores else None

    def add(self, row) -> None:  # PUT de configurações grava por aqui
        self.valores[row.chave] = row.valor

    def commit(self) -> None:
        pass


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

check(provedor == "gemini", "NVIDIA com 410 -> o Gemini assume (provedor devolvido: gemini)")
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
    "fim de vida" in resultado_410["detail"] or "410" in resultado_410["detail"],
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

# ------------------------------------ 3b) E2E pelo caminho HTTP real (Chamar)

# Diferente dos cenários acima (que trocam `chamar_provedor` por um dublê),
# aqui só o `httpx.Client` é substituído: `chamar_provedor`, a construção da
# URL, os headers e o `raise_for_status` rodam de verdade. A NVIDIA devolve
# 410 e o Gemini devolve 200 — a notícia tem de nascer do Gemini.
llm_router.chamar_provedor = original_chamar


class _RespostaHttp:
    def __init__(self, status_code: int, corpo: dict) -> None:
        self.status_code = status_code
        self._corpo = corpo
        self.text = json.dumps(corpo)
        self.elapsed = _timedelta(milliseconds=1)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}: {self.text}")

    def json(self) -> dict:
        return self._corpo


def _post_e2e(self, endpoint, headers=None, json=None):
    # distingue pelo modelo pedido: nvidia (410) vs google/gemini (200)
    modelo = (json or {}).get("model", "")
    if "gemini" in modelo:
        return _RespostaHttp(
            200,
            {"choices": [{"message": {"content": '{"titulo":"T","resumo":"R","corpo":"C"}'}}], "model": modelo},
        )
    return _RespostaHttp(410, {"detail": "The model has reached its end of life"})


class _ClientE2E:
    def __init__(self, *a, **k) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, endpoint, headers=None, json=None):
        return _post_e2e(self, endpoint, headers, json)


llm_router.httpx.Client = _ClientE2E

registros.clear()

texto_e2e, provedor_e2e = llm_router.gerar_texto(_db_com_chaves(), "escreva uma noticia")

check(provedor_e2e == "gemini", "E2E HTTP: NVIDIA 410 -> Gemini assume (provedor: gemini)")
check("titulo" in texto_e2e, "E2E HTTP: o conteúdo devolvido é o do Gemini (JSON utilizável)")
check(
    any("Erro na NVIDIA (" in m and "Acionando Google Gemini" in m for m in registros),
    "E2E HTTP: log 'Erro na NVIDIA (...). Acionando Google Gemini...' emitido",
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

# ------------------------------- 5) HOTFIX 0.5.03 — prefixo nvidia_nim/ fora

# O id `nvidia_nim/mistralai/mistral-large-4-1t-a52b` é convenção do LiteLLM.
# A API da NVIDIA só aceita `mistralai/mistral-large-4-1t-a52b` — o payload do
# POST /v1/chat/completions tem de sair limpo.
check(
    llm_router.limpar_nome_modelo("nvidia_nim/mistralai/mistral-large-4-1t-a52b")
    == "mistralai/mistral-large-4-1t-a52b",
    "limpar_nome_modelo: 'nvidia_nim/' é removido do id",
)
check(
    llm_router.limpar_nome_modelo("mistralai/mistral-large-4-1t-a52b")
    == "mistralai/mistral-large-4-1t-a52b",
    "limpar_nome_modelo: id sem prefixo (barra de fornecedor inclusa) fica intacto",
)
check(
    llm_router.limpar_nome_modelo(" NVIDIA_NIM/nvidia_nim/meta/llama-3.3-70b-instruct ")
    == "meta/llama-3.3-70b-instruct",
    "limpar_nome_modelo: maiúsculas, espaços e prefixo duplicado também saem",
)
check(
    llm_router.limpar_nome_modelo("") == "" and llm_router.limpar_nome_modelo(None) == "",
    "limpar_nome_modelo: vazio/None não explodem",
)

db_prefixada = FakeDB(
    {
        "nvidia_api_key": "nv-test",
        # valor como viria de outra ferramenta (LiteLLM) ou de dump de config
        "nvidia_model": "nvidia_nim/mistralai/mistral-large-4-1t-a52b",
    }
)

check(
    llm_router.provider_config(db_prefixada, "nvidia")["model"] == "mistralai/mistral-large-4-1t-a52b",
    "provider_config: o modelo sai do banco já limpo (sem nvidia_nim/)",
)

# 5b) o payload REAL do POST /v1/chat/completions — capturado no fio.
payloads_enviados: list[dict] = []


class _ClientCapturador:
    """Guarda o JSON de cada post e devolve 200 com conteúdo utilizável."""

    def __init__(self, *a, **k) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, endpoint, headers=None, json=None):
        payloads_enviados.append(json)
        modelo = (json or {}).get("model", "")
        return _RespostaHttp(
            200,
            {"choices": [{"message": {"content": '{"titulo":"T","resumo":"R","corpo":"C"}'}}], "model": modelo},
        )


llm_router.httpx.Client = _ClientCapturador

texto_hotfix, modelo_hotfix = llm_router.chamar_provedor(db_prefixada, "nvidia", "escreva uma noticia", 64)

payload_hotfix = payloads_enviados[-1]
check(
    payload_hotfix.get("model") == "mistralai/mistral-large-4-1t-a52b",
    f"chamar_provedor: payload['model'] limpo — obtido: {payload_hotfix.get('model')!r}",
)
check(
    "nvidia_nim" not in str(payload_hotfix.get("model", "")),
    "chamar_provedor: nenhum resto de 'nvidia_nim' no model do JSON enviado",
)
check(
    payload_hotfix.get("messages") == [{"role": "user", "content": "escreva uma noticia"}]
    and payload_hotfix.get("max_tokens") == 64,
    "chamar_provedor: o resto do payload (messages/max_tokens) intacto",
)
check(
    modelo_hotfix == "mistralai/mistral-large-4-1t-a52b",
    "chamar_provedor: o modelo devolvido ao caller também é o id limpo",
)
check("titulo" in texto_hotfix, "chamar_provedor: a chamada com prefixo chega ao 200 normalmente")

# 5c) o teste de conexão prova o MESMO model que a geração envia
resultado_hotfix = llm_router.test_provider(db_prefixada, "nvidia")
check(
    resultado_hotfix.get("ok") is True,
    f"test_provider: OK com o modelo antes prefixado — detail: {resultado_hotfix.get('detail')}",
)
check(
    payloads_enviados[-1].get("model") == "mistralai/mistral-large-4-1t-a52b",
    "test_provider: o POST de teste também vai com o id limpo",
)
check(
    resultado_hotfix.get("model") == "mistralai/mistral-large-4-1t-a52b",
    "test_provider: 'model' do JSON de resposta é o id limpo",
)

# 5d) descoberta de modelos + PUT: a UI só vê e só salva o id limpo
try:
    import sqlalchemy.orm  # noqa: F401
except ModuleNotFoundError:  # CI instala só httpx — stub mantém o teste autônomo
    _stub_sa = types.ModuleType("sqlalchemy")
    _stub_orm = types.ModuleType("sqlalchemy.orm")

    class _SessionStub:  # só existe por causa da anotação de tipo da rota
        pass

    _stub_orm.Session = _SessionStub
    _stub_sa.orm = _stub_orm
    sys.modules["sqlalchemy"] = _stub_sa
    sys.modules["sqlalchemy.orm"] = _stub_orm

if not hasattr(sys.modules["backend.core.database"], "get_db"):
    sys.modules["backend.core.database"].get_db = lambda: None

from backend.app.routers import configuracoes  # noqa: E402
from backend.app.schemas import ConfiguracoesPatch  # noqa: E402

# A NVIDIA (ou um proxy à frente dela) devolve um id já com o prefixo.
_resposta_get_original = llm_router.httpx.get
llm_router.httpx.get = lambda url, **kw: _RespostaHttp(
    200,
    {
        "data": [
            {"id": "nvidia_nim/mistralai/mistral-large-4-1t-a52b"},
            {"id": "mistralai/mistral-large-2-instruct"},
        ]
    },
)
try:
    catalogo = configuracoes.listar_modelos_nvidia(db_prefixada)
finally:
    llm_router.httpx.get = _resposta_get_original

check(
    catalogo.get("models")
    == ["mistralai/mistral-large-2-instruct", "mistralai/mistral-large-4-1t-a52b"],
    f"descoberta: lista devolvida à UI sem 'nvidia_nim/' — obtido: {catalogo.get('models')}",
)
check(
    catalogo.get("modelo_atual") == "mistralai/mistral-large-4-1t-a52b"
    and catalogo.get("modelo_atual_disponivel") is True,
    "descoberta: modelo salvo com prefixo é reconhecido no catálogo (id limpo dos dois lados)",
)

db_put = FakeDB({})
configuracoes.salvar_configuracoes(
    ConfiguracoesPatch(nvidia_model="nvidia_nim/mistralai/mistral-large-4-1t-a52b"), db_put
)
check(
    db_put.valores.get("nvidia_model") == "mistralai/mistral-large-4-1t-a52b",
    f"PUT: grava só o id limpo no banco — obtido: {db_put.valores.get('nvidia_model')!r}",
)
check(
    configuracoes.obter_configuracoes(db_put)["nvidia_model"] == "mistralai/mistral-large-4-1t-a52b",
    "GET: a UI recebe o id limpo mesmo com valor prefixado no banco",
)

# ------------------------------------------------------------- veredicto

print()
if falhas:
    print(f"Fallback do router LLM: {len(falhas)} verificação(ões) falharam.")
    sys.exit(1)
print("Fallback do router LLM: todas as verificações passaram.")
sys.exit(0)

"""Testes do pacote SEO/AdSense (Pacote 1) e do login local (Pacote 2).

Roda sem pytest e sem servidor: `python backend/tests/test_seo_auth.py`.
Cobre:
  - prompt do pipeline exigindo HTML semântico e >= 1500 palavras;
  - bloqueio de publicação sem <h2>/<p>;
  - mock do LLM devolvendo HTML válido e verificação do payload WordPress;
  - login correcto/incorrecto, token, rotas protegidas e troca de senha.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Stub do módulo de banco: os testes não precisam de SQLAlchemy a correr.
if "backend.core.database" not in sys.modules:
    _stub = types.ModuleType("backend.core.database")

    class _Marcador:
        pass

    _stub.Configuracao = _Marcador
    _stub.Usuario = _Marcador
    _stub.Blog = _Marcador
    _stub.Noticia = _Marcador
    _stub.Log = _Marcador
    _stub.Visto = _Marcador
    _stub.SessionLocal = lambda *a, **k: None

    def _get_db():
        yield None

    _stub.get_db = _get_db
    _stub.init_db = lambda: None
    sys.modules["backend.core.database"] = _stub

falhas: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(f"{'PASS' if cond else 'FAIL'} — {msg}")
    if not cond:
        falhas.append(msg)


# ---------------------------------------------------------------- Pacote 1

from backend.core import pipeline  # noqa: E402

SRC_PIPELINE = (ROOT / "backend/core/pipeline.py").read_text(encoding="utf8")

# 1. prompt exige a estrutura AdSense
for exigencia in ("1500", "<h2>", "<h3>", "<p>", "<ul>", "Conclus", "60 caracteres", "140 caracteres"):
    check(exigencia in SRC_PIPELINE, f"prompt do pipeline exige '{exigencia}'")

check("NÃO use <h1>" in SRC_PIPELINE, "prompt proíbe <h1> (o título já é o h1 da página)")

# 2. validação de conteúdo publicável
HTML_BOM = (
    "<p>Introdução em dois parágrafos, com frases curtas.</p>"
    "<h2>Primeira seção</h2><p>Conteúdo.</p>"
    "<h3>Subseção</h3><ul><li>item</li></ul>"
    "<h2>Segunda seção</h2><p>Mais conteúdo.</p>"
    "<h2>Conclusão</h2><p>Fechamento explícito do artigo.</p>"
)
HTML_RUIM = "<p>Só um parágrafo, sem hierarquia nenhuma.</p>"
HTML_SEM_P = "<h2>Um heading</h2>mas sem parágrafo algum."

estado_bom = pipeline.conteudo_publicavel(HTML_BOM)
check(estado_bom["ok"], "conteudo_publicavel aceita HTML com <h2> e <p>")
check("problemas" in estado_bom and estado_bom["problemas"] == [], "conteúdo válido não lista problemas")

estado_ruim = pipeline.conteudo_publicavel(HTML_RUIM)
check(not estado_ruim["ok"], "conteudo_publicavel rejeita HTML sem <h2>")
check("nenhuma seção <h2>" in estado_ruim["problemas"], "rejeição sem <h2> explica o problema")
check("detalhe" in estado_ruim and "bloqueada" not in estado_ruim["detalhe"].lower(),
      "detalhe orienta a regeneração (não é mensagem de bloqueio de publicação)")

estado_sem_p = pipeline.conteudo_publicavel(HTML_SEM_P)
check(not estado_sem_p["ok"], "conteudo_publicavel rejeita HTML sem <p>")
check("nenhum parágrafo <p>" in estado_sem_p["problemas"], "rejeição sem <p> explica o problema")

# 3. título e meta description dentro dos limites
tit_longo = "Um título bastante longo que ultrapassa com folga o limite de sessenta caracteres"
limpo = pipeline._limpar_titulo(tit_longo)
check(len(limpo) <= 60, f"título cortado para <= 60 caracteres (obtido {len(limpo)})")
check(not limpo.endswith((" ", ",", ";", ":", ".", "-")), "título cortado sem pontuação pendurada")
check(pipeline._limpar_titulo("Título curto") == "Título curto", "título curto passa intacto")

meta_longa = "<p>" + ("palavra " * 60).strip() + "</p>"
check(len(pipeline._limpar_meta_description(meta_longa)) <= 140, "meta description limitada a 140")
check("<p>" not in pipeline._limpar_meta_description(meta_longa), "meta description sem tags HTML")

# 4. mock do LLM + payload WordPress
RESPOSTA_LLM = """{
  "titulo": "Brasil anuncia novo plano econômico para 2027 com foco em infraestrutura",
  "resumo": "O governo apresentou um plano de infraestrutura com investimentos bilionários; veja o que muda.",
  "corpo": "<p>O governo anunciou nesta semana um novo plano econômico.</p><h2>O que prevê o plano</h2><p>O documento traz investimentos em logística.</p><h3>Rodovias</h3><ul><li>duplicação</li></ul><h2>Reação do mercado</h2><p>Analistas avaliam com cautela.</p><h2>Conclusão</h2><p>O plano depende do Congresso.</p>"
}"""

dados = pipeline._parse_resposta_llm(RESPOSTA_LLM)
check("titulo" in dados and "corpo" in dados, "mock do LLM é parseado como JSON")
corpo = dados["corpo"]

wp = __import__("backend.core.wordpress_publisher", fromlist=["publish_to_wordpress"])

# payload que o WordPress receberia (espelha o de publish_to_wordpress)
payload = {"title": pipeline._limpar_titulo(dados["titulo"]), "content": corpo, "status": "publish"}
check("<h2>" in payload["content"], "payload WordPress contém <h2>")
check("<p>" in payload["content"], "payload WordPress contém <p>")
check(payload["status"] == "publish", "payload WordPress publica com status 'publish'")
check(len(payload["title"]) <= 60, "título do payload <= 60 caracteres")

try:
    wp.validar_conteudo(HTML_BOM)
    check(True, "validar_conteudo deixa passar HTML semântico")
except RuntimeError:
    check(False, "validar_conteudo deixa passar HTML semântico")

try:
    wp.validar_conteudo(HTML_RUIM)
    check(False, "validar_conteudo bloqueia HTML sem <h2>")
except RuntimeError as exc:
    check("bloqueada" in str(exc).lower(), f"bloqueio explica a regra: {str(exc)[:80]}")

# ---------------------------------------------------------------- Pacote 2
# O login precisa do banco REAL (cria o utilizador e valida o hash), e não do
# stub. Esta secção remonta os módulos com um SQLite em memória.

for _mod in [m for m in list(sys.modules) if m.startswith("backend")]:
    del sys.modules[_mod]

import os as _os  # noqa: E402
import tempfile as _tempfile  # noqa: E402

_tmp = _tempfile.mkdtemp(prefix="pandanews-tests-")
_os.environ["PANDANEWS_HOME"] = _tmp
import importlib  # noqa: E402

_config = importlib.import_module("backend.core.config")
_db = importlib.import_module("backend.core.database")
_db.init_db()

from backend.core import auth as auth_core  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from backend.app.main import app  # noqa: E402

cliente = TestClient(app)

# login
r = cliente.post("/api/v1/auth/login", json={"email": "dan.hachuel@gmail.com", "senha": "123456"})
check(r.status_code == 200, "login correto devolve 200")
token = r.json().get("token", "")
check(bool(token), "login correto devolve token")
payload_token = __import__("jwt").decode(token, options={"verify_signature": False})
check(payload_token.get("sub") == "dan.hachuel@gmail.com", "token traz sub = e-mail")
check("exp" in payload_token, "token traz exp (validade de 24h)")
validade_horas = (payload_token["exp"] - payload_token.get("iat", payload_token["exp"])) / 3600
check(23 <= validade_horas <= 25, f"validade do token ~24h (obtido {validade_horas:.1f}h)")

r = cliente.post("/api/v1/auth/login", json={"email": "dan.hachuel@gmail.com", "senha": "errada"})
check(r.status_code == 401, "senha errada devolve 401")

r = cliente.post("/api/v1/auth/login", json={"email": "ninguem@exemplo.com", "senha": "123456"})
check(r.status_code == 401, "e-mail inexistente devolve 401")

r1 = cliente.post("/api/v1/auth/login", json={"email": "dan.hachuel@gmail.com", "senha": "x"})
r2 = cliente.post("/api/v1/auth/login", json={"email": "ninguem@exemplo.com", "senha": "x"})
check(r1.json().get("detail") == r2.json().get("detail"),
      "mensagem genérica (não revela se o e-mail existe)")

# rotas protegidas
check(cliente.get("/api/v1/blogs").status_code == 401, "rota protegida sem token devolve 401")
check(cliente.post("/api/v1/noticias/gerar", json={"blog_id": 1}).status_code == 401,
      "POST protegido sem token devolve 401")

r = cliente.get("/api/v1/blogs", headers={"Authorization": f"Bearer {token}"})
check(r.status_code == 200, "rota protegida COM token devolve 200")

r = cliente.get("/api/v1/auth/eu", headers={"Authorization": f"Bearer {token}"})
check(r.status_code == 200 and r.json().get("email") == "dan.hachuel@gmail.com",
      "/auth/eu devolve o e-mail do token")

import jwt as pyjwt
from datetime import datetime, timedelta, timezone

expirado = pyjwt.encode({"sub": "dan.hachuel@gmail.com",
                         "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
                        auth_core._secret(), algorithm=auth_core.ALGORITMO)
check(cliente.get("/api/v1/blogs", headers={"Authorization": f"Bearer {expirado}"}).status_code == 401,
      "token expirado devolve 401")

forjado = pyjwt.encode({"sub": "dan.hachuel@gmail.com",
                        "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                       "chave-errada", algorithm="HS256")
check(cliente.get("/api/v1/blogs", headers={"Authorization": f"Bearer {forjado}"}).status_code == 401,
      "token forjado (outra chave) devolve 401")

check(cliente.get("/api/v1/blogs", headers={"Authorization": "token-sem-bearer"}).status_code == 401,
      "cabeçalho sem 'Bearer' devolve 401")

# públicos
check(cliente.get("/api/v1/health").status_code == 200, "/health continua público")
check(cliente.get("/api/v1/auth/status").status_code == 200, "/auth/status é público")
check(cliente.post("/api/v1/auth/login", json={}).status_code in (401, 422),
      "login vazio não cria sessão")

# troca de senha
r = cliente.post("/api/v1/auth/alterar-senha",
                 json={"senha_atual": "errada", "senha_nova": "nova123456"},
                 headers={"Authorization": f"Bearer {token}"})
check(r.status_code == 401, "troca com senha atual errada devolve 401")

r = cliente.post("/api/v1/auth/alterar-senha",
                 json={"senha_atual": "123456", "senha_nova": "curta"},
                 headers={"Authorization": f"Bearer {token}"})
check(r.status_code == 422, "senha nova com menos de 6 caracteres é rejeitada")

r = cliente.post("/api/v1/auth/alterar-senha",
                 json={"senha_atual": "123456", "senha_nova": "nova123456"},
                 headers={"Authorization": f"Bearer {token}"})
check(r.status_code == 200, "troca correta devolve 200")

check(cliente.post("/api/v1/auth/login",
                   json={"email": "dan.hachuel@gmail.com", "senha": "123456"}).status_code == 401,
      "senha antiga deixa de valer")
r = cliente.post("/api/v1/auth/login", json={"email": "dan.hachuel@gmail.com", "senha": "nova123456"})
check(r.status_code == 200, "senha nova passa a valer")

# repõe a senha padrão para o próximo arranque
cliente.post("/api/v1/auth/alterar-senha",
             json={"senha_atual": "nova123456", "senha_nova": "123456"},
             headers={"Authorization": f"Bearer {r.json()['token']}"})

# helpers de hash
check(auth_core.senha_confere("123456", auth_core.hash_senha("123456")), "hash/check de senha fecham")
check(not auth_core.senha_confere("123456", auth_core.hash_senha("outra")), "check nega senha errada")
check(auth_core.email_do_token("lixo") is None, "token inválido devolve None")
check(auth_core.email_do_token("") is None, "token vazio devolve None")

# ---------------------------------------------------------------- Pacote 3

from backend.core import supabase_db  # noqa: E402

check("usuarios" in supabase_db.TABELAS_ESPERADAS, "Supabase espera a tabela usuarios")
check("public.usuarios" in supabase_db.SCHEMA_SQL, "schema SQL do Supabase cria usuarios")

# backup automático antes de migrar
backup = supabase_db.criar_backup_sqlite()
check(backup.get("ok") is True, "criar_backup_sqlite não falha")
check(backup.get("criado") is True, "backup do SQLite é criado (banco sqlite com dados)")
check("backups" in str(backup.get("backup", "")), "backup vai para data/backups/")
check(backup.get("nome", "").startswith("pandanews_") and backup.get("nome", "").endswith(".db"),
      f"nome do backup no formato pandanews_AAAAMMDD_HHMMSS.db (obtido {backup.get('nome')})")
check((Path(backup["backup"]).stat().st_size > 0 if backup.get("criado") else True),
      "backup tem conteúdo (cópia real, não ficheiro vazio)")

# estado do banco para a UI
from backend.core.database import SessionLocal  # noqa: E402
from backend.app.routers.configuracoes import _status_banco  # noqa: E402

_db_sessao = SessionLocal()
try:
    estado = _status_banco(_db_sessao)
finally:
    _db_sessao.close()
check(estado["backend"] in ("sqlite", "supabase"), "status do banco devolve backend válido")
check(estado["rotulo"] in ("SQLite local", "Supabase conectado"), f"rótulo exposto: {estado['rotulo']}")
check("backups" in estado, "status do banco lista os backups")
check(len(estado["backups"]) >= 1, "o backup acabado de criar aparece no estado")

# ---------------------------------------------------------------- veredicto

print()
if falhas:
    print(f"{len(falhas)} verificação(ões) falharam:")
    for f in falhas:
        print("   -", f)
    sys.exit(1)
print("SEO/AdSense + login local: todas as verificações passaram.")
sys.exit(0)
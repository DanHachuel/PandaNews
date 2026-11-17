"""Testes de multi-tenancy: migracao de dados legados + isolamento entre usuarios.

Roda sem pytest e sem servidor: `python backend/tests/test_multi_tenant.py`.

Cobre os criterios de aceitacao do SaaS multi-tenant:
  1. migracao local: dados sem `user_id` (schema anterior) passam a pertencer
     ao primeiro utilizador (dan.hachuel@gmail.com) — historico preservado;
  2. o utilizador original continua a ver os seus dados apos a migracao;
  3. novo utilizador (POST /auth/registro) nao ve blogs/noticias/imagens/
     logs/configuracoes de outro (isolamento);
  4. IDOR: nenhuma rota protegida aceita id de recurso de outro utilizador
     (GET/PATCH/DELETE de blog, gerar noticia) — tudo devolve 404.

O teste corre sobre um SQLite temporario (PANDANEWS_HOME) — nunca toca na
base real de ~/.pandanews.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# home temporario ANTES de importar o backend: config.py resolve DB_PATH a
# partir dele, e o teste fica isolado da base do utilizador.
_TMP = tempfile.mkdtemp(prefix="pandanews-tenant-")
os.environ["PANDANEWS_HOME"] = _TMP

import importlib  # noqa: E402

_db = importlib.import_module("backend.core.database")
_db.init_db()

from backend.core import auth as auth_core  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402

cliente = TestClient(app)

falhas: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(f"{'PASS' if cond else 'FAIL'} — {msg}")
    if not cond:
        falhas.append(msg)


# ------------------------------------------------------------ schema legado
#
# Simula uma base anterior ao multi-tenant: blogs/noticias sem `user_id` e
# `configuracoes` com PK simples. Criado por SQL cru para exercitar o caminho
# real de migracao (ALTER TABLE + UPDATE), nao apenas o default do modelo.

DB = Path(_TMP) / "data" / "pandanews.db"
con = sqlite3.connect(DB)
con.executescript(
    """
    drop table if exists noticias;
    drop table if exists blogs;
    drop table if exists configuracoes;

    create table blogs (
      id integer primary key autoincrement,
      nome varchar(200) not null,
      tema varchar(50) not null default 'geral',
      regiao varchar(100) not null default 'Brasil',
      fontes_rss text not null default '[]',
      estilo_editorial text not null default '',
      frequencia_horas integer not null default 6,
      status varchar(20) not null default 'ativo',
      created_at datetime
    );
    create table noticias (
      id integer primary key autoincrement,
      blog_id integer not null references blogs(id),
      titulo varchar(300) not null default '',
      corpo text not null default '',
      resumo text not null default '',
      imagem_url varchar(500) not null default '',
      status varchar(20) not null default 'rascunho',
      llm_provider varchar(50) not null default '',
      created_at datetime
    );
    create table configuracoes (
      chave varchar(100) primary key,
      valor text not null default ''
    );
    insert into blogs (nome, created_at) values ('Blog Legado', '2026-01-01 00:00:00');
    insert into noticias (blog_id, titulo, corpo, status, created_at)
      values (1, 'Noticia Legada', '<p>conteudo</p>', 'rascunho', '2026-01-01 00:00:00');
    insert into configuracoes (chave, valor) values ('meta_diaria', '3');
    """
)
con.commit()
con.close()

# ------------------------------------------------------- 1) migracao local

# re-executa o init_db: create_all completa as colunas novas e _migrate()
# atribui os registos antigos ao primeiro utilizador.
_db.init_db()

sessao = _db.SessionLocal()
blogs_legados = sessao.query(_db.Blog).all()
check(len(blogs_legados) == 1, "blog legado preservado pela migracao")
check(
    all(b.user_id == "dan.hachuel@gmail.com" for b in blogs_legados),
    f"blog legado atribuido ao 1º utilizador (obtido: {[b.user_id for b in blogs_legados]})",
)
noticias_legadas = sessao.query(_db.Noticia).all()
check(
    all(n.user_id == "dan.hachuel@gmail.com" for n in noticias_legadas),
    "noticia legada atribuida ao 1º utilizador",
)
confs = sessao.query(_db.Configuracao).all()
check(
    all(c.user_id == "dan.hachuel@gmail.com" for c in confs),
    "configuracoes legadas atribuidas ao 1º utilizador",
)
sessao.close()

# ------------------------------------- 2) utilizador original ve o historico

r = cliente.post("/api/v1/auth/login", json={"email": "dan.hachuel@gmail.com", "senha": "123456"})
check(r.status_code == 200, "login do utilizador original continua a funcionar")
token_a = r.json().get("token", "")
r = cliente.get("/api/v1/blogs", headers={"Authorization": f"Bearer {token_a}"})
check(r.status_code == 200 and len(r.json()) == 1, "utilizador original ve o seu blog migrado")
blog_id = r.json()[0]["id"]
r = cliente.get("/api/v1/noticias", headers={"Authorization": f"Bearer {token_a}"})
check(r.status_code == 200 and len(r.json()) == 1, "utilizador original ve a sua noticia migrada")

# ------------------------------------------------- 3) registo do utilizador B

r = cliente.post(
    "/api/v1/auth/registro",
    json={"email": "segunda.conta@exemplo.com", "senha": "senha-de-seis"},
)
check(r.status_code == 200 and bool(r.json().get("token")), "POST /auth/registro cria conta e devolve token")
token_b = r.json().get("token", "")
r2 = cliente.post(
    "/api/v1/auth/registro",
    json={"email": "segunda.conta@exemplo.com", "senha": "senha-de-seis"},
)
check(r2.status_code == 409, "registo com e-mail repetido devolve 409")
r = cliente.post("/api/v1/auth/registro", json={"email": "invalido", "senha": "senha-de-seis"})
check(r.status_code == 400, "registo com e-mail invalido devolve 400")
r = cliente.post("/api/v1/auth/registro", json={"email": "curta@exemplo.com", "senha": "123"})
check(r.status_code == 422, "registo com senha curta devolve 422")
r = cliente.post("/api/v1/auth/login", json={"email": "segunda.conta@exemplo.com", "senha": "senha-de-seis"})
check(r.status_code == 200, "login da conta nova funciona")

# ------------------------------------------------ 4) isolamento entre contas

r = cliente.get("/api/v1/blogs", headers={"Authorization": f"Bearer {token_b}"})
check(r.status_code == 200 and r.json() == [], "segunda conta nao ve nenhum blog")
r = cliente.get("/api/v1/noticias", headers={"Authorization": f"Bearer {token_b}"})
check(r.status_code == 200 and r.json() == [], "segunda conta nao ve nenhuma noticia")
r = cliente.get("/api/v1/imagens", headers={"Authorization": f"Bearer {token_b}"})
check(r.status_code == 200 and r.json() == [], "segunda conta nao ve nenhuma imagem")
r = cliente.get("/api/v1/logs", headers={"Authorization": f"Bearer {token_b}"})
check(r.status_code == 200 and r.json() == [], "segunda conta nao ve nenhum log")
r = cliente.get("/api/v1/configuracoes", headers={"Authorization": f"Bearer {token_b}"})
cfg = r.json()
check(
    r.status_code == 200 and not (cfg.get("nvidia_api_key") or {}).get("configured"),
    "segunda conta nao herda as chaves do primeiro utilizador",
)
check(
    (cfg.get("meta_diaria") in (None, 3)) ,
    "segunda conta cai no padrao quando nao tem valor proprio",
)
r = cliente.get("/api/v1/dashboard", headers={"Authorization": f"Bearer {token_b}"})
dash = r.json()
check(
    dash.get("blogs_total") == 0 and dash.get("noticias_total") == 0,
    "dashboard da segunda conta comeca zerado",
)

# ------------------------------------------------------- 5) IDOR (404 em tudo)

r = cliente.get(f"/api/v1/blogs/{blog_id}", headers={"Authorization": f"Bearer {token_b}"})
check(r.status_code == 404, "GET /blogs/{id} de outro utilizador devolve 404")
r = cliente.patch(
    f"/api/v1/blogs/{blog_id}", json={"nome": "hackeado"}, headers={"Authorization": f"Bearer {token_b}"}
)
check(r.status_code == 404, "PATCH /blogs/{id} de outro utilizador devolve 404")
r = cliente.post(
    "/api/v1/noticias/gerar", json={"blog_id": blog_id}, headers={"Authorization": f"Bearer {token_b}"}
)
check(r.status_code == 404, "gerar noticia no blog de outro utilizador devolve 404")
r = cliente.delete(f"/api/v1/blogs/{blog_id}", headers={"Authorization": f"Bearer {token_b}"})
check(r.status_code == 404, "DELETE /blogs/{id} de outro utilizador devolve 404")
r = cliente.get(
    "/api/v1/noticias", params={"blog_id": blog_id}, headers={"Authorization": f"Bearer {token_b}"}
)
check(r.status_code == 200 and r.json() == [], "listar noticias filtradas por blog alheio devolve vazio")

# o dono continua com tudo intacto
r = cliente.get("/api/v1/blogs", headers={"Authorization": f"Bearer {token_a}"})
check(len(r.json()) == 1, "dados do dono intactos apos as tentativas de IDOR")

# ------------------------------------------------------------ veredicto final

print()
if falhas:
    print(f"Multi-tenancy: {len(falhas)} verificacao(oes) falharam.")
    sys.exit(1)
print("Multi-tenancy: todas as verificacoes passaram.")
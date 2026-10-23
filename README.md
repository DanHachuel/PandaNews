# PandaNews

SaaS **local** (roda no navegador) para criação e automação de múltiplos blogs de notícias com IA.

- Blogs multi-tenant com tema (esporte, política, economia, tecnologia, geral) e recorte regional
- Coleta de feeds RSS → redação via LLM com fallback **NVIDIA NIM → Google Gemini**
- Imagens fotojornalísticas via Gemini Image
- Fluxo editorial: rascunho → revisão humana opcional → aprovado/publicado
- 100% local por padrão (SQLite + arquivos), com Supabase opcional
- Agendamento automático por blog (APScheduler)

## Instalação

CMD / MobaXterm:

```
npx.cmd --yes --prefer-online @danhachuel/pandanews@latest install
npx.cmd --yes --prefer-online @danhachuel/pandanews@latest
```

Shell (PowerShell, Linux, macOS):

```
npx --yes @danhachuel/pandanews@latest install
npx --yes @danhachuel/pandanews@latest
```

Requisitos: **Node.js >= 20**. Nenhum Python pré-instalado é necessário — o instalador provisiona um runtime Python portátil na primeira execução (`.runtime/` na raiz do pacote; sobrescreva com a variável de ambiente `PANDANEWS_HOME`).

## Status (versão 0.1.00)

Versão inicial de **bootstrap**: estrutura do repositório, CLI (`pandanews install/start/build`) e workflow de publicação via GitHub Actions. O backend FastAPI e a UI React chegam na **0.2.00** (Fases 1 a 4 do plano de implementação — ver `CHANGELOG.md`).

## Desenvolvimento

```
# Backend
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev

# CLI local
node bin/cli.js install --skip-python-deps
node bin/cli.js
```

## Regras do projeto

Versionamento (PATCH de dois dígitos), release via GitHub Actions, CHANGELOG obrigatório e demais regras permanentes estão em [`AGENTS.md`](AGENTS.md).

## Licença

MIT — veja [LICENSE](LICENSE).

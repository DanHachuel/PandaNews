# Changelog

Todas as versões publicadas são registradas aqui antes do publish (regra em AGENTS.md). A etiqueta visual usa PATCH de dois dígitos (ex.: 0.1.00); o registry npm normaliza para a versão canônica (ex.: 0.1.0).

## 0.2.02 (2026-10-24)

- **O sistema NUNCA abre o navegador**: o app exibe o endereço no terminal e o usuário decide quando abrir (dependência `open` removida)
- **Terminal limpo**: logs de acesso do uvicorn (stdout — `GET /health`, `GET /api/v1/*` etc.) vão apenas para `data/backend.log`; o console mantém somente stderr (banner de inicialização, WARNING/ERROR e tracebacks)
- **Fallback de porta também para o backend**: se 8000 estiver ocupada (ex.: outra instância), o backend sobe em 8001, 8002... e o proxy da UI segue automaticamente — junto com o fallback já existente da UI (4030, 4031...)
- Novo endpoint `GET /health` na raiz (200 OK) para clientes que esperam esse caminho — elimina os 404; o health canônico segue em `/api/v1/health`
- `data/backend.log` continua registrando TODAS as requisições (incluindo `/health`) para auditoria — o filtro no logger `uvicorn.access` (Python) foi deliberadamente evitado: removeria `/health` também do arquivo de auditoria; o silenciamento é feito apenas no console

## 0.2.01 (2026-10-23)

- **Blindagem do backend**: saída do uvicorn espelhada no console e gravada em `<home>/data/backend.log` — queda anormal registra o motivo para diagnóstico
- **Auto-restart**: se o backend encerrar com código anormal (ex.: 103), reinicia sozinho em 3s (até 5 tentativas) — a UI não cai junto
- `install`: correção idempotente dos caminhos absolutos do `pyvenv.cfg` após migração de runtime (venv movida herdava caminhos antigos)

## 0.2.00 (2026-10-23)

- **UI React completa** (Fase 2): Vite + TypeScript + Tailwind, sidebar com 7 seções, topbar com seletor de blog e tema claro/escuro
  - Dashboard: checklist de onboarding (efeito Zeigarnik) com barra de progresso, estatísticas, gráfico de geração dos últimos 7 dias e últimos erros
  - Blogs: cards, criação em assistente de 3 passos (Lei de Hick), edição, pausar/ativar e exclusão com confirmação modal (Lei de Jakob)
  - Notícias: filtros por blog/status, badges de status (rascunho em âmbar — von Restorff), aprovar/rejeitar e edição manual
  - Configurações: NVIDIA NIM e Google Gemini com keys mascaradas e teste de conexão real, ordem de fallback reordenável, banco SQLite/Supabase e agendamento — em blocos expansíveis (Lei de Miller)
  - Automação: toggle global do scheduler e por blog; Imagens e Logs com empty states
- **Favicon de urso-panda** 🐼 nas guias do navegador (SVG) — também no placeholder
- **Backend Fase 1**: SQLite com tabelas blogs/noticias/configuracoes/logs criadas no startup, CRUD de blogs (`/api/v1/blogs`), configurações mascaradas (`/api/v1/configuracoes`), teste de LLM real por provedor (`/api/v1/llm/test`), dashboard (`/api/v1/dashboard`), notícias e logs
- `start.js`: proxy `/api` → backend (UI same-origin) e fallback SPA para rotas do React Router
- Workflow: build do frontend antes do publish (`frontend/dist` entra no tarball)

## 0.1.03 (2026-10-23)

- Runtime movido para um diretório **estável por usuário** (`~/.pandanews`, sobrescrevível via `PANDANEWS_HOME`): upgrades de versão do pacote não reinstalam mais Python/dependências — o instalador detecta o que já existe e só instala o que falta
- **Migração automática**: runtimes de instalações anteriores (cache do npx ou layout antigo na pasta do pacote) são localizados e reaproveitados em vez de baixados de novo (`PANDANEWS_SKIP_MIGRATE=1` força instalação limpa)
- **Fingerprint de dependências** (requirements.txt + versão do Python): o pip só roda quando os requisitos mudam
- Reinstalação do Python apenas quando a versão do runtime muda (limpeza automática do antigo)
- Workflow: passo `npm ci` antes do smoke test — o checkout do CI não tem `node_modules` e o launcher (que importa `fs-extra`) falhava com ERR_MODULE_NOT_FOUND

## 0.1.02 (2026-10-23)

- Porta padrão da UI alterada de 3030 para **4030** (sobrescrevível via `PANDANEWS_UI_PORT`)
- Fallback automático de porta: se 4030 estiver ocupada, o PandaNews tenta a seguinte (4031, 4032, ...) em até 20 tentativas, com mensagem clara se nenhuma estiver livre
- CORS do backend passa a aceitar localhost/127.0.0.1 em qualquer porta, acompanhando a porta dinâmica da UI

## 0.1.01 (2026-10-23)

- README reescrito para o fluxo de um único comando via npx (padrão Thunderbolt): `npx @danhachuel/pandanews` instala tudo junto e sobe o app; removidas as instruções manuais de desenvolvimento (pip, uvicorn, npm)
- Instalador completo (`pandanews install`): download de Python 3.12.7 portátil (python-build-standalone), criação de virtualenv e instalação de todas as dependências do backend em um único passo — nenhum Python pré-instalado necessário (antecipação do núcleo da Fase 4)
- `pandanews` (start) agora sobe o backend FastAPI em 127.0.0.1:8000, serve página em 127.0.0.1:3030 e abre o navegador automaticamente; instala o runtime sozinho na primeira execução
- Tratamento de porta ocupada (EADDRINUSE) com mensagem clara; portas configuráveis via `PANDANEWS_API_PORT` / `PANDANEWS_UI_PORT` e sem processos órfãos no encerramento
- CORS habilitado no backend para a UI local (127.0.0.1:3030)

## 0.1.00 (2026-10-23)

Bootstrap inicial do repositório PandaNews.

- Estrutura base de pastas: `bin/`, `scripts/`, `backend/` (app + core), `frontend/`, `.github/workflows/`
- `AGENTS.md` com as regras permanentes do projeto (versionamento de dois dígitos, push obrigatório, release via GitHub Actions, CHANGELOG obrigatório, sessões simultâneas)
- `package.json` com pacote `@danhachuel/pandanews` e binário `pandanews`
- CLI `pandanews` com comandos `install`, `start` e `build` (instalação estrutural funcional; Python portátil chega na 0.2.00, Fase 4)
- Workflow `publish-npm.yml`: validação de metadados, smoke test do instalador, publicação com dist-tag `next` via dispatch e promoção a `latest` via tags `vX.Y.ZZ`
- Correção do passo `Apply requested version`: a etiqueta visual de dois dígitos (ex.: `0.1.00`) é normalizada para semver canônico (ex.: `0.1.0`) antes do `npm version` — o primeiro dispatch falhou com "Version not changed"
- `README.md`, `LICENSE` (MIT), `.gitignore`, `CHANGELOG.md`
- Release placeholder no registry npm para criar o pacote `@danhachuel/pandanews`

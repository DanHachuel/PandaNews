# Changelog

Todas as versões publicadas são registradas aqui antes do publish (regra em AGENTS.md). A etiqueta visual usa PATCH de dois dígitos (ex.: 0.1.00); o registry npm normaliza para a versão canônica (ex.: 0.1.0).

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

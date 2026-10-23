# Changelog

Todas as versões publicadas são registradas aqui antes do publish (regra em AGENTS.md). A etiqueta visual usa PATCH de dois dígitos (ex.: 0.1.00); o registry npm normaliza para a versão canônica (ex.: 0.1.0).

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

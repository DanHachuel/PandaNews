# Regras do Projeto — AGENTS.md (PandaNews)

Regras permanentes do repositório **PandaNews** (pacote npm `@danhachuel/pandanews`, binário `pandanews`). Toda a sessão de agente que trabalhe neste projeto deve segui-las integralmente.

## Versionamento NPM

O PandaNews usa a convenção visual de lançamento MAJOR.MINOR.PATCH, com dois dígitos no PATCH. Ao atingir o patch 99, a próxima publicação deve incrementar o componente MINOR e reiniciar o PATCH em 00; quando o MINOR está em 9, é o MAJOR que avança e MINOR/PATCH reiniciam em 00.

Exemplos obrigatórios: depois de 0.3.99, a etiqueta apresentada é 0.4.00; depois de 0.9.99, a etiqueta apresentada é 1.0.00 (nunca 0.10.00). Nunca apresentar patch acima de 99 nem minor acima de 9.

O NPM aplica SemVer e normaliza zeros à esquerda: a etiqueta visual 0.4.00 é publicada no registry como a versão canónica 0.4.0. Antes de cada publicação, confirmar a versão em package.json, no workflow NPM e no registry. Nos comandos Windows/MobaXterm, usar a versão canónica literal confirmada no registry; na interface e comunicação de lançamento, usar a etiqueta visual com patch de dois dígitos.

## Push obrigatório

Sempre que uma sessão de agente criar commits, o ramo deve ser enviado de imediato para o origin (push) — nunca deixar trabalho apenas commitado no disco local. Não perguntar ao utilizador se deve fazer push: fazer sempre, automaticamente, no final de cada tarefa que produza commits.

## Regras de release (permanentes)

**Publicação imediata** — sempre que algo for actualizado no repositório, enviar para o GitHub (push) e publicar de imediato a nova versão no NPM.

**Publicar sempre via GitHub Actions** — as publicações NPM ocorrem sempre via o workflow *Publish npm package*, nunca por npm publish local. Sequência: bump de versão → commit/push → dispatch manual com dist-tag `next` → push da tag `vX.Y.ZZ`, que verifica o tarball e promove a versão a `latest`.

**Transparência** — depois de criar ou publicar uma versão, relatar explicitamente a versão e as áreas ou ficheiros alterados.

**UX sem travas de pré-registo** — nunca criar travas de pré-registo; validações de credenciais apenas no momento da acção que realmente precisa delas.

## Comandos de instalação

Após cada versão, entregar sempre os comandos no formato:

- CMD/MobaXterm: `npx.cmd --yes --prefer-online @danhachuel/pandanews@<VERSAO> install` e `npx.cmd --yes --prefer-online @danhachuel/pandanews@<VERSAO>`
- Instalação normal: `npx --yes @danhachuel/pandanews@<VERSAO> install` e `npx --yes @danhachuel/pandanews@<VERSAO>`

## CHANGELOG obrigatório

Sempre que existir qualquer alteração com push (código, docs, configuração, correção, publicação npm), escrever a entrada correspondente no CHANGELOG.md antes de publicar — nenhuma versão sai sem registo. Ao integrar trabalho de outra sessão sem entrada, documentá-la retroactivamente.

## Sessões simultâneas

Antes de qualquer commit/push, verificar o ramo principal remoto (main) (git fetch origin + comparar) e fazer rebase sempre que o main tiver avançado — o utilizador corre várias sessões simultâneas. Em colisão de versão, a versão já publicada vence e a sessão renumera para o patch seguinte (confirmar no registry antes de publicar).

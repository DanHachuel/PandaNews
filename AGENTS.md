# Regras do Projeto — AGENTS.md (PandaNews)

Regras permanentes do repositório **PandaNews** (pacote npm `@danhachuel/pandanews`, binário `pandanews`). Toda a sessão de agente que trabalhe neste projeto deve segui-las integralmente.

## ⚠️ ATENÇÃO AGENTE

**Antes de iniciar qualquer tarefa, leia todos os arquivos em `.agents/skills/*/SKILL.md`.** Eles contêm regras críticas para evitar regressões fatais (EBUSY, janelas CMD, quebra de API, AdSense). Siga-as à risca.

Cada skill declara no topo quando deve ser lida. Resumo:

| Skill | Leia antes de… |
|---|---|
| `windows-runtime-guard` | tocar em `scripts/`, `bin/cli.js`, launcher ou qualquer código que lance subprocesso |
| `llm-resilience-guard` | tocar em `backend/core/llm_router.py`, no pipeline de geração, nos provedores LLM ou no teste de conexão |
| `wordpress-seo-guard` | tocar no prompt do LLM, no pipeline, no publicador WordPress ou no endpoint de publicação |
| `parallel-session-guard` | commitar, rebasear ou publicar qualquer versão do npm |
| `systemic-view-guard` | mudar assinatura de função, endpoint, schema do banco ou ciclo de vida do processo |
| `surgical-scope-guard` | começar qualquer bugfix ou feature — impede refatoração não solicitada |
| `contract-test-guard` | escrever ou alterar qualquer teste do projeto |

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

## Proibição de janelas de console/CMD (permanente)

É **PROIBIDO** criar ou publicar versões que abram janelas de terminal (CMD, PowerShell, console Python ou qualquer outra tela preta) no computador do usuário. Qualquer processo filho lançado pelo app — backend Python, subprocessos do pipeline, scripts auxiliares — deve:

- **No Windows**, nascer com `windowsHide: true` e grupo de processo isolado (`detached: true`) — nunca herdar o console do launcher;
- **Em qualquer plataforma**, rodar em background, com saída apenas em arquivo de log, sem alocar terminal visível;
- ser encerrado **sempre por código** (`taskkill /PID /T` no Windows, sinal no grupo no Unix), nunca por propagação de sinais do terminal.

Uma versão que exiba qualquer janela de console no computador do usuário é **inválida**: deve ser corrigida antes da publicação ou imediatamente depois (hotfix), com a entrada correspondente no CHANGELOG. O teste `scripts/test-start-isolation.mjs` (rodado no CI) falha o build se qualquer spawn do launcher perder `windowsHide: true` ou `detached: true`.

**Armadilha do redirector do venv (Windows)** — `windowsHide: true` no spawn do launcher **não basta** quando o binário lançado é o `venv/Scripts/python.exe` das distribuições python-build-standalone: esse executável é um *redirector* que re-executa o interpretador real (`.runtime/python/python.exe`), e o **neto nasce sem as flags de ocultação do pai** — o Windows então aloca um console novo para ele. Medido: spawn do venv = 1 processo filho + 1 hospedeiro de console novo; spawn do interpretador base com o `site-packages` do venv no `PYTHONPATH` = 0 filhos, 0 console novo. Por isso o launcher sobe o interpretador **base** no Windows (`pythonBin()` em `scripts/start.js`), e nunca o `venvBin()` direto. No Unix o `venv/bin/python` é symlink, sem redirector, e lá segue-se usando o venv.

**Watchdog sem teto é loop de janelas** — uma rotina que reergue o backend sem limite máximo de tentativas transforma qualquer falha de bind em spawned infinito, e cada spawned é candidato a uma janela. O watchdog de `scripts/start.js` tem teto duro (`MAX_REINICIOS = 3`), encerra o processo zumbi por código, aponta o `backend.log` e sai com `exit(1)`; antes de reiniciar ainda reaproveita um backend já vivo (`backendJaRodando()`) em vez de empilhar outra instância.

## Comandos de instalação

Após cada versão, entregar sempre os comandos no formato:

- CMD/MobaXterm: `npx.cmd --yes --prefer-online @danhachuel/pandanews@<VERSAO> install` e `npx.cmd --yes --prefer-online @danhachuel/pandanews@<VERSAO>`
- Instalação normal: `npx --yes @danhachuel/pandanews@<VERSAO> install` e `npx --yes @danhachuel/pandanews@<VERSAO>`

## Ciclo de vida das instâncias (permanente)

O backend corre **destacado** e sobrevive ao fechamento do terminal — inclusive ao Ctrl+C. Consequência: um `pandanews start` pode encontrar uma instância anterior ainda viva e, se a reaproveitar, o utilizador fica com a UI nova a ser servida por um backend de versão velha.

- **Lock global em `~/.pandanews/pandanews.pid`** (fora da pasta do pacote npm, que o `npx` apaga ao atualizar, e fora de `data/`). Regista o launcher **e** o backend: `pandanews kill` e o auto-kill precisam dos dois.
- **Auto-kill no arranque**: `runStart` chama `matarInstanciasAntigas` **antes** de subir o backend, e depois arranca sempre fresco. Duas redes de segurança, porque o lock pode ficar obsoleto (medido: lock a apontar para o processo errado): os PIDs do lock **e** quem estiver dono de uma porta candidata (`pidDaPorta` via `netstat` no Windows). Nenhuma delas pode matar o próprio `process.pid`.
- **Comando `pandanews kill`** (alias `stop`): lock global + portas, sempre por código, sempre silencioso (`windowsHide` + `stdio: 'ignore'`).

**Runtime permanente (fix do EBUSY)** — o servidor **nunca** corre de dentro do cache do `npx`: todo o código de execução vive em `~/.pandanews/runtime` (cópia feita pelo `install`, que depois imprime "Instalação concluída! O cache do npx foi liberado." e sai sem iniciar o servidor). O `start` atualiza a cópia quando a versão muda e sobe backend + UI sempre a partir daí; o PID global vive em `~/.pandanews/pandanews.pid`. Um `start` antes de `install` num home novo prepara tudo sozinho; num checkout de desenvolvimento, a raiz do repositório serve de código.

## CHANGELOG obrigatório

Sempre que existir qualquer alteração com push (código, docs, configuração, correção, publicação npm), escrever a entrada correspondente no CHANGELOG.md antes de publicar — nenhuma versão sai sem registo. Ao integrar trabalho de outra sessão sem entrada, documentá-la retroactivamente.

## Sessões simultâneas

Antes de qualquer commit/push, verificar o ramo principal remoto (main) (git fetch origin + comparar) e fazer rebase sempre que o main tiver avançado — o utilizador corre várias sessões simultâneas. Em colisão de versão, a versão já publicada vence e a sessão renumera para o patch seguinte (confirmar no registry antes de publicar).

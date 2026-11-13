# Changelog

Todas as versões publicadas são registradas aqui antes do publish (regra em AGENTS.md). A etiqueta visual usa PATCH de dois dígitos (ex.: 0.1.00); o registry npm normaliza para a versão canônica (ex.: 0.1.0).

## 0.5.04 (2026-11-13)

- **PACOTE 1 — Conteúdo pronto para AdSense (SEO)**
  - `backend/core/pipeline.py`: prompt de redação reescrito para exigir **estrutura HTML semântica** — título ≤ 60 caracteres, corpo **mínimo de 1500 palavras** (teto de 4000 tokens), `<h2>` para seções principais, `<h3>` para subseções, `<p>` com 2–3 frases, `<ul>`/`<ol>` para listas, introdução em 2 parágrafos, conclusão explícita, `<h1>` proibido (o título já é o h1 da página) e **meta description ≤ 140 caracteres** devolvida no campo `resumo` (sem tags HTML)
  - Novos helpers `_limpar_titulo` (corta em 60 caracteres na última palavra, sem pontuação pendurada) e `_limpar_meta_description`; `regenerar_noticia` também passou a usar o tecto de 4000 tokens
  - **Bloqueio de publicação sem estrutura**: `conteudo_publicavel()` exige pelo menos um `<h2>` e um `<p>`; `wordpress_publisher.validar_conteudo()` corre antes do POST e levanta "Publicação bloqueada: …" explicando o que falta e orientando a regeneração. Notícia sem estrutura não chega ao WordPress
- **PACOTE 2 — Login local (estilo ProdMaker)**
  - Tabela `usuarios` (`id`, `email` único, `senha_hash`, `criado_em`) criada no `init_db()`; no primeiro arranque é semeado o utilizador padrão **`dan.hachuel@gmail.com` / `123456`** — a senha é guardada como **hash bcrypt**, nunca em texto plano (a inicial pode vir de `PANDANEWS_SENHA_INICIAL`)
  - `backend/core/auth.py`: hash/verificação bcrypt e **JWT HS256** com `sub` + `exp` (24h), assinado por chave gerada em `~/.pandanews/data/jwt.secret` (permissão restrita, fora do código)
  - Endpoints **públicos**: `POST /api/v1/auth/login` (mensagem genérica — não revela se o e-mail existe), `GET /api/v1/auth/status`. **Protegidos**: `GET /api/v1/auth/eu`, `POST /api/v1/auth/alterar-senha` (valida senha actual, mínimo 6 caracteres, recusa senha igual à anterior)
  - **Todas as rotas de dados protegidas** (blogs, noticias, imagens, automacao, configuracoes, dashboard, llm, logs, wordpress) via `include_router(..., dependencies=[Depends(usuario_atual)])` — 401 sem token, expirado, forjado ou sem `Bearer`
  - Frontend: página **`Login.tsx`** (cartão centralizado, logo PandaNews, botão de 44px), **`AuthGuard` no layout** do `App.tsx` (nenhuma rota escapa), token no `localStorage`, e o cliente `api.ts` passou a enviar `Authorization: Bearer` e a limpar a sessão + redireccionar em 401
  - Configurações ganhou a secção **"Minha Conta"**: e-mail da sessão, troca de senha e botão **Sair**
- **PACOTE 3 — Fase 6 (Supabase + UX)**
  - `usuarios` entrou em `TABELAS_ESPERADAS`, no `SCHEMA_SQL` e na migração (antes migrava só 4 tabelas)
  - **Backup automático antes de migrar**: `criar_backup_sqlite()` copia `pandanews.db` para `data/backups/pandanews_AAAAMMDD_HHMMSS.db`; `migrar_do_sqlite()` chama-o **antes** de tocar no destino e devolve o caminho no resultado
  - `GET /api/v1/configuracoes` passou a expor `banco` — rótulo **"SQLite local"** ou **"Supabase conectado"**, credencial detectada, flag de migração e a **lista dos backups**; a UI mostra o estado, o projecto e os backups disponíveis
  - **UX (lei de Fitts)**: `Button` subiu de `h-10` (40px) para **`h-11` (44px)** — alvo confortável para rato e toque
- **Validação**: 148 verificações automáticas, 0 falhas — `test_seo_auth.py` (novo, 66: prompt, validação `<h2>`/`<p>`, título/meta, mock do LLM no payload WordPress, login, token, rotas protegidas, troca de senha, backup e status), `test_llm_fallback.py` (31), `npm test` (51). E2E com servidor real: **14/14** — login 200/401, rota protegida 401→200, status do banco, backup criado e listado, `/login` servido pelo fallback SPA
- Nota: a exigência de login é **local e sem travas** — credenciais só são pedidas no momento da acção que precisa delas (regra do AGENTS.md)

## 0.5.03 (2026-11-09)

- **HOTFIX — prefixo `nvidia_nim/` removido antes de chamar a API da NVIDIA**: os ids de modelo estavam a ser guardados/enviados com o prefixo de convenção do LiteLLM (`nvidia_nim/mistralai/mistral-large-4-1t-a52b`). Como o PandaNews faz HTTP directo para `https://integrate.api.nvidia.com/v1/chat/completions` — e não passa por um proxy — a NVIDIA não reconhecia o prefixo e devolvia erro de modelo não encontrado
- `backend/core/llm_router.py`: novo helper `limpar_nome_modelo()` (+ `PREFIXOS_PROXY`) que remove o prefixo do id sem tocar na barra legítima de `fornecedor/modelo`. `provider_config` já entrega o modelo limpo; o payload do POST em `chamar_provedor` e em `test_provider` monta `"model": "mistralai/mistral-large-4-1t-a52b"`, e o modelo devolvido ao caller também é o id limpo
- `backend/app/routers/configuracoes.py`: `GET /configuracoes` exibe o id limpo; `PUT /configuracoes` grava apenas o id limpo (um valor prefixado nunca mais entra no banco); `GET /configuracoes/llm/nvidia/models` devolve a lista limpa e compara `modelo_atual_disponivel` id-limpo com id-limpo — antes um modelo correcto salvo com prefixo aparecia na UI como "fora do catálogo"
- **Frontend** (`Configuracoes.tsx`): `limparModelo()` aplicado à lista de modelos, ao valor do `<select>` e ao payload de salvamento — defesa em profundidade, a UI nunca mostra nem reenvia o prefixo
- **Testes**: 19 verificações novas em `backend/tests/test_llm_fallback.py` (35 no total, todas verdes local e no CI). O teste captura o JSON real do POST e exige `model == "mistralai/mistral-large-4-1t-a52b"` sem resto de `nvidia_nim`, tanto na geração quanto no teste de conexão, e cobre a descoberta de modelos e o PUT
- **CHANGELOG**: removida a entrada duplicada da 0.5.02 (a sessão anterior deixou duas secções para a mesma versão; a mantida é a mais completa)

## 0.5.02 (2026-11-09)

- **BUG MEDIDO antes de corrigir**: nesta máquina havia **2 backends uvicorn simultâneos** (porta 8000 e porta 8001) e o ficheiro de PID `data/backend.pid` apontava para o processo **errado** — sintomas exactos do efeito colateral do isolamento por `detached: true`: o backend sobrevive ao terminal, e cada `pandanews start` reaproveitava ou empilhava outra instância em vez de actualizar. Resultado para o utilizador: a UI nova a ser servida por um backend de versão velha
- **Lock global `~/.pandanews/pandanews.pid`**: o PID deixa de ser gravado em `data/backend.pid` e passa a viver no lar estável do utilizador — **fora da pasta do pacote npm**, que o `npx` apaga ao atualizar. O lock guarda o launcher **e** o backend em JSON (`{launcher, backend, port}`), porque `kill` e o auto-kill precisam dos dois
- **Auto-kill no arranque**: `runStart` chama `matarInstanciasAntigas(home)` **antes** de subir o backend e depois arranca sempre fresco — nada de reaproveitar zombie. **Duas redes de segurança**, porque o lock pode ficar obsoleto (foi o que aconteceu): os PIDs registados no lock **e** quem estiver dono de uma porta candidata. `pidDaPorta()` descobre esse dono via `netstat -ano` no Windows (spawn silencioso: `windowsHide` + `stdio: 'pipe'`), o único caminho que apanha o zombie que o ficheiro perdeu. Após matar, espera 1s para o SO libertar ficheiros e portas antes do bind seguinte
- **Nenhum processo se mata a si mesmo**: `matarInstanciasAntigas` e `comandoKill` ignoram qualquer PID igual a `process.pid` — dois launchers a arrancar ao mesmo tempo não se suicidam mutuamente
- **Comando `pandanews kill`** (alias `pandanews stop`) no `bin/cli.js`: lê o lock global, encerra backend e launcher por código, limpa o lock. Permite encerrar o app em background sem reiniciar a máquina
- **`taskkill`/`netstat` do ciclo de vida silenciosos**: `windowsHide: true` + `detached: true` + `stdio: 'ignore'` no kill e `stdio: 'pipe'` no netstat — nenhuma janela de console em nenhum caminho
- **FIX DO EBUSY (raiz, não workaround) — runtime permanente**: o servidor **nunca** corre de dentro do cache do `npx`. `install` copia o código para `~/.pandanews/runtime` (marcador `.version` incluído) e o `start` actualiza essa cópia quando a versão muda, subindo backend e UI sempre a partir daí (`cwd: codeDir`). Sem processos vivos dentro do cache, o `npx` pode renomeá-lo sem `EBUSY`. Em checkout de desenvolvimento, a raiz do repositório serve de código
- **README**: documenta o `EBUSY` do `npx` no Windows, por que acontecia e que está corrigido — com `npm install -g` recomendado por evitar o download repetido
- **AGENTS.md**: nova regra permanente "Ciclo de vida das instâncias" — lock global, auto-kill, comando `kill`, runtime permanente e a limitação do `npx`
- **Teste de regressão ampliado**: 51 verificações (eram 34), cobrindo o lock global, a ordem matar-depois-iniciar, a protecção contra auto-kill, o `netstat` silencioso, a espera de 1s e o comando `kill` no CLI. Validação funcional: após `pandanews kill`, os 2 zombies desapareceram e as portas 8000/8001 ficaram livres
- **E2E do ciclo de vida**: duas sessões do launcher em sequência — a segunda matou a primeira, sobrou exactamente um uvicorn novo, o lock foi actualizado para o backend novo, a porta 8001 nunca foi ocupada e `pandanews kill` limpou tudo no fim
- Colisão de versão resolvida por renumeração (0.5.01 já publicado, regra do AGENTS.md)

## 0.4.12 (2026-11-08)

- **Regra permanente documentada no AGENTS.md** — duas armadilhas que causaram os hotfixes 0.4.04 e 0.4.11, agora escritas para não se repetirem:
  - **Armadilha do redirector do venv (Windows)**: `windowsHide: true` no spawn do launcher não basta quando o binário é o `venv/Scripts/python.exe` do python-build-standalone — ele re-executa o interpretador real e o neto nasce sem as flags do pai, e o Windows aloca um console novo. O launcher sobe o interpretador **base** com o `site-packages` do venv no `PYTHONPATH`; nunca o `venvBin()` direto no Windows
  - **Watchdog sem teto é loop de janelas**: rotina que reergue o backend sem limite máximo transforma falha de bind em spawned infinito. Teto duro `MAX_REINICIOS = 3`, encerramento por código, `exit(1)` e reaproveitamento de backend vivo antes de reiniciar
- Sem alteração de código — apenas documentação das regras permanentes (regra do AGENTS.md exige entrada no CHANGELOG para qualquer alteração com push)

## 0.4.11 (2026-11-08)

- **CAUSA RAIZ DAS JANELAS CMD — medida, não adivinhada**: no Windows o `venv/Scripts/python.exe` das distribuições python-build-standalone é um **REDIRECIONADOR**: ele re-executa o interpretador real (`.runtime/python/python.exe`) e esse **neto nasce sem as flags de ocultação do pai**. O Windows então aloca um console NOVO para o neto. Experimento no próprio repositório (spawn com `detached` + `windowsHide`, `stdio` no arquivo): venv python = **1 processo filho + 1 hospedeiro de console novo**; python base + `PYTHONPATH` = **0 filhos, 0 console novo**
- **Correção**: `startBackend` passa a subir o **interpretador base** diretamente, com o `site-packages` do venv no `PYTHONPATH` — um único processo, sem neto, sem console novo. Dependências idênticas (verificado: import do app inteiro com o python base). No Unix o `venv/bin/python` é symlink, então lá seguimos usando o venv
- **Watchdog com teto duro (`MAX_REINICIOS = 3`)**: 3 falhas de leitura consecutivas disparam um reinício, mas no máximo 3 tentativas. Ao estourar, o watchdog **encerra o backend zumbi por código, mostra o erro e o caminho do `backend.log`, e sai com `exit(1)`** — um backend que não sobe nunca mais vira loop infinito de spawns (e cada spawn era candidato a janela)
- **Watchdog não empilha mais instâncias**: antes de reiniciar, consulta `backendJaRodando()` e reaproveita um backend vivo. Backend duplicado era o que fazia a porta "morrer" para o proxy e disparar reinício atrás de reinício — foi isso que apareceu no log como "crash loop" (37 marcadores de início em ~80 min, embora cada um terminasse em `Application startup complete`)
- **`taskkill` do encerramento silencioso de verdade**: além de `windowsHide: true` e `detached: true`, agora com `stdio: 'ignore'` — nenhuma saída vazando para o terminal
- **Teste de mutação ampliado**: `scripts/test-start-isolation.mjs` passa a auditar as funções isoladamente — `encerrarPorPid` (kill: `windowsHide` + `detached` + `stdio: 'ignore'`), `iniciarWatchdog` (teto, `exit(1)`, reset do contador, caminho pelo `startBackend`) e a escolha do binário (`pythonBin` prefere o base, injeta `PYTHONPATH`, e o spawn do backend **não** usa `venvBin` direto). Total: 34 verificações
- **Verificação E2E com grupo de controle**: subindo o launcher real, o processo python ficou com **0 filhos** (antes: 1, o redirector). O hospedeiro de console que apareceu na medição foi atribuído ao próprio `Start-Job` do PowerShell — um job **vazio**, sem nenhum processo filho, já cria 1 `conhost`. Ou seja: nenhuma janela é atribuível ao PandaNews
- **Causa do "backend morrendo" descartada**: todos os módulos importam limpo — `backend.app.main`, `wordpress_publisher`, `pipeline`, `scheduler`, `proc`. Nenhum `openai` no código, nenhuma dependência de terceiros faltando em `requirements.txt`. O `backend.log` confirma 35 inicializações completas; o backend atual está no ar desde 21:20
- Colisão de versão resolvida por renumeração (0.4.10 já publicado, regra do AGENTS.md)

## 0.5.01 (2026-11-08)

- **Badge de versão dinâmica no sidebar** (padrão Thunderbolt/ProdMaker): `PandaNews vX.Y.Z` ao lado do nome, com a versão injetada do `package.json` da raiz via `define` do Vite (`__APP_VERSION__`) — atualiza sozinha a cada release, sem edição manual do React; `vite-env.d.ts` tipa a global
- Removida a versão hardcoded do rodapé do sidebar (agora só a badge dinâmica)

## 0.5.00 (2026-11-08)

- **Módulo Publicador WordPress** (preparação para monetização AdSense): credenciais `wordpress_url` / `wordpress_user` / `wordpress_app_password` salvas no banco local e mascaradas no frontend; coluna `noticias.wordpress_post_id` (com migração leve para bancos existentes)
- `backend/core/wordpress_publisher.py`: teste de conexão real (`GET /wp-json/wp/v2/users/me`), upload de imagem em 2 etapas (`POST /wp-json/wp/v2/media` → `featured_media`) e criação do post (`POST /wp-json/wp/v2/posts`, `status: publish`, categoria resolvida pelo tema do blog — busca ou cria)
- Endpoint `POST /api/v1/noticias/{id}/publicar`: bloqueia republicação (400 "Já publicado"), exige **mínimo de 300 palavras** (diretriz AdSense), grava `status=publicado` + `wordpress_post_id` e devolve o link do post; `GET /api/v1/wordpress/status` + `POST /api/v1/wordpress/testar`
- Frontend: seção **Integração WordPress** em Configurações (URL, usuário, senha de aplicativo mascarada, Testar Conexão com estado) e botão **🌐 Publicar no WordPress** nos cards de notícias — loading durante o envio, badge "Publicado" + link "Ver no site" após o sucesso
- **Diretriz rígida AdSense no prompt do LLM**: "O texto final deve ter no mínimo 1500 palavras. Expanda o contexto, traga implicações e detalhes para criar um artigo profundo e otimizado para SEO. Nunca gere textos com menos de 1000 palavras." — teto de tokens da redação elevado para 4000

## 0.4.10 (2026-11-08)

- **Cobertura E2E pelo caminho HTTP real**: o teste de fallback ganhou um cenário que substitui apenas o `httpx.Client` — `chamar_provedor`, a construção da URL, os headers e o `raise_for_status` rodam de verdade. A NVIDIA devolve 410, o Gemini devolve 200 e a notícia nasce do Gemini com o log `Erro na NVIDIA (...). Acionando Google Gemini...` emitido. Fecha a lacuna de testar só a função mockada
- Teste sobe para 16 verificações, todas verdes local e no CI

## 0.4.09 (2026-11-08)

- **Frontend — Gemini tratado como a NVIDIA no teste de conexão**: o badge agora distingue `degraded` (âmbar, modelo em fim de vida 404/410) de `falhou` (vermelho) e a mensagem de detalhe usa a cor correspondente. Antes um 404/410 do Gemini aparecia como "falhou" vermelho — agora o usuário entende que é o modelo, não a chave, e que a geração segue pela NVIDIA

## 0.4.08 (2026-11-08)

- **Mantém o rótulo `gemini` em `noticias.llm_provider`**: a reescrita do router (0.4.07) devolvia o id interno `google`, o que regrediria o alinhamento banco/UI feito na 0.4.05/0.4.06. `gerar_texto` volta a devolver `"gemini"` quando o provedor do Google responde — Dashboards, filtros e exibição continuam consistentes
- Nenhuma outra mudança funcional

## 0.4.07 (2026-11-08)

- **CORREÇÃO DEFINITIVA da NVIDIA NIM — réplica do Thunderbolt**: `backend/core/llm_router.py` reescrito para falar com provedores OpenAI-compatible por **HTTP direto** (`POST {base_url}/chat/completions`, `Authorization: Bearer`, `Content-Type: application/json`, `Accept: application/json`), a mesma estrutura que funciona no projeto Thunderbolt — `requests` trocado por `httpx`, já dependência do projeto
- **Causa raiz 1 — dependência fantasma**: o 0.4.05/0.4.06 importava `from openai import APIStatusError, OpenAI`, mas `openai` **não está** em `requirements.txt`. Em instalação nova o backend morria com `ImportError` antes de qualquer chamada — era a exceção quebrando o fluxo antes da troca de provedor. A dependência foi eliminada: nada de SDK extra para instalar
- **Causa raiz 2 — modelo em fim de vida**: o default `meta/llama-3.3-70b-instruct` chegou ao fim da vida em 2026-08-26 e devolve **HTTP 410 Gone**; `meta/llama-3.1-nemotron-70b-instruct` devolve **HTTP 404 page not found**. O default agora é `mistralai/mistral-large-2-instruct`, verificado no catálogo ao vivo (`GET https://integrate.api.nvidia.com/v1/models`)
- **Endpoint à prova de 404**: a Base URL é normalizada antes do uso (`/v1`, `/v1/models` e `/v1/chat/completions` são aceitos sem duplicar o sufixo) — o `/chat/completions` duplicado era uma fonte de 404
- **Fallback implacável**: `except Exception` captura tudo — HTTP 4xx/5xx, 404/410, timeout, rede e JSON inválido. O log registra exatamente `Erro na NVIDIA ({e}). Acionando Google Gemini...` e o próximo provedor assume na mesma iteração; a notícia é gerada sem tela de erro
- **"Testar conexão" valida inferência real**: `POST /api/v1/llm/test` executa um `chat/completions` de verdade com `max_tokens=1` (não lista modelos). A string de erro do provedor volta no JSON para o frontend exibir; 404/410 marcam `degraded` com instrução de trocar de modelo
- **Proxy de modelos reforçado**: `/configuracoes/llm/nvidia/models` normaliza a URL, distingue 401/403 (chave recusada) de outros erros e devolve `modelo_atual_disponivel`
- **Frontend**: aviso vermelho quando o modelo selecionado saiu do catálogo da NVIDIA (404/410) — o usuário vê o problema antes de clicar em testar, com a indicação de que as gerações estão caindo no Gemini
- **Teste funcional novo**: `backend/tests/test_llm_fallback.py` (13 verificações, roda sem pytest e sem servidor) cobre o fallback no 410, a mensagem de log exigida, o erro quando todos os provedores falham, o formato do `test_provider` e a normalização do endpoint — agregado ao CI
- Colisão de versão resolvida por renumeração (0.4.06 já publicado), conforme a regra de sessões simultâneas do AGENTS.md

## 0.4.04 (2026-11-08)

- **HOTFIX real — fim das janelas de CMD no instalador**: o 0.4.03 blindou apenas o launcher (`start.js`) e deixou o **caminho de instalação** descoberto. No Windows, `tar` (extração do Python portátil), `python -m venv` e `pip install -r requirements.txt` eram lançados **sem `windowsHide`** — era aí que as múltiplas janelas de terminal apareciam. Os três `spawnSync` de `scripts/install.js` agora nascem com `windowsHide: true` (`CREATE_NO_WINDOW`)
- `scripts/build.js` blindado também: `npm install` e `npm run build` do frontend são chamados com `shell: true` (o wrapper `cmd.exe`/`npm.cmd` entra na conta) — ambos agora com `windowsHide: true`, sem piscar tela preta
- Saída preservada: o instalador mantém `stdio: 'inherit'`, então o progresso continua visível **no console que o usuário já abriu** — só a janela extra deixa de existir (verificado empiricamente no Windows)
- **Helper Python único e obrigatório**: `backend/core/proc.py` expõe `run_silent_process` / `run_silent` / `spawn_silent` / `call_silent` / `check_output_silent` / `system_silent`, aplicando `CREATE_NO_WINDOW = 0x08000000` via `creationflags` no Windows. O pipeline e o APScheduler rodam em memória (threads do `BackgroundScheduler`), sem processos do SO; o helper é o ponto único para qualquer subprocesso futuro
- **Teste de regressão ampliado e validado**: `scripts/test-start-isolation.mjs` deixa de olhar só o `start.js` e passa a varrer **todos** os pontos de entrada — `start.js`, `install.js`, `build.js` e `bin/cli.js` — exigindo `windowsHide: true` em cada `spawn`/`spawnSync`/`exec`/`execSync` (inclusive quando as opções vêm de constante compartilhada, ex. `...SILENT_WINDOWS`)
- O teste também trava regressões do backend Python: qualquer `subprocess.run/Popen/call/check_output/check_call` ou `os.system`/`os.popen` direto em `backend/**/*.py` falha o build (precisa passar por `backend.core.proc`)
- E ainda barra `uvicorn` com `--reload`/`--workers` no launcher — cada worker é um processo filho extra que, no Windows, pode alocar console próprio e ignorar as flags do pai
- **Guard verificado por mutação**: com a flag removida do `pip`, com um `subprocess.run` direto no backend e com `--reload` no uvicorn, o teste falha em todos os casos (exit 1) — não é carimbo de borracha
- Nota de transparência: a colisão de versão com o 0.4.03 já publicado no registry foi resolvida por renumeração, conforme a regra de sessões simultâneas do AGENTS.md

## 0.4.06 (2026-11-08)

- Rótulos de exibição do LLM alinhados ao critério de aceitação: o provedor do Google passa a ser gravado/exposto como **`gemini`** em `noticias.llm_provider` (antes o id interno `google`), e os warning de fallback usam os nomines "NVIDIA NIM" e "Gemini" — `Modelo NVIDIA NIM indisponível (Status 404). Acionando fallback para Gemini.`
- Nenhuma mudança funcional de roteamento — apenas nomenclatura consistente entre banco, log e UI

## 0.4.05 (2026-11-08)

- **HOTFIX — fallback à prova de falhas no LLM Router** (crítico): roteamento reescrito em `backend/core/llm_router.py`, agora explícito provedor por provedor na ordem configurada. Qualquer erro HTTP (4xx/5xx, incluindo **404/410** da NVIDIA) é interceptado, registrado (`Modelo nvidia indisponível (Status {status}). Acionando fallback para {próximo}.`) e o próximo provedor é acionado imediatamente — a geração não trava mais. A função devolve qual provedor respondeu (`noticias.llm_provider`) e o incidente fica em `backend.log`
- **HOTFIX — janelas de CMD na instalação**: os spawns de `tar` (extração do Python portátil), `python -m venv` e `pip install` em `scripts/install.js` nasciam sem `windowsHide` no Windows — origem das múltiplas janelas de terminal. Todos agora usam `SILENT_WINDOWS` (CREATE_NO_WINDOW), com `stdio: 'inherit'` (progresso continua visível no console que o usuário já abriu, sem janela extra). `scripts/build.js` (npm) e o helper `backend/core/proc.py` (subprocessos Python) seguem a mesma regra
- **Teste de conexão real**: `/api/v1/llm/test` dispara POST `/chat/completions` de verdade; 404/410 devolvem estado **`degraded`** com a mensagem "Sua chave da NVIDIA retornou erro 404. O sistema usará o Gemini (fallback) para gerar as notícias."
- Frontend: badge âmbar `degraded` no resultado do teste + tag vermelha **[Indisponível]** ao lado do select de modelos — destacada mas mantida selecionável
- Validado em E2E com mock servers: NVIDIA → 404 → Gemini → 200 → notícia gerada com `llm_provider='google'` e logs do incidente em `backend.log`

## 0.4.03 (2026-11-08)

- **Regra permanente no AGENTS.md**: é PROIBIDO criar/publicar versões que abram janelas de terminal (CMD/PowerShell/console Python) no computador do usuário — todo processo filho deve nascer com `windowsHide: true` + grupo isolado, rodar em background com saída apenas em log e ser encerrado por código; versão que exiba janela de console é inválida (hotfix + CHANGELOG)
- Teste de regressão reforçado: varre **todas** as chamadas `spawn`/`spawnSync` do launcher e falha se qualquer uma perder `windowsHide`/`detached` — o CI passa a barrar isso automaticamente
- `taskkill` do encerramento gracioso também com `detached: true` (uniformidade da regra)

## 0.4.02 (2026-11-08)

- **Seletor dinâmico de modelos NVIDIA NIM**: novo endpoint proxy `GET /api/v1/configuracoes/llm/nvidia/models` que consulta a NVIDIA em tempo real com a chave do usuário — a API key nunca é exposta ao frontend/Network tab
- Campo "Modelo" da NVIDIA em Configurações agora é um `<select>` populado automaticamente (5 min de cache, botão ↻ para recarregar) — o usuário não digita mais IDs
- Resiliência: sem chave, offline ou lista indisponível, o select mantém o modelo atual como opção (fallback) com aviso âmbar — nada de travar a tela

## 0.4.01 (2026-11-08)

- **Isolamento de processos (Windows/MobaXterm)**: o backend Python roda em grupo de processos próprio (`detached: true` → `CREATE_NEW_PROCESS_GROUP`) com `windowsHide: true` (sem janela fantasma) e `stdio` em fd do arquivo — um Ctrl+C no terminal agora derruba **apenas o launcher Node**; o backend e as gerações em andamento sobrevivem
- **Fim do processo órfão na porta 8000**: ao reabrir o app, o launcher detecta o backend vivo (`backend.pid` + probe de porta) e o **reaproveita**, em vez de subir uma segunda instância
- **Log sem terminal**: a inicialização do uvicorn e as requisições ficam registradas em `data/backend.log` mesmo com o terminal fechado (auditoria preservada)
- Encerramento do backend **sempre por código**: `taskkill /PID /F /T` no Windows, `kill` no grupo no Unix — sinais do terminal nunca chegam ao backend
- `unref()` no processo filho + watchdog de saúde (polling de porta a cada 10s; 3 falhas reerguem o backend silenciosamente)
- Teste de regressão `scripts/test-start-isolation.mjs` (`npm test`) roda no CI verificando as flags de isolamento — passo adicionado ao workflow de publish

## 0.4.00 (2026-10-30)

- **Supabase opcional (Fase 6)**: detecção automática de credenciais (`SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` no ambiente ou em Configurações); teste de conexão real (`POST /configuracoes/testar-supabase`); schema SQL pronto para o SQL Editor (`GET /configuracoes/schema-supabase`); migração dos dados locais SQLite → Supabase (`POST /configuracoes/migrar-supabase`) com relatório por tabela. O app continua 100% local e funcional sem Supabase
- **Meta diária** (Gradiente de Meta): card "Meta de hoje" no Dashboard com "faltam X notícias para bater a meta", barra de progresso e campo configurável em Configurações → Agendamento (`meta_diaria`)
- **Breadcrumbs** em todas as telas internas (Lei de Jakob): Dashboard / Blogs, Dashboard / Notícias, etc.
- **Configurações reformulada**: seção Banco de dados com status do backend ativo (SQLite local), detecção de credenciais, teste, schema SQL e migração — sem travas de pré-registro
- Revisão das 7 leis de usabilidade: Fitts (CTAs ≥40px), Hick (menu 7 itens, wizard 3 passos, expanders), Zeigarnik (checklist + stepper + meta), Jakob (breadcrumbs, ações destrutivas isoladas), Gradiente de Meta (meta diária, gráfico 7 dias), von Restorff (CTA verde, badge âmbar de rascunho), Miller (blocos ≤7, datas pt-BR)

## 0.3.01 (2026-10-25)

- **Páginas legais e de verificação** em `legal/` (padrão AutoPost-Lunga, adaptado ao PandaNews): `index.html` (apresentação do app, funcionalidades e provedores de API), `terms.html` (Termos de Uso em pt-BR) e `privacy.html` (Política de Privacidade em conformidade com a LGPD — Lei 13.709/2018)
- Backend serve as páginas em `/legal/index.html`, `/legal/terms.html` e `/legal/privacy.html` (whitelist de arquivos, servidos também via UI em `/legal/*` através do proxy)
- Conteúdo específico do PandaNews: dados de configuração de blogs, feeds RSS, chaves de API locais (NVIDIA NIM, Google Gemini, Supabase), compartilhamento mínimo com provedores (apenas prompts/contexto editorial), direitos do titular exercidos localmente, armazenamento em SQLite (`data/pandanews.db`) e imagens em `data/imagens/`
- `legal/` passa a fazer parte do tarball npm (`files`)

## 0.3.00 (2026-10-24)

- **Pipeline de notícias completo** (Fase 3): coleta RSS (feedparser) → filtragem por relevância (palavras-chave do tema + bônus de região) → redação via LLM com fallback NVIDIA → Gemini (resposta em JSON: título, resumo, corpo) → imagem fotojornalística via Gemini Image salva em `data/imagens/`
- **Scheduler ativo** (Fase 5): APScheduler com um job por blog ativo (intervalo = frequência do blog), toggle global em Automação liga/desliga de fato, recarregamento automático ao criar/editar/pausar/excluir blogs
- **Novos endpoints**: `POST /api/v1/noticias/gerar` (dispara o pipeline), `POST /api/v1/noticias/{id}/regenerar`, `GET/POST /api/v1/imagens` (galeria, arquivo e geração manual por prompt), `GET /api/v1/automacao/status` (próxima execução por blog), `POST /api/v1/automacao/executar`
- Dedup de itens: tabela `vistos` evita reutilizar o mesmo item de feed; migração leve adiciona `fonte_url`/`fonte_titulo` às notícias em bancos existentes
- Logs de execução por etapa (coleta/redação/imagem/pipeline) visíveis na página Logs
- UI: botão "Gerar notícia agora" com stepper de progresso (Gradiente de Meta: coletando → redigindo → gerando imagem → salvo), ação Regenerar nas notícias, galeria real de imagens com geração manual e próxima execução por blog na Automação

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

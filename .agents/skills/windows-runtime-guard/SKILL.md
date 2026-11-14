---
name: windows-runtime-guard
description: Blindar o PandaNews contra janelas CMD/PowerShell e travas de arquivo (EBUSY) no Windows. Leia antes de tocar em scripts/, bin/cli.js, launcher ou qualquer código que lance subprocesso.
---

# windows-runtime-guard

**Propósito:** nenhuma versão do PandaNews pode abrir janela de terminal no computador do
usuário, nem travar arquivos do cache do `npx` (erro `EBUSY`). Estas regras são permanentes e
valem para Windows, macOS e Linux.

## 1. Runtime permanente — o servidor nunca corre do cache do `npx`

- Todo o código de execução vive em `~/.pandanews/runtime` (resolvido por
  `backend/core/config.py:resolve_home()` no Python e por `resolveHome()` em `scripts/install.js`).
- `pandanews install` copia `backend/`, `frontend/dist/`, `scripts/` e `bin/` para
  `~/.pandanews/runtime`, imprime "Instalação concluída! O cache do npx foi liberado." e **sai sem
  iniciar o servidor**.
- `pandanews start` atualiza a cópia quando a versão do pacote muda (marcador `.version`) e sobe
  backend (`cwd` no runtime) e UI (dist do runtime) sempre a partir daí.
- Em checkout de desenvolvimento, a raiz do repositório serve de código.
- **Consequência:** com processos vivos dentro do cache, o `npx` não consegue renomear a pasta e
  estoura `EBUSY`. Nunca suba o backend a partir do cache.

## 2. Spawn silencioso — todo processo filho nasce invisível

**Node.js (`scripts/start.js`, `scripts/install.js`, `scripts/build.js`, `bin/cli.js`):**

```js
const SILENT_WINDOWS = { windowsHide: true };           // CREATE_NO_WINDOW
spawn(cmd, args, { cwd, detached: true, windowsHide: true, stdio: 'ignore', ...SILENT_WINDOWS });
```

- `windowsHide: true` em **todo** `spawn`/`spawnSync`/`exec`/`execSync` (inclusive quando as opções
  vêm de constante compartilhada, ex. `...SILENT_WINDOWS`).
- `detached: true` isola o grupo de processo — o filho não herda o console do launcher.
- Saída apenas em arquivo de log (`stdio` apontando para `backend.log`), nunca para um terminal novo.

**Python (`backend/**/*.py`):** use **sempre** o helper `backend/core/proc.py`
(`run_silent_process`, `run_silent`, `spawn_silent`, `call_silent`, `check_output_silent`,
`system_silent`). Ele aplica `CREATE_NO_WINDOW = 0x08000000` via `creationflags` no Windows.
`subprocess.run/Popen/call/check_output/check_call` e `os.system`/`os.popen` diretos no backend
**quebram o build** (`scripts/test-start-isolation.mjs` varre `backend/**/*.py`).

**Armadilha do redirector do venv (Windows):** `windowsHide: true` **não basta** quando o binário é
o `venv/Scripts/python.exe` das distribuições python-build-standalone — ele é um *redirector* que
re-executa o interpretador real (`.runtime/python/python.exe`) e o **neto nasce sem as flags do
pai**; o Windows aloca um console novo. Medido: venv = 1 filho + 1 console novo; interpretador base
com o `site-packages` do venv no `PYTHONPATH` = 0 filhos, 0 console novo. Por isso o launcher sobe o
interpretador **base** no Windows (`pythonBin()` em `scripts/start.js`) e **nunca** o `venvBin()`
direto. No Unix o `venv/bin/python` é symlink, sem redirector, e lá segue-se usando o venv.

## 3. Auto-kill seguro e encerramento por código

- O lock global vive em `~/.pandanews/pandanews.pid` (JSON: `{launcher, backend, port}`) — **fora**
  da pasta do pacote npm (que o `npx` apaga ao atualizar) e fora de `data/`.
- `runStart` chama `matarInstanciasAntigas(home)` **antes** de subir o backend e arranca sempre
  fresco. Duas redes de segurança, porque o lock pode ficar obsoleto: os PIDs do lock **e** quem for
  dono de uma porta candidata (`pidDaPorta()` via `netstat -ano`, spawn silencioso).
- **Nenhum processo mata a si mesmo:** ignore qualquer PID igual a `process.pid`.
- Encerramento sempre por código — `taskkill /PID <pid> /T /F` (árvore completa) no Windows, sinal no
  grupo no Unix — sempre com `windowsHide: true` e `stdio: 'ignore'`.
- Comando do usuário: `pandanews kill` (alias `pandanews stop`).
- Após matar, espere ~1s para o SO liberar arquivos e portas antes do bind seguinte.

**Watchdog sem teto é loop de janelas:** o watchdog de `scripts/start.js` tem teto duro
(`MAX_REINICTOS = 3`), encerra o zumbi por código, aponta o `backend.log` e sai com `exit(1)`. Antes
de reiniciar, reaproveita um backend vivo (`backendJaRodando()`) em vez de empilhar outra instância.

## 4. Proibição absoluta

É terminantemente proibido publicar código que abra qualquer janela de console (CMD, PowerShell,
conhost, terminal Python) no computador do usuário. Uma versão que exiba janela é **inválida**:
corrigir antes de publicar (ou hotfix imediato) com entrada no CHANGELOG. A barreira automática é
`node scripts/test-start-isolation.mjs` (51 verificações, rodado no CI): remova `windowsHide` de
qualquer spawn, use `subprocess.run` direto no backend ou ligue `--reload` no uvicorn e o build
falha.

**Antes de commitar.** rode `node scripts/test-start-isolation.mjs`.
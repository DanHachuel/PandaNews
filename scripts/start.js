// Inicia o PandaNews: backend FastAPI (127.0.0.1:8000+) + UI (127.0.0.1:4030+).
//
// Fluxo de um único comando: se o runtime não estiver provisionado, executa o
// install completo (Python portátil + dependências) antes de subir os
// servidores. Ambas as portas têm fallback automático (API: 8000, 8001, ...;
// UI: 4030, 4031, ...). O sistema NÃO abre o navegador.
//
// ISOLAMENTO DE PROCESSOS (Windows/MobaXterm): o backend Python roda em grupo
// de processos próprio (detached + windowsHide) com stdio direto no arquivo
// <home>/data/backend.log — não herda o console do launcher. Um Ctrl+C ou
// perda do terminal derruba apenas o launcher Node; o backend e as gerações
// em andamento sobrevivem. O encerramento do backend é SEMPRE por código
// (SIGTERM + taskkill /PID /T), nunca por propagação de sinal do terminal.
// Se uma instância anterior morreu deixando backend vivo, o launcher detecta
// (backend.pid + health) e reaproveita em vez de subir uma segunda.
import { appendFileSync, closeSync, existsSync, openSync, readFileSync, unlinkSync, writeFileSync } from 'node:fs';
import { spawn, spawnSync } from 'node:child_process';
import { createServer, request as httpRequest } from 'node:http';
import net from 'node:net';
import { join, extname } from 'node:path';
import { instalarCodigoRuntime, resolveHome, runInstall, runtimeDir, PKG_ROOT } from './install.js';

const API_PORT_BASE = Number(process.env.PANDANEWS_API_PORT || 8000);
const UI_PORT_BASE = Number(process.env.PANDANEWS_UI_PORT || 4030);
const PORT_MAX_TRIES = 20;
const BACKEND_POLL_ATTEMPTS = 60; // até 30s para o backend iniciar
const BACKEND_POLL_MS = 500;
const UI_POLL_ATTEMPTS = 20; // até 10s para a UI antiga responder

let activeBackendPort = API_PORT_BASE;

const FAVICON_URI = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='20' fill='%230b1220'/%3E%3Ccircle cx='25' cy='28' r='13' fill='%23e6edf3'/%3E%3Ccircle cx='75' cy='28' r='13' fill='%23e6edf3'/%3E%3Ccircle cx='50' cy='52' r='30' fill='%23e6edf3'/%3E%3Cellipse cx='37' cy='48' rx='9' ry='11' fill='%230b1220' transform='rotate(-15 37 48)'/%3E%3Cellipse cx='63' cy='48' rx='9' ry='11' fill='%230b1220' transform='rotate(15 63 48)'/%3E%3Ccircle cx='38' cy='49' r='3' fill='%2322c55e'/%3E%3Ccircle cx='62' cy='49' r='3' fill='%2322c55e'/%3E%3Cellipse cx='50' cy='62' rx='5' ry='4' fill='%230b1220'/%3E%3C/svg%3E";

// ---------------------------------------------------------------- utilidades

function venvBin(home) {
  return process.platform === 'win32'
    ? join(home, '.runtime', 'venv', 'Scripts', 'python.exe')
    : join(home, '.runtime', 'venv', 'bin', 'python');
}

// ------------------------------------------------------------------------
// JANELAS DE CONSOLE NO WINDOWS — porque subimos o python BASE e não o venv
//
// Medido neste repositório (spawn com detached + windowsHide, stdio no
// arquivo): `venv/Scripts/python.exe` das distribuições python-build-
// standalone é um REDIRECIONADOR — ele re-executa o interpretador real
// (`runtime/python/python.exe`) e esse NETO nasce SEM as flags de
// ocultação do pai. O Windows então aloca um console NOVO para o neto:
// 1 processo filho + 1 hospedeiro de console (conhost/WindowsTerminal)
// novos, ou seja, uma janela de terminal na cara do usuário.
//
// Subindo o interpretador base diretamente, com o site-packages do venv no
// PYTHONPATH, temos um ÚNICO processo: 0 filhos, 0 console novo. As
// dependências são exatamente as mesmas (verificado: import do app inteiro
// com o python base + PYTHONPATH).
//
// No Unix o `venv/bin/python` é um symlink para o base — sem redirector,
// sem neto —, então lá seguimos usando o venv normalmente.
// ------------------------------------------------------------------------
function baseBin(home) {
  return process.platform === 'win32'
    ? join(home, '.runtime', 'python', 'python.exe')
    : null;
}

function venvSitePackages(home) {
  return join(home, '.runtime', 'venv', 'Lib', 'site-packages');
}

function pythonBin(home) {
  if (process.platform === 'win32') {
    const base = baseBin(home);
    if (base && existsSync(base)) return base;
  }
  return venvBin(home);
}

function pythonEnv(home) {
  const env = { ...process.env, PANDANEWS_HOME: home, PYTHONUNBUFFERED: '1' };
  if (process.platform === 'win32') {
    // python base só enxerga as dependências do venv via PYTHONPATH
    const site = venvSitePackages(home);
    if (existsSync(site)) env.PYTHONPATH = site;
  }
  return env;
}

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.ico': 'image/x-icon',
};

// Testa se uma porta aceita conexão TCP (uvicorn ouvindo).
function portaAberta(port) {
  return new Promise((resolve) => {
    const socket = net.connect({ host: '127.0.0.1', port });
    socket.once('connect', () => {
      socket.destroy();
      resolve(true);
    });
    socket.once('error', () => resolve(false));
    socket.setTimeout(500, () => {
      socket.destroy();
      resolve(false);
    });
  });
}

// Encontra a primeira porta livre a partir de base (probe real de bind).
function probePort(port) {
  return new Promise((resolve) => {
    const srv = net.createServer();
    srv.once('error', () => resolve(false));
    srv.once('listening', () => srv.close(() => resolve(true)));
    srv.listen(port, '127.0.0.1');
  });
}

async function findFreePort(base, maxTries) {
  for (let port = base; port < base + maxTries; port++) {
    if (await probePort(port)) return port;
  }
  throw new Error(`Nenhuma porta livre entre ${base} e ${base + maxTries - 1}`);
}

// Encerra o processo por PID e (no Windows) a árvore de processos /T.
// Corre SEMPRE silenciosamente: windowsHide + stdio ignore — um taskkill
// que piscasse uma janela de console negaria a regra permanente do projeto.
function encerrarPorPid(pid, motivo) {
  try {
    if (process.platform === 'win32') {
      spawnSync('taskkill', ['/pid', String(pid), '/f', '/t'], {
        windowsHide: true, // CREATE_NO_WINDOW — sem tela preta
        detached: true, // grupo isolado, imune a Ctrl+C do console
        stdio: 'ignore', // taskkill não escreve no terminal do launcher
      });
    } else {
      process.kill(pid, 'SIGTERM');
    }
  } catch {
      /* processo já não existia */
  }
  console.log(motivo);
}

// ------------------------------------------------------------- lock global
//
// CICLO DE VIDA: o backend roda DESTACADO (detached + windowsHide), então
// sobrevive ao terminal — e também sobrevive ao fim da própria sessão. Sem
// um registo de quem está vivo, cada `pandanews start` empilhava outra
// instância: o PID antigo nunca morria, a porta ficava presa e o utilizador
// ficava com um backend de versão velha a servir a UI nova. Medido nesta
// máquina: 2 uvicorns simultâneos (8000 e 8001) e o `data/backend.pid` a
// apontar para o processo ERRADO.
//
// Por isso o lock vive em `~/.pandanews/pandanews.pid` — dentro do lar
// estável do utilizador, FORA da pasta do pacote npm (que o npx apaga ao
// atualizar) e fora de `data/`. Qualquer versão o encontra.
const LOCK_FILE = 'pandanews.pid';

function pidFilePath(home) {
  return join(home, LOCK_FILE);
}

// Lê o lock global. Devolve null se não existir ou estiver corrompido —
// lock corrompido NUNCA pode impedir o arranque.
export function lerPidGlobal(home) {
  const file = pidFilePath(home);
  if (!existsSync(file)) return null;
  try {
    const dados = JSON.parse(readFileSync(file, 'utf8'));
    if (typeof dados !== 'object' || dados === null) return null;
    return {
      launcher: Number.isInteger(dados.launcher) ? dados.launcher : null,
      backend: Number.isInteger(dados.backend) ? dados.backend : null,
      port: Number.isInteger(dados.port) ? dados.port : null,
    };
  } catch {
    return null;
  }
}

export function escreverPidGlobal(home, launcher, backend, port) {
  try {
    writeFileSync(
      pidFilePath(home),
      JSON.stringify({ launcher, backend, port, criado: new Date().toISOString() }, null, 2),
    );
  } catch {
    /* melhor esforço — o lock nunca deve derrubar o arranque */
  }
}

export function limparPidGlobal(home) {
  try {
    unlinkSync(pidFilePath(home));
  } catch {
    /* melhor esforço */
  }
}

// ---------------------------------------------------- descobrir e matar

// Descobre o PID dono de uma porta em LISTEN. No Windows via `netstat`
// (spawn silencioso: windowsHide + stdio pipe — nunca uma janela); no Unix
// devolve null, onde o lock global já basta.
function pidDaPorta(port) {
  if (process.platform !== 'win32') return null;
  try {
    const r = spawnSync('netstat', ['-ano'], {
      windowsHide: true, // CREATE_NO_WINDOW
      detached: true,
      stdio: ['ignore', 'pipe', 'ignore'], // só precisamos do stdout
    });
    if (r.status !== 0 || !r.stdout) return null;
    const alvo = `:${port}`;
    for (const linha of r.stdout.toString().split(/\r?\n/)) {
      if (!linha.includes(alvo) || !/LISTENING/i.test(linha)) continue;
      const colunas = linha.trim().split(/\s+/);
      const pid = Number(colunas[colunas.length - 1]);
      if (Number.isInteger(pid) && pid > 0) return pid;
    }
  } catch {
    /* netstat indisponível — seguimos sem o fallback */
  }
  return null;
}

// Mata uma árvore de processos por PID, sempre em silencioso.
// `matarArvore` é a primitiva; `encerrarPorPid` é o wrapper com mensagem.
export function matarArvore(pid) {
  try {
    if (process.platform === 'win32') {
      spawnSync('taskkill', ['/pid', String(pid), '/f', '/t'], {
        windowsHide: true, // CREATE_NO_WINDOW — sem tela preta
        detached: true, // grupo de processos isolado
        stdio: 'ignore', // taskkill não escreve no terminal
      });
    } else {
      // grupo de processos: sinal negativo mata o processo e os filhos
      process.kill(-pid, 'SIGKILL');
    }
  } catch {
    /* processo já não existia */
  }
}

// Mata TODAS as instâncias anteriores antes de subir uma nova.
// Duas redes de segurança, porque o lock pode ficar obsoleto (foi o que
// aconteceu: ficheiro a apontar para o processo errado):
//   1. os PIDs registados no lock global (launcher + backend);
//   2. qualquer processo ainda dono de uma porta candidata — o netstat
//      apanha o zombie que o ficheiro perdeu.
export async function matarInstanciasAntigas(home) {
  const lock = lerPidGlobal(home);
  let mortos = 0;

  if (lock) {
    for (const pid of [lock.launcher, lock.backend]) {
      // NUNCA matar o próprio processo: dois launchers a arrancar ao mesmo
      // tempo não podem suicidar-se mutuamente.
      if (pid && pid !== process.pid) {
        matarArvore(pid);
        mortos += 1;
      }
    }
  }

  // varre as portas candidatas: o que sobrar a segurá-las é zombie
  for (let port = API_PORT_BASE; port < API_PORT_BASE + PORT_MAX_TRIES; port++) {
    const dono = pidDaPorta(port);
    if (dono && dono !== process.pid) {
      matarArvore(dono);
      mortos += 1;
    }
  }

  if (mortos > 0) {
    console.log(`Encerrando instância anterior (${mortos} processo(s)) antes de iniciar...`);
    // 1s para o SO libertar os ficheiros e as portas — sem isto o bind
    // seguinte pode falhar com EADDRINUSE
    await new Promise((r) => setTimeout(r, 1000));
  }
  limparPidGlobal(home);
}

// Encerramento explícito (`pandanews kill`): lock global + portas.
export async function comandoKill(home) {
  let mortos = 0;
  const lock = lerPidGlobal(home);
  if (lock) {
    for (const pid of [lock.launcher, lock.backend]) {
      if (pid && pid !== process.pid) {
        matarArvore(pid);
        mortos += 1;
      }
    }
  }
  for (let port = API_PORT_BASE; port < API_PORT_BASE + PORT_MAX_TRIES; port++) {
    const dono = pidDaPorta(port);
    if (dono && dono !== process.pid) {
      matarArvore(dono);
      mortos += 1;
    }
  }
  limparPidGlobal(home);

  if (mortos > 0) {
    console.log(`PandaNews encerrado (${mortos} processo(s)).`);
  } else {
    console.log('Nenhuma instância do PandaNews em execução.');
  }
}

// ---------------------------------------------------------- UI estática/proxy

function placeholderPage() {
  return `<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>PandaNews</title>
<link rel="icon" href="${FAVICON_URI}">
</head>
<body style="font-family: Inter, system-ui, sans-serif; background: #0b1220; color: #e6edf3; display: flex; min-height: 100vh; align-items: center; justify-content: center;">
  <div style="text-align: center;">
    <h1 style="font-size: 3rem; margin: 0;">🐼 PandaNews</h1>
    <p style="color: #9aa7b5;">Backend ativo em <a style="color: #22c55e;" href="/api/v1/health">/api/v1/health</a></p>
    <p style="color: #9aa7b5;">A UI React completa chega na versão 0.2.00.</p>
  </div>
</body>
</html>`;
}

// Encaminha /api/* para o backend FastAPI (na porta ativa).
function proxyApi(req, res) {
  const options = {
    hostname: '127.0.0.1',
    port: activeBackendPort,
    path: req.url,
    method: req.method,
    headers: { ...req.headers, host: `127.0.0.1:${activeBackendPort}` },
  };
  const proxied = httpRequest(options, (upstream) => {
    res.writeHead(upstream.statusCode || 502, upstream.headers);
    upstream.pipe(res);
  });
  proxied.on('error', () => {
    res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify({ detail: `Backend PandaNews não responde em 127.0.0.1:${activeBackendPort}` }));
  });
  req.pipe(proxied);
}

let uiServer = null;

// Diretório de EXECUÇÃO do código: ~/.pandanews/runtime (runtime permanente,
// fora do cache do npx). Só cai para PKG_ROOT em checkout de desenvolvimento.
let codeDir = PKG_ROOT;

function createUiServer() {
  const distDir = join(codeDir, 'frontend', 'dist');
  return createServer((req, res) => {
    if (req.url.startsWith('/api') || req.url.startsWith('/legal')) {
      proxyApi(req, res);
      return;
    }
    const url = req.url.split('?')[0];
    const filePath = join(distDir, url === '/' ? 'index.html' : url.slice(1));
    if (!existsSync(filePath)) {
      // SPA (BrowserRouter): rotas sem extensão caem no index.html quando o
      // build existe; sem build, mostra o placeholder.
      const indexHtml = join(distDir, 'index.html');
      const hasBuild = existsSync(indexHtml);
      const isAsset = extname(url) !== '';
      if (hasBuild && !isAsset) {
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(readFileSync(indexHtml));
        return;
      }
      if (!hasBuild) {
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(placeholderPage());
        return;
      }
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('Not found');
      return;
    }
    res.writeHead(200, { 'Content-Type': MIME[extname(filePath)] || 'application/octet-stream' });
    res.end(readFileSync(filePath));
  });
}

function listenUi(port, attempt) {
  if (attempt > PORT_MAX_TRIES) {
    console.error(`Nenhuma porta livre entre ${UI_PORT_BASE} e ${UI_PORT_BASE + PORT_MAX_TRIES - 1}.`);
    console.error('Encerre algum processo que as ocupe ou defina PANDANEWS_UI_PORT.');
    process.exit(1);
  }
  const server = createUiServer();
  server.once('error', (err) => {
    if (err && err.code === 'EADDRINUSE') {
      console.log(`Porta ${port} ocupada — tentando ${port + 1}...`);
      listenUi(port + 1, attempt + 1);
    } else {
      console.error(`Erro no servidor de UI: ${err && err.message}`);
      process.exit(1);
    }
  });
  server.listen(port, '127.0.0.1', () => {
    uiServer = server;
    console.log(`PandaNews ativo em http://127.0.0.1:${port} — abra no seu navegador.`);
    console.log('Pressione Ctrl+C para encerrar o launcher.');
  });
}

// ------------------------------------------------------- backend destacado

let backendPid = null; // PID do backend que ESTA sessão iniciou (null = reaproveitado)

// Descobre um backend já em execução LENDO O LOCK GLOBAL
// (~/.pandanews/pandanews.pid), não a pasta do pacote — que o npx apaga ao
// atualizar. Devolve o PID registado e a porta que respondeu.
async function backendJaRodando(home) {
  const lock = lerPidGlobal(home);
  if (!lock) return null;
  const pid = lock.backend;
  if (!Number.isInteger(pid) || pid <= 0) return null;
  // procura o backend em qualquer porta candidata (a que gravou o lock)
  for (let port = API_PORT_BASE; port < API_PORT_BASE + PORT_MAX_TRIES; port++) {
    if (await portaAberta(port)) return { pid, port };
  }
  return null;
}

async function esperarBackend(port) {
  for (let i = 0; i < BACKEND_POLL_ATTEMPTS; i++) {
    if (await portaAberta(port)) return true;
    await new Promise((r) => setTimeout(r, BACKEND_POLL_MS));
  }
  return false;
}

// Sobe o uvicorn em grupo de processos próprio: detached (novo grupo no
// Windows), windowsHide (sem janela preta) e stdio direto no arquivo de log.
// No Windows sobe o interpretador BASE + PYTHONPATH do venv — um único
// processo, sem o redirector que abria a janela de console (ver pythonBin).
async function startBackend(home) {
  const port = await findFreePort(API_PORT_BASE, PORT_MAX_TRIES);
  if (port !== API_PORT_BASE) {
    console.log(`Porta ${API_PORT_BASE} ocupada — backend usando ${port}.`);
  }
  activeBackendPort = port;

  const logPath = join(home, 'data', 'backend.log');
  const bootstrapLine = `--- ${new Date().toISOString()} — iniciando backend (porta ${port}) ---\n`;
  appendFileSync(logPath, bootstrapLine);
  // stdio por FD (obrigatório com detached no Windows: async forks não aceitam path)
  const logFd = openSync(logPath, 'a');

  console.log(`Iniciando backend FastAPI em http://127.0.0.1:${port} ... (log: ${logPath})`);
  const python = spawn(
    pythonBin(home),
    ['-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', String(port)],
    {
      cwd: codeDir, // SEMPRE o runtime permanente — nunca o cache do npx (EBUSY)
      detached: true, // CREATE_NEW_PROCESS_GROUP no Windows — imune a Ctrl+C do console
      windowsHide: true, // sem janela de console fantasma
      stdio: ['ignore', logFd, logFd], // saída direto no arquivo (append) — não herda console
      env: pythonEnv(home),
    },
  );
  closeSync(logFd); // o filho tem sua própria cópia herdada
  python.unref(); // o launcher não morre com o backend e vice-versa
  backendPid = python.pid ?? null;
  // Lock GLOBAL (~/.pandanews/pandanews.pid) — fora da pasta do pacote, que
  // o npx apaga ao atualizar. Guarda o launcher E o backend: `pandanews kill`
  // e o auto-kill do arranque seguinte precisam dos dois.
  escreverPidGlobal(home, process.pid, backendPid, port);

  if (await esperarBackend(port)) {
    console.log(`Backend no ar em http://127.0.0.1:${port} (sobrevive a Ctrl+C — encerrado apenas por este launcher).`);
    return true;
  }
  console.error('Backend não respondeu a tempo — verifique o log completo em:');
  console.error(`  ${logPath}`);
  return false;
}

// Watchdog de saúde: spawn destacado não emite eventos de exit confiáveis —
// a porta é polidada a cada 10s. FALHAS_PARA_REINICIAR leituras ruins
// consecutivas disparam um reinício, mas no MÁXIMO MAX_REINICIOS vezes:
// sem essa trava, um backend que não consegue subir de jeito nenhum (porta
// tomada por órfão, dependência quebrada) viraria um loop infinito de spawns
// — e cada spawn no Windows é candidato a uma janela de console.
const FALHAS_PARA_REINICIAR = 3;
const MAX_REINICIOS = 3;

let falhasSaude = 0;
let reinicios = 0; // tentativas de reinício mal-sucedidas EM SEQUÊNCIA

function iniciarWatchdog(home) {
  const timer = setInterval(async () => {
    if (await portaAberta(activeBackendPort)) {
      //backend respondendo: zera as duas contagens (queda pontual não punida)
      falhasSaude = 0;
      reinicios = 0;
      return;
    }

    falhasSaude += 1;
    if (falhasSaude < FALHAS_PARA_REINICIAR) return;

    // --- teto de tentativas atingido: para tudo em vez de loop infinito ---
    if (reinicios >= MAX_REINICIOS) {
      clearInterval(timer);
      // encerra o backend zumbi por código, silenciosamente
      if (backendPid) encerrarPorPid(backendPid, `Backend (PID ${backendPid}) encerrado após ${MAX_REINICIOS} falhas.`);
      console.error('');
      console.error(`O backend não respondeu em http://127.0.0.1:${activeBackendPort} após ${MAX_REINICIOS} tentativas de reinício.`);
      console.error('O launcher está sendo encerrado para não entrar em loop infinito.');
      console.error(`Diagnóstico completo em: ${join(home, 'data', 'backend.log')}`);
      console.error('Se a porta estiver ocupada por outra instância, encerre-a ou defina PANDANEWS_API_PORT.');
      process.exit(1);
      return;
    }

    falhasSaude = 0;

    // --- reaproveita backend vivo em vez de empilhar outra instância ---
    // backend duplicado era o que fazia a porta "morrer" para o proxy e
    // disparava reinício atrás de reinício.
    const existente = await backendJaRodando(home);
    if (existente) {
      console.log(`Backend já em execução (PID ${existente.pid}) na porta ${existente.port} — reaproveitando (sem subir outra instância).`);
      activeBackendPort = existente.port;
      backendPid = null;
      return;
    }

    // --- reinício ---
    reinicios += 1;
    console.error(`Backend não responde — reiniciando... (tentativa ${reinicios} de ${MAX_REINICIOS})`);
    backendPid = null;
    const subiu = await startBackend(home);
    if (subiu) {
      // conseguiu subir: a próxima leitura saudável zera o contador
      console.log('Backend reerguido pelo watchdog.');
    }
  }, 10000);
  timer.unref();
}

// ---------------------------------------------------------------- execução

export async function runStart() {
  const home = resolveHome();
  if (!existsSync(join(home, '.runtime', '.ready'))) {
    console.log('Runtime não encontrado — instalando tudo (Python portátil + dependências)...');
    await runInstall({});
  }
  if (!existsSync(venvBin(home))) {
    console.log('Runtime Python ausente. Execute o comando com `install` primeiro:');
    console.log('  npx --yes @danhachuel/pandanews install');
    process.exitCode = 1;
    return;
  }

  // 0) RUNTIME PERMANENTE (fix definitivo do EBUSY): o servidor NUNCA sobe
  //    de dentro do cache do npx. A cópia em ~/.pandanews/runtime é criada
  //    aqui se faltar (barato: sem download, sem pip) ou atualizada quando
  //    a versão do pacote mudar. Em checkout de desenvolvimento, a raiz do
  //    repositório serve de código.
  const runtime = runtimeDir(home);
  const versaoPacote = (() => {
    try {
      return JSON.parse(readFileSync(join(PKG_ROOT, 'package.json'), 'utf8')).version || '';
    } catch {
      return '';
    }
  })();
  const versaoRuntime = existsSync(join(runtime, '.version'))
    ? readFileSync(join(runtime, '.version'), 'utf8').trim()
    : '';
  if (!existsSync(join(runtime, 'backend', 'app', 'main.py'))) {
    console.log('Preparando o runtime permanente (~/.pandanews/runtime) — o servidor não roda mais do cache do npx...');
    instalarCodigoRuntime(home);
  } else if (versaoPacote && versaoRuntime !== versaoPacote) {
    console.log(`Runtime defasado (${versaoRuntime || 'sem versão'} → ${versaoPacote}) — atualizando a cópia...`);
    instalarCodigoRuntime(home);
  }
  if (existsSync(join(runtime, 'backend', 'app', 'main.py'))) {
    codeDir = runtime;
  } else if (existsSync(join(PKG_ROOT, 'backend', 'app', 'main.py'))) {
    codeDir = PKG_ROOT; // desenvolvimento (checkout git)
  } else {
    console.error('Código do backend não encontrado. Execute o comando com `install` primeiro:');
    console.error('  npx --yes @danhachuel/pandanews install');
    process.exitCode = 1;
    return;
  }

  // 1) MATA A INSTÂNCIA ANTERIOR antes de subir a nova.
  //    O backend roda destacado e sobrevive ao terminal — sem isto, cada
  //    `pandanews start` empilhava outro backend zombie (medido: 2 uvicorns
  //    em 8000 e 8001, lock a apontar para o processo errado) e o utilizador
  //    ficava com a UI nova a ser servida por um backend de versão velha.
  //    Duas redes: PIDs do lock global + quem estiver dono das portas.
  await matarInstanciasAntigas(home);

  // 2) backend fresco — sempre. Nada a reaproveitar: matámos tudo acima.
  const backendOk = await startBackend(home);

  // 3) interface
  listenUi(UI_PORT_BASE, 1);

  // watchdog de saúde do backend (reergue em quedas silenciosas)
  iniciarWatchdog(home);

  // 4) sinais: encerramento SEMPRE por código, nunca por propagação do terminal
  const encerrarTudo = () => {
    console.log('\nEncerrando PandaNews...');
    if (backendPid) {
      encerrarPorPid(backendPid, `Backend (PID ${backendPid}) encerrado — log: ${join(home, 'data', 'backend.log')}`);
    } else {
      console.log('Nenhum backend foi iniciado por esta sessão.');
    }
    limparPidGlobal(home); // o lock global morre com a sessão
    process.exit(0);
  };
  process.on('SIGINT', encerrarTudo);
  process.on('SIGTERM', () => {
    if (backendPid) matarArvore(backendPid);
    limparPidGlobal(home);
    process.exit(0);
  });

  if (!backendOk) {
    process.exitCode = 1;
  }
}

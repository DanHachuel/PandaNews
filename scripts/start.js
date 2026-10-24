// Inicia o PandaNews: backend FastAPI (127.0.0.1:8000+) + UI (127.0.0.1:4030+).
//
// Fluxo de um único comando: se o runtime não estiver provisionado, executa o
// install completo (Python portátil + dependências) antes de subir os
// servidores. Ambas as portas têm fallback automático (API: 8000, 8001, ...;
// UI: 4030, 4031, ...). O sistema NÃO abre o navegador: o endereço é exibido
// no terminal e o usuário decide quando abrir.
//
// Robustez: o output do backend é gravado em <home>/data/backend.log (completo)
// e, se o processo morrer de forma anormal, o backend reinicia sozinho (até 5
// vezes) — a UI não cai junto. Logs de acesso não poluem o console.
import { createWriteStream, existsSync, readFileSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { createServer, request as httpRequest } from 'node:http';
import net from 'node:net';
import { join, extname } from 'node:path';
import { resolveHome, runInstall, PKG_ROOT } from './install.js';

const API_PORT_BASE = Number(process.env.PANDANEWS_API_PORT || 8000);
const UI_PORT_BASE = Number(process.env.PANDANEWS_UI_PORT || 4030);
const PORT_MAX_TRIES = 20;
const BACKEND_MAX_RESTARTS = 5;
const BACKEND_RESTART_DELAY_MS = 3000;
const BACKEND_HEALTHY_UPTIME_MS = 60000;

let activeBackendPort = API_PORT_BASE;

const FAVICON_URI = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='20' fill='%230b1220'/%3E%3Ccircle cx='25' cy='28' r='13' fill='%23e6edf3'/%3E%3Ccircle cx='75' cy='28' r='13' fill='%23e6edf3'/%3E%3Ccircle cx='50' cy='52' r='30' fill='%23e6edf3'/%3E%3Cellipse cx='37' cy='48' rx='9' ry='11' fill='%230b1220' transform='rotate(-15 37 48)'/%3E%3Cellipse cx='63' cy='48' rx='9' ry='11' fill='%230b1220' transform='rotate(15 63 48)'/%3E%3Ccircle cx='38' cy='49' r='3' fill='%2322c55e'/%3E%3Ccircle cx='62' cy='49' r='3' fill='%2322c55e'/%3E%3Cellipse cx='50' cy='62' rx='5' ry='4' fill='%230b1220'/%3E%3C/svg%3E";

function venvBin(home) {
  return process.platform === 'win32'
    ? join(home, '.runtime', 'venv', 'Scripts', 'python.exe')
    : join(home, '.runtime', 'venv', 'bin', 'python');
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

// Testa se uma porta pode ser vinculada (probe real de bind).
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

function createUiServer() {
  const distDir = join(PKG_ROOT, 'frontend', 'dist');
  return createServer((req, res) => {
    if (req.url.startsWith('/api')) {
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
    console.log('Pressione Ctrl+C para encerrar.');
  });
}

let backendProc = null;
let backendRestarts = 0;

// Sobe o backend com saída completa em <home>/data/backend.log; o console
// mantém apenas stderr (banner, erros, tracebacks). Se o processo morrer de
// forma anormal, reinicia sozinho (até 5 tentativas).
function startBackend(home) {
  console.log(`Iniciando backend FastAPI em http://127.0.0.1:${activeBackendPort} ...`);
  const uvicorn = spawn(
    venvBin(home),
    ['-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', String(activeBackendPort)],
    {
      cwd: PKG_ROOT,
      stdio: ['inherit', 'pipe', 'pipe'],
      env: { ...process.env, PANDANEWS_HOME: home },
    },
  );
  backendProc = uvicorn;

  const logPath = join(home, 'data', 'backend.log');
  const logStream = createWriteStream(logPath, { flags: 'a' });
  logStream.write(`\n--- ${new Date().toISOString()} — iniciando backend (pid ${uvicorn.pid}, porta ${activeBackendPort}) ---\n`);
  // Logs de acesso do uvicorn (stdout) vão SOMENTE para o arquivo: o terminal
  // fica limpo. O stderr (banner, WARNING/ERROR e tracebacks) é visível.
  uvicorn.stdout.on('data', (chunk) => {
    logStream.write(chunk);
  });
  uvicorn.stderr.on('data', (chunk) => {
    process.stderr.write(chunk);
    logStream.write(chunk);
  });

  const startedAt = Date.now();
  uvicorn.on('exit', (code) => {
    logStream.end(`--- backend encerrou com código ${code} ---\n`);
    if (code === 0 || code === null) {
      return;
    }
    if (Date.now() - startedAt > BACKEND_HEALTHY_UPTIME_MS) {
      backendRestarts = 0; // rodou saudável por tempo suficiente: zera o contador
    }
    backendRestarts += 1;
    if (backendRestarts > BACKEND_MAX_RESTARTS) {
      console.error(`Backend caiu ${backendRestarts - 1}x seguidas — desistindo.`);
      console.error(`Log completo do backend: ${logPath}`);
      process.exit(1);
    }
    console.error(`Backend encerrou com código ${code} — reiniciando em 3s (tentativa ${backendRestarts}/${BACKEND_MAX_RESTARTS})...`);
    setTimeout(() => startBackend(home), BACKEND_RESTART_DELAY_MS);
  });
}

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

  // Fallback de portas: API em 8000, 8001, ...; UI em 4030, 4031, ...
  activeBackendPort = await findFreePort(API_PORT_BASE, PORT_MAX_TRIES);
  if (activeBackendPort !== API_PORT_BASE) {
    console.log(`Porta ${API_PORT_BASE} ocupada — backend usando ${activeBackendPort}.`);
  }

  startBackend(home);
  listenUi(UI_PORT_BASE, 1);

  process.on('exit', () => {
    if (uiServer) uiServer.close();
    if (backendProc) backendProc.kill();
  });
  process.on('SIGINT', () => process.exit(0));
  process.on('SIGTERM', () => process.exit(0));
}

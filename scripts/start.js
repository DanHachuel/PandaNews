// Inicia o PandaNews: backend FastAPI (127.0.0.1:8000) + UI (127.0.0.1:4030+).
//
// Fluxo de um único comando (padrão Thunderbolt): se o runtime não estiver
// provisionado, executa o install completo (Python portátil + dependências)
// antes de subir os servidores. A UI começa em PANDANEWS_UI_PORT (padrão 4030)
// e, se a porta estiver ocupada, tenta automaticamente a seguinte (4031, ...).
import { existsSync, readFileSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { join, extname } from 'node:path';
import { resolveHome, runInstall, PKG_ROOT } from './install.js';

const BACKEND_PORT = Number(process.env.PANDANEWS_API_PORT || 8000);
const UI_PORT_BASE = Number(process.env.PANDANEWS_UI_PORT || 4030);
const UI_PORT_MAX_TRIES = 20;

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
<head><meta charset="utf-8"><title>PandaNews</title></head>
<body style="font-family: Inter, system-ui, sans-serif; background: #0b1220; color: #e6edf3; display: flex; min-height: 100vh; align-items: center; justify-content: center;">
  <div style="text-align: center;">
    <h1 style="font-size: 3rem; margin: 0;">🐼 PandaNews</h1>
    <p style="color: #9aa7b5;">Backend ativo em <a style="color: #22c55e;" href="http://127.0.0.1:8000/api/v1/health">127.0.0.1:8000</a></p>
    <p style="color: #9aa7b5;">A UI React completa chega na versão 0.2.00 (Fases 1 a 3 do plano).</p>
  </div>
</body>
</html>`;
}

let uiServer = null;

function createUiServer() {
  const distDir = join(PKG_ROOT, 'frontend', 'dist');
  return createServer((req, res) => {
    const url = req.url.split('?')[0];
    const filePath = join(distDir, url === '/' ? 'index.html' : url.slice(1));
    if (!existsSync(filePath)) {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(placeholderPage());
      return;
    }
    res.writeHead(200, { 'Content-Type': MIME[extname(filePath)] || 'application/octet-stream' });
    res.end(readFileSync(filePath));
  });
}

function listenUi(port, attempt) {
  if (attempt > UI_PORT_MAX_TRIES) {
    console.error(`Nenhuma porta livre entre ${UI_PORT_BASE} e ${UI_PORT_BASE + UI_PORT_MAX_TRIES - 1}.`);
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
    console.log(`PandaNews ativo em http://127.0.0.1:${port}`);
    console.log('Pressione Ctrl+C para encerrar.');
    openBrowser(`http://127.0.0.1:${port}`);
  });
}

async function openBrowser(url) {
  try {
    const { default: open } = await import('open');
    await open(url);
  } catch {
    /* ambiente sem navegador (ex.: CI) */
  }
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

  console.log(`Iniciando backend FastAPI em http://127.0.0.1:${BACKEND_PORT} ...`);
  const uvicorn = spawn(
    venvBin(home),
    ['-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
    { cwd: PKG_ROOT, stdio: 'inherit' },
  );
  uvicorn.on('exit', (code) => {
    if (code !== 0 && code !== null) {
      console.error(`Backend encerrou com código ${code}.`);
      process.exit(code ?? 1);
    }
  });

  listenUi(UI_PORT_BASE, 1);

  process.on('exit', () => {
    if (uiServer) uiServer.close();
    uvicorn.kill();
  });
  process.on('SIGINT', () => process.exit(0));
  process.on('SIGTERM', () => process.exit(0));
}

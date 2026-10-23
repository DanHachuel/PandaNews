// Instalador do runtime PandaNews.
//
// Provisiona tudo em um único comando (padrão Thunderbolt):
// 1. estrutura de pastas (data/, .runtime/)
// 2. Python 3.12.7 portátil via python-build-standalone (sem Python pré-instalado)
// 3. virtualenv em .runtime/venv
// 4. dependências do backend (backend/requirements.txt)
// 5. marcadores de estado (.runtime/.ready, .runtime/.python-ready)
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
export const PKG_ROOT = join(__dirname, '..');

const PYTHON_VERSION = '3.12.7';
const PYTHON_RELEASE = '20241016';

// Raiz de instalação: PANDANEWS_HOME sobrepõe o padrão (raiz do pacote instalado).
export function resolveHome() {
  return process.env.PANDANEWS_HOME ? resolve(process.env.PANDANEWS_HOME) : PKG_ROOT;
}

// Detecta plataforma e asset de python-build-standalone.
export function detectPlatform() {
  const arch = process.arch === 'arm64' ? 'aarch64' : 'x86_64';
  if (process.platform === 'win32') {
    return { os: 'windows', arch, asset: `${arch}-pc-windows-msvc-shared-install_only.tar.gz` };
  }
  if (process.platform === 'darwin') {
    return { os: 'macos', arch, asset: `${arch}-apple-darwin-install_only.tar.gz` };
  }
  return { os: 'linux', arch, asset: `${arch}-unknown-linux-gnu-install_only.tar.gz` };
}

function pythonArchiveUrl(platform) {
  const base = 'https://github.com/astral-sh/python-build-standalone/releases/download';
  return `${base}/${PYTHON_RELEASE}/cpython-${PYTHON_VERSION}+${PYTHON_RELEASE}-${platform.asset}`;
}

function pythonBin(home) {
  return process.platform === 'win32'
    ? join(home, '.runtime', 'python', 'python.exe')
    : join(home, '.runtime', 'python', 'bin', 'python3');
}

function venvBin(home) {
  return process.platform === 'win32'
    ? join(home, '.runtime', 'venv', 'Scripts', 'python.exe')
    : join(home, '.runtime', 'venv', 'bin', 'python');
}

async function downloadPython(home, platform) {
  const url = pythonArchiveUrl(platform);
  const runtimeDir = join(home, '.runtime');
  const downloadsDir = join(runtimeDir, 'downloads');
  const archive = join(downloadsDir, `cpython-${PYTHON_VERSION}+${PYTHON_RELEASE}-${platform.asset}`);
  mkdirSync(downloadsDir, { recursive: true });
  console.log(`Baixando Python ${PYTHON_VERSION} portátil (${platform.os} ${platform.arch})...`);
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Falha no download do Python (${res.status}): ${url}`);
  const buf = Buffer.from(await res.arrayBuffer());
  writeFileSync(archive, buf);
  console.log(`Download concluído (${(buf.length / 1024 / 1024).toFixed(1)} MB). Extraindo...`);
  const tar = spawnSync('tar', ['-xzf', archive, '-C', runtimeDir]);
  if (tar.status !== 0) throw new Error('Falha ao extrair o Python portátil (tar).');
  if (!existsSync(pythonBin(home))) {
    throw new Error('Extração do Python concluída, mas o binário não foi encontrado.');
  }
  console.log(`Python ${PYTHON_VERSION} pronto em ${join(runtimeDir, 'python')}`);
}

function createVenv(home) {
  console.log('Criando virtualenv...');
  const venv = spawnSync(pythonBin(home), ['-m', 'venv', join(home, '.runtime', 'venv')], { stdio: 'inherit' });
  if (venv.status !== 0) throw new Error('Falha ao criar o virtualenv.');
  if (!existsSync(venvBin(home))) throw new Error('Virtualenv criado, mas o binário não foi encontrado.');
}

function installDeps(home) {
  console.log('Instalando dependências do backend (pode levar alguns minutos)...');
  const req = join(PKG_ROOT, 'backend', 'requirements.txt');
  const pip = spawnSync(
    venvBin(home),
    ['-m', 'pip', 'install', '--disable-pip-version-check', '-r', req],
    { stdio: 'inherit' },
  );
  if (pip.status !== 0) throw new Error('Falha ao instalar as dependências do backend.');
}

export async function runInstall({ skipPythonDeps = false } = {}) {
  const home = resolveHome();
  const platform = detectPlatform();

  console.log(`PandaNews install — plataforma: ${platform.os} (${platform.arch})`);
  console.log(`Raiz do runtime: ${home}`);

  // Estrutura de pastas do runtime local
  const dirs = [
    join(home, 'data'),
    join(home, 'data', 'imagens'),
    join(home, '.runtime'),
  ];
  for (const dir of dirs) {
    mkdirSync(dir, { recursive: true });
  }

  if (skipPythonDeps) {
    console.log('--skip-python-deps: instalação estrutural (uso em CI).');
  } else if (existsSync(join(home, '.runtime', '.python-ready'))) {
    console.log('Runtime Python já provisionado — nada a fazer.');
  } else {
    if (!existsSync(pythonBin(home))) {
      await downloadPython(home, platform);
    } else {
      console.log('Python portátil já presente.');
    }
    if (!existsSync(venvBin(home))) {
      createVenv(home);
    } else {
      console.log('Virtualenv já presente.');
    }
    installDeps(home);
    writeFileSync(join(home, '.runtime', '.python-ready'), new Date().toISOString());
    console.log('Dependências instaladas. Runtime Python pronto.');
  }

  writeFileSync(join(home, '.runtime', '.ready'), new Date().toISOString());
  console.log('Instalação concluída.');
  return home;
}

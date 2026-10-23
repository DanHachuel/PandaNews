// Instalador do runtime PandaNews.
//
// O runtime vive em um diretório ESTÁVEL por usuário (~/.pandanews, ou
// PANDANEWS_HOME), separado da pasta do pacote npm: upgrades de versão não
// reinstalam Python/dependências. O instalador detecta o que já existe e só
// executa o que falta:
//   1. estrutura de pastas (data/, .runtime/)
//   2. Python 3.12.7 portátil (python-build-standalone)
//   3. virtualenv (.runtime/venv)
//   4. dependências do backend — com fingerprint de requirements.txt + versão
//      do Python: pip só roda quando mudam
//   5. migração de runtimes legados (pasta do pacote / cache do npx)
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import os from 'node:os';
import fse from 'fs-extra';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
export const PKG_ROOT = join(__dirname, '..');

const PYTHON_VERSION = '3.12.7';
const PYTHON_RELEASE = '20241016';

// Raiz de instalação estável: PANDANEWS_HOME sobrepõe; padrão ~/.pandanews.
export function resolveHome() {
  if (process.env.PANDANEWS_HOME) return resolve(process.env.PANDANEWS_HOME);
  return join(os.homedir(), '.pandanews');
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

function pythonSpec() {
  return `cpython-${PYTHON_VERSION}+${PYTHON_RELEASE}`;
}

// Fingerprint das dependências: muda quando o requirements.txt ou a versão do
// Python mudam — só então o pip roda de novo.
function depsFingerprint() {
  const reqPath = join(PKG_ROOT, 'backend', 'requirements.txt');
  const req = existsSync(reqPath) ? readFileSync(reqPath, 'utf8') : '';
  const hash = createHash('sha256').update(req).digest('hex').slice(0, 16);
  return `${pythonSpec()};req=${hash}`;
}

// Procura runtimes legados: na própria pasta do pacote (layout antigo) e nos
// buckets do cache do npx (versões anteriores do pacote). Best effort.
function findLegacyRuntime() {
  const candidates = [];
  const marker = '.python-ready';
  const sameDir = join(PKG_ROOT, '.runtime');
  if (existsSync(join(sameDir, marker))) candidates.push(sameDir);
  try {
    const cacheBase = process.env.npm_config_cache
      ? process.env.npm_config_cache
      : join(os.homedir(), process.platform === 'win32' ? join('AppData', 'Local', 'npm-cache') : '.npm');
    const npxRoot = join(cacheBase, '_npx');
    if (existsSync(npxRoot)) {
      for (const entry of readdirSync(npxRoot)) {
        const rt = join(npxRoot, entry, 'node_modules', '@danhachuel', 'pandanews', '.runtime');
        if (existsSync(join(rt, marker))) candidates.push(rt);
      }
    }
  } catch { /* best effort */ }
  if (candidates.length === 0) return null;
  candidates.sort((a, b) => statSync(join(b, marker)).mtimeMs - statSync(join(a, marker)).mtimeMs);
  return candidates[0];
}

// Reaproveita um runtime legado movendo-o para o home estável. Pula se o home
// já tiver um runtime válido, ou se PANDANEWS_SKIP_MIGRATE estiver definido.
function migrateLegacyRuntime(home) {
  if (process.env.PANDANEWS_SKIP_MIGRATE) return;
  const targetRuntime = join(home, '.runtime');
  if (existsSync(join(targetRuntime, '.python-ready'))) return;
  const legacy = findLegacyRuntime();
  if (!legacy) return;
  console.log(`Runtime já instalado encontrado em ${legacy} — reaproveitando (movendo para ${home})...`);
  try {
    // Remove stubs vazios criados antes da migração: rename de diretório no
    // Windows falha (EPERM) quando o destino já existe.
    rmSync(targetRuntime, { recursive: true, force: true });
    fse.moveSync(legacy, targetRuntime);
    const legacyData = join(dirname(legacy), 'data');
    if (existsSync(legacyData)) {
      fse.copySync(legacyData, join(home, 'data'));
      rmSync(legacyData, { recursive: true, force: true });
    }
    console.log('Migração concluída.');
  } catch (err) {
    console.log(`Migração falhou (${err && err.message}) — seguindo com instalação nova.`);
  }
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
  } else {
    migrateLegacyRuntime(home);

    // Versão do Python mudou? Limpa o runtime antigo antes de reinstalar.
    const specFile = join(home, '.runtime', '.python-spec');
    const wantSpec = pythonSpec();
    const haveSpec = existsSync(specFile) ? readFileSync(specFile, 'utf8').trim() : '';
    if (haveSpec && haveSpec !== wantSpec) {
      console.log('Versão do Python do runtime mudou — limpando instalação antiga...');
      rmSync(join(home, '.runtime', 'python'), { recursive: true, force: true });
      rmSync(join(home, '.runtime', 'venv'), { recursive: true, force: true });
    }

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

    // Dependências: só roda o pip quando o fingerprint muda.
    const fpFile = join(home, '.runtime', '.deps-fingerprint');
    const haveFp = existsSync(fpFile) ? readFileSync(fpFile, 'utf8').trim() : '';
    const wantFp = depsFingerprint();
    if (haveFp !== wantFp) {
      installDeps(home);
      writeFileSync(fpFile, wantFp);
      console.log('Dependências em dia.');
    } else {
      console.log('Dependências já instaladas — nada a fazer.');
    }

    writeFileSync(specFile, wantSpec);
    writeFileSync(join(home, '.runtime', '.python-ready'), new Date().toISOString());
  }

  writeFileSync(join(home, '.runtime', '.ready'), new Date().toISOString());
  console.log('Instalação concluída.');
  return home;
}

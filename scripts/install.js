// Instalador do runtime PandaNews.
//
// Fase 0 (0.1.00): detecta plataforma, cria a estrutura de pastas (data/, .runtime/)
// e grava o marcador .runtime/.ready. O provisionamento completo de Python
// portátil + venv + dependências chega na versão 0.2.00 (Fase 4 do plano).
import { mkdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
export const PKG_ROOT = join(__dirname, '..');

// Raiz de instalação: PANDANEWS_HOME sobrepõe o padrão (raiz do pacote instalado).
export function resolveHome() {
  return process.env.PANDANEWS_HOME ? resolve(process.env.PANDANEWS_HOME) : PKG_ROOT;
}

// Detecta plataforma e arquitetura para o download de python-build-standalone (Fase 4).
export function detectPlatform() {
  const arch = process.arch === 'arm64' ? 'aarch64' : 'x86_64';
  if (process.platform === 'win32') {
    return { os: 'windows', arch, asset: `${arch}-pc-windows-msvc-shared-install_only.zip` };
  }
  if (process.platform === 'darwin') {
    return { os: 'macos', arch, asset: `${arch}-apple-darwin-install_only.tar.gz` };
  }
  return { os: 'linux', arch, asset: `${arch}-unknown-linux-gnu-install_only.tar.gz` };
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

  // Fase 4 (0.2.00): download de Python 3.12 portátil, venv e requirements.
  if (skipPythonDeps) {
    console.log('--skip-python-deps: instalação estrutural (uso em CI).');
  } else {
    console.log('Provisionamento de Python portátil e dependências: chega na versão 0.2.00 (Fase 4).');
  }

  writeFileSync(join(home, '.runtime', '.ready'), new Date().toISOString());
  console.log('Estrutura pronta. Runtime inicializado.');
  return home;
}

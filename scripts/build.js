// Compila o frontend de desenvolvimento (frontend/ -> frontend/dist).
// A UI React + Vite + Tailwind é inicializada na Fase 2 do plano.
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const PKG_ROOT = join(__dirname, '..');

export async function runBuild() {
  const frontendDir = join(PKG_ROOT, 'frontend');
  if (!existsSync(join(frontendDir, 'package.json'))) {
    console.log('frontend/ ainda não foi inicializado — chega na Fase 2 (versão 0.2.00).');
    return;
  }
  const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  console.log('Instalando dependências do frontend...');
  const install = spawnSync(npmCmd, ['install'], { cwd: frontendDir, stdio: 'inherit' });
  if (install.status !== 0) throw new Error('Falha ao instalar dependências do frontend.');
  console.log('Compilando o frontend...');
  const build = spawnSync(npmCmd, ['run', 'build'], { cwd: frontendDir, stdio: 'inherit' });
  if (build.status !== 0) throw new Error('Falha ao compilar o frontend.');
  console.log('Frontend compilado em frontend/dist.');
}

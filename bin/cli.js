#!/usr/bin/env node
// PandaNews CLI (@danhachuel/pandanews)
// Comandos: install | start (padrão) | build | help | version
import { readFileSync } from 'node:fs';
import { runInstall } from '../scripts/install.js';
import { runStart } from '../scripts/start.js';
import { runBuild } from '../scripts/build.js';

const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));

const args = process.argv.slice(2);
const command = args.find((a) => !a.startsWith('--')) || 'start';
const flags = new Set(args.filter((a) => a.startsWith('--')));

function printHelp() {
  console.log(`
PandaNews ${pkg.version} — automação de blogs de notícias com IA

Uso:
  pandanews install   Prepara o runtime local (estrutura + Python portátil)
  pandanews           Inicia backend (127.0.0.1:8000) e UI (127.0.0.1:3030)
  pandanews build     Compila o frontend de desenvolvimento

Opções:
  --skip-python-deps  Instalação estrutural sem Python (uso em CI)
  --help              Mostra esta ajuda
  --version           Mostra a versão
`);
}

async function main() {
  if (flags.has('--help') || command === 'help') {
    printHelp();
    return;
  }
  if (flags.has('--version') || command === 'version') {
    console.log(pkg.version);
    return;
  }
  if (command === 'install') {
    await runInstall({ skipPythonDeps: flags.has('--skip-python-deps') });
  } else if (command === 'start') {
    await runStart();
  } else if (command === 'build') {
    await runBuild();
  } else {
    console.error(`Comando desconhecido: ${command}`);
    printHelp();
    process.exitCode = 1;
  }
}

main().catch((err) => {
  console.error(`pandanews: ${err && err.message ? err.message : err}`);
  process.exitCode = 1;
});

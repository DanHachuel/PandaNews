#!/usr/bin/env node
// PandaNews CLI (@danhachuel/pandanews)
// Comandos: install | start (padrão) | kill | build | help | version
import { readFileSync } from 'node:fs';
import { runInstall } from '../scripts/install.js';
import { runStart, comandoKill } from '../scripts/start.js';
import { runBuild } from '../scripts/build.js';
import { resolveHome } from '../scripts/install.js';

const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));

const args = process.argv.slice(2);
const command = args.find((a) => !a.startsWith('--')) || 'start';
const flags = new Set(args.filter((a) => a.startsWith('--')));

function printHelp() {
  console.log(`
PandaNews ${pkg.version} — automação de blogs de notícias com IA

Uso:
  pandanews install   Prepara o runtime local (estrutura + Python portátil)
  pandanews           Inicia backend (127.0.0.1:8000) e UI (127.0.0.1:4030)
  pandanews kill      Encerra backend e launcher em background (também: stop)
  pandanews build     Compila o frontend de desenvolvimento

Opções:
  --skip-python-deps  Instalação estrutural sem Python (uso em CI)
  --help              Mostra esta ajuda
  --version           Mostra a versão

Atualizar de versão (recomendado no Windows):
  npm install -g @danhachuel/pandanews@latest
  O comando acima evita o erro EBUSY do npx, que tenta renomear a própria
  pasta de cache enquanto uma instância destacada ainda a segura.

Notas:
  O backend roda em background e sobrevive ao fechamento do terminal. Ao
  iniciar uma nova versão, o launcher encerra a instância anterior
  automaticamente; use 'pandanews kill' para encerrar sem reiniciar.
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
  } else if (command === 'kill' || command === 'stop') {
    // Encerramento explícito: lock global (~/.pandanews/pandanews.pid) +
    // quem estiver dono das portas. Sempre por código, sem janela de console.
    await comandoKill(resolveHome());
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

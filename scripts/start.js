// Inicia o PandaNews: backend FastAPI (127.0.0.1:8000) + UI estática (127.0.0.1:3030).
//
// Fase 0 (0.1.00): garante que o runtime esteja instalado e informa o status.
// Fase 4 (0.2.00): sobe o uvicorn, serve frontend/dist e abre o navegador.
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { resolveHome, runInstall } from './install.js';

export async function runStart() {
  const home = resolveHome();
  const readyMarker = join(home, '.runtime', '.ready');

  if (!existsSync(readyMarker)) {
    console.log('Runtime não encontrado — executando install...');
    await runInstall({});
  }

  console.log('');
  console.log('PandaNews 0.1.00 — versão inicial de bootstrap.');
  console.log('O backend FastAPI (127.0.0.1:8000) e a UI (127.0.0.1:3030) serão');
  console.log('servidos por este comando a partir da versão 0.2.00 (Fases 1 a 4 do plano).');
  console.log(`Raiz do runtime: ${home}`);
}

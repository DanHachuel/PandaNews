// Teste de regressão do isolamento de processos do launcher (scripts/start.js).
//
// Falha se as flags de isolamento forem removidas: detached (novo grupo de
// processos — imune a Ctrl+C do console no Windows), windowsHide (sem janela
// fantasma), stdio no arquivo (backend sobrevive ao terminal), unref e o
// arquivo backend.pid (encerramento gracioso por código).
//
// Roda em qualquer plataforma, inclusive no CI (Linux/ubuntu) — sem exigir o
// runtime Python completo.
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'scripts', 'start.js'), 'utf8');

const verificacoes = [
  [/detached:\s*true/, 'detached: true — grupo de processos próprio (CREATE_NEW_PROCESS_GROUP no Windows)'],
  [/windowsHide:\s*true/, 'windowsHide: true — sem janela de console fantasma'],
  [/stdio:\s*\['ignore',\s*logFd,\s*logFd\]/, "stdio: ['ignore', logFd, logFd] — saída do backend no arquivo (fd)"],
  [/openSync\(logPath, 'a'\)/, 'openSync do log em append (fd reaproveitado pelo filho)'],
  [/PYTHONUNBUFFERED/, 'PYTHONUNBUFFERED=1 — logs do backend sem buffer'],
  [/backend\.pid/, 'backend.pid — PID gravado para encerramento gracioso'],
  [/\.unref\(\)/, 'unref() — launcher não acopla o ciclo de vida ao backend'],
  [/taskkill/, 'encerramento no Windows via taskkill /PID /T (árvore de processos)'],
  [/process\.kill/, 'encerramento no Unix via signal no grupo de processos'],
];

let falhas = 0;
for (const [regex, descricao] of verificacoes) {
  const ok = regex.test(src);
  console.log(`${ok ? 'PASS' : 'FAIL'} — ${descricao}`);
  if (!ok) falhas += 1;
}

if (falhas > 0) {
  console.error(`Isolamento de processos: ${falhas} verificação(ões) falharam.`);
  process.exit(1);
}
console.log('Isolamento de processos: todas as verificações passaram.');

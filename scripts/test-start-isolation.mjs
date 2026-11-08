// Teste de regressão do isolamento de processos (regra permanente do AGENTS.md):
// NENHUM spawn/exec do launcher/instalador pode abrir janela de terminal (CMD,
// PowerShell, console Python) no computador do usuário.
//
// Cobre TODOS os pontos de entrada:
//   scripts/start.js    — backend uvicorn + taskkill + watchdog de reinício
//   scripts/install.js  — tar / venv / pip
//   scripts/build.js    — npm.cmd install e run build (shell: true)
//   bin/cli.js          — despacho de comandos
//   backend/**/*.py     — nenhuma chamada direta a subprocess/os.system
//
// Roda em qualquer plataforma, inclusive no CI (Linux/ubuntu) — sem exigir o
// runtime Python completo.
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

const falhas = [];

function assert(condicao, mensagem) {
  console.log(`${condicao ? 'PASS' : 'FAIL'} — ${mensagem}`);
  if (!condicao) falhas.push(mensagem);
}

// ---------------------------------------------------------------- utilidades

// Extrai o conteúdo entre delimitadores balanceados, começando em `inicio`
// (índice do delimitador de abertura). Ignora delimitadores dentro de strings.
function ateOFechamento(src, inicio, abre, fecha) {
  let profundidade = 1;
  let aspa = null;
  let escapando = false;
  for (let i = inicio + 1; i < src.length; i++) {
    const c = src[i];
    if (escapando) {
      escapando = false;
      continue;
    }
    if (c === '\\') {
      escapando = true;
      continue;
    }
    if (aspa) {
      if (c === aspa) aspa = null;
      continue;
    }
    if (c === "'" || c === '"' || c === '`') {
      aspa = c;
      continue;
    }
    if (c === abre) profundidade += 1;
    else if (c === fecha) {
      profundidade -= 1;
      if (profundidade === 0) return src.slice(inicio + 1, i);
    }
  }
  return src.slice(inicio + 1);
}

// Texto completo dos argumentos de uma chamada, a partir do '(' encontrado.
function argumentosDaChamada(src, indiceAbre) {
  return ateOFechamento(src, indiceAbre, '(', ')');
}

// Objetos literais de nível de módulo (const NOME = { ... }) — servem para
// resolver spreads como `...SILENT_WINDOWS` dentro das opções de spawn.
function constantesDeModulo(src) {
  const mapa = new Map();
  const regex = /const\s+([A-Za-z_$][\w$]*)\s*=\s*\{/g;
  let m;
  while ((m = regex.exec(src)) !== null) {
    const inicioChaves = m.index + m[0].length - 1;
    mapa.set(m[1], ateOFechamento(src, inicioChaves, '{', '}'));
  }
  return mapa;
}

// Uma referência a constante (solta ou via spread `...NOME`) é silenciosa
// apenas se a constante NOME trouxer windowsHide.
function referenciaConstanteSilenciosa(argTexto, constantes) {
  const regex = /([A-Za-z_$][\w$]*)/g;
  let m;
  while ((m = regex.exec(argTexto)) !== null) {
    const definicao = constantes.get(m[1]);
    if (definicao && /windowsHide:\s*true/.test(definicao)) return true;
  }
  return false;
}

// ------------------------------------------------------------ varredura JS

const PONTOS_DE_ENTRADA_JS = ['scripts/start.js', 'scripts/install.js', 'scripts/build.js', 'bin/cli.js'];

for (const relativo of PONTOS_DE_ENTRADA_JS) {
  const caminho = join(root, relativo);
  if (!existsSync(caminho)) {
    assert(false, `${relativo} — arquivo ausente`);
    continue;
  }
  const src = readFileSync(caminho, 'utf8');
  const constantes = constantesDeModulo(src);

  const chamadas = [...src.matchAll(/\b(spawn|spawnSync|exec|execSync|execFile|execFileSync)\s*\(/g)];
  let silenciosas = 0;
  for (const chamada of chamadas) {
    const indiceAbre = chamada.index + chamada[0].length - 1;
    const texto = argumentosDaChamada(src, indiceAbre);
    if (/windowsHide:\s*true/.test(texto) || referenciaConstanteSilenciosa(texto, constantes)) {
      silenciosas += 1;
    } else {
      const marca = `${chamada[1]}(${texto.slice(0, 60).replace(/\s+/g, ' ')}…)`;
      assert(false, `${relativo} — ${marca} sem windowsHide: true (abre janela de console no usuário)`);
    }
  }
  if (chamadas.length === 0) {
    assert(true, `${relativo} — nenhuma chamada de processo direta (sem risco de janela de console)`);
  } else {
    assert(
      silenciosas === chamadas.length,
      `${relativo} — ${silenciosas}/${chamadas.length} chamadas de processo com windowsHide: true`,
    );
  }
}

// ------------------------------------------- isolamento do backend (start.js)

const startSrc = readFileSync(join(root, 'scripts', 'start.js'), 'utf8');

for (const [regex, descricao] of [
  [/detached:\s*true/, 'detached: true — grupo de processos próprio (CREATE_NEW_PROCESS_GROUP no Windows)'],
  [/windowsHide:\s*true/, 'windowsHide: true — sem janela de console fantasma'],
  [/stdio:\s*\['ignore',\s*logFd,\s*logFd\]/, "stdio: ['ignore', logFd, logFd] — saída do backend no arquivo (fd)"],
  [/openSync\(logPath, 'a'\)/, 'openSync do log em append (fd reaproveitado pelo filho)'],
  [/PYTHONUNBUFFERED/, 'PYTHONUNBUFFERED=1 — logs do backend sem buffer'],
  [/backend\.pid/, 'backend.pid — PID gravado para encerramento gracioso'],
  [/\.unref\(\)/, 'unref() — launcher não acopla o ciclo de vida ao backend'],
  [/taskkill/, 'encerramento no Windows via taskkill /PID /T (árvore de processos)'],
  [/process\.kill/, 'encerramento no Unix via signal no grupo de processos'],
]) {
  assert(regex.test(startSrc), descricao);
}

// Uvicorn em produção JAMAIS com --reload/--workers: cada worker é um processo
// filho extra, que no Windows pode alocar console próprio e ignorar as flags
// do processo pai.
const uvicornExtras = startSrc.match(/['"]--(?:reload|workers)['"]/g);
assert(
  !uvicornExtras,
  `uvicorn sem --reload/--workers (nenhum processo filho extra no Windows)${
    uvicornExtras ? ` — encontrado: ${uvicornExtras.join(', ')}` : ''
  }`,
);

// ------------------------------------------------- kill/restart (funções)

// Extrai o corpo de uma função pelo nome — usado para auditar as rotinas de
// encerramento e de reinício isoladamente.
function corpoDaFuncao(src, nome) {
  const assinatura = src.indexOf(`function ${nome}(`);
  if (assinatura === -1) return '';
  // pula a lista de parâmetros e devolve o bloco entre {} do corpo
  const fechaParams = src.indexOf(')', assinatura);
  if (fechaParams === -1) return '';
  const abreCorpo = src.indexOf('{', fechaParams);
  if (abreCorpo === -1) return '';
  return ateOFechamento(src, abreCorpo, '{', '}');
}

// 1) taskkill / kill do encerramento — silencioso de verdade
const corpoEncerrar = corpoDaFuncao(startSrc, 'encerrarPorPid');
assert(corpoEncerrar.length > 0, 'encerrarPorPid existe (rotina de kill do launcher)');
assert(
  /windowsHide:\s*true/.test(corpoEncerrar),
  'kill (taskkill) com windowsHide: true — sem tela preta ao encerrar',
);
assert(
  /detached:\s*true/.test(corpoEncerrar),
  'kill (taskkill) com detached: true — grupo de processos isolado',
);
assert(
  /stdio:\s*'ignore'/.test(corpoEncerrar),
  "kill (taskkill) com stdio: 'ignore' — nenhuma saída vazando para o terminal",
);

// 2) watchdog de reinício — nunca em loop infinito
assert(
  /MAX_REINICIOS\s*=\s*\d+/.test(startSrc),
  'watchdog tem teto de tentativas (MAX_REINICIOS) — sem loop infinito de spawns',
);
assert(
  /MAX_REINICIOS/.test(corpoDaFuncao(startSrc, 'iniciarWatchdog')),
  'watchdog USa o teto: para de reiniciar e encerra o launcher ao atingi-lo',
);
assert(
  /process\.exit\(1\)/.test(corpoDaFuncao(startSrc, 'iniciarWatchdog')),
  'watchdog encerra o launcher com exit(1) quando o teto estoura',
);
assert(
  /reinicios\s*=\s*0/.test(corpoDaFuncao(startSrc, 'iniciarWatchdog')),
  'watchdog zera o contador quando o backend volta a responder (queda pontual não punida)',
);

// 3) o caminho de reinício passa pelo startBackend (que spawna silenciosamente)
assert(
  /startBackend\(home\)/.test(corpoDaFuncao(startSrc, 'iniciarWatchdog')),
  'watchdog reergue o backend via startBackend (spawn com windowsHide + detached)',
);

// 4) REDIRECIONADOR DO VENV — a causa raiz medida da janela CMD no Windows.
//    `venv/Scripts/python.exe` do python-build-standalone re-executa o
//    interpretador real sem as flags do pai, e o Windows aloca um console
//    novo para esse neto. A correção sobe o python BASE + PYTHONPATH do venv.
assert(
  /function pythonBin\(/.test(startSrc),
  'start.js escolhe o binário python via pythonBin() (correção do redirector)',
);
assert(
  /'python', 'python\.exe'/.test(startSrc) || /runtime.*python.*exe/.test(startSrc),
  'pythonBin prefere o interpretador BASE (.runtime/python) no Windows',
);
assert(
  /PYTHONPATH/.test(startSrc),
  'pythonBin injeta PYTHONPATH do site-packages do venv (mesmas dependências)',
);
assert(
  /venvSitePackages/.test(startSrc),
  'pythonBin resolve o site-packages do venv (python base só enxerga via PYTHONPATH)',
);
assert(
  !/venvBin\(home\),\s*\n?\s*\[/m.test(startSrc.match(/const python = spawn\([\s\S]{0,300}/)?.[0] ?? ''),
  'o spawn do backend NÃO usa venvBin direto (usaria o redirector que abre janela)',
);

// ------------------------------------------------ varredura Python (backend)

const PROC_HELPER = join(root, 'backend', 'core', 'proc.py');
assert(existsSync(PROC_HELPER), 'backend/core/proc.py — helper silencioso existe (ponto único de subprocesso)');
if (existsSync(PROC_HELPER)) {
  const procSrc = readFileSync(PROC_HELPER, 'utf8');
  assert(/CREATE_NO_WINDOW\s*=\s*0x08000000/.test(procSrc), 'CREATE_NO_WINDOW = 0x08000000 definido no helper');
  assert(/def run_silent_process/.test(procSrc), 'run_silent_process disponível no helper');
  assert(/creationflags/.test(procSrc), 'helper aplica creationflags no Windows');
}

// Lista recursiva dos .py do backend (sem __pycache__).
function listarPy(diretorio, acumulador = []) {
  for (const entrada of readdirSync(diretorio, { withFileTypes: true })) {
    if (entrada.name === '__pycache__') continue;
    const caminho = join(diretorio, entrada.name);
    if (entrada.isDirectory()) listarPy(caminho, acumulador);
    else if (entrada.name.endsWith('.py')) acumulador.push(caminho);
  }
  return acumulador;
}

const PADROES_PROIBIDOS = [
  [/subprocess\.run\(/, 'subprocess.run('],
  [/subprocess\.Popen\(/, 'subprocess.Popen('],
  [/subprocess\.call\(/, 'subprocess.call('],
  [/subprocess\.check_output\(/, 'subprocess.check_output('],
  [/subprocess\.check_call\(/, 'subprocess.check_call('],
  [/os\.system\(/, 'os.system('],
  [/os\.popen\(/, 'os.popen('],
];

const backendDir = join(root, 'backend');
let arquivosPy = 0;
let diretasProibidas = 0;
if (existsSync(backendDir)) {
  for (const arquivo of listarPy(backendDir)) {
    if (arquivo.endsWith(join('core', 'proc.py'))) continue; // helper autorizado
    arquivosPy += 1;
    const conteudo = readFileSync(arquivo, 'utf8');
    const relativo = arquivo.slice(root.length + 1);
    for (const [regex, rotulo] of PADROES_PROIBIDOS) {
      if (regex.test(conteudo)) {
        diretasProibidas += 1;
        assert(false, `${relativo} — uso direto de ${rotulo} sem CREATE_NO_WINDOW (use backend.core.proc)`);
      }
    }
  }
}
assert(arquivosPy > 0, `backend/ — ${arquivosPy} arquivos .py varridos`);
assert(
  diretasProibidas === 0,
  'nenhuma chamada direta a subprocess/os.system no backend (todas via helper silencioso)',
);

// -------------------------------------------------------------- veredicto

if (falhas.length === 0) {
  console.log('Isolamento de processos: todas as verificações passaram.');
  process.exit(0);
}
console.error(`Isolamento de processos: ${falhas.length} verificação(ões) falharam.`);
process.exit(1);

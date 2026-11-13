import { NavLink, useNavigate } from 'react-router-dom';
import { PandaLogo } from './PandaLogo';
import { useAuth } from '../lib/auth';

// Lei de Hick: no máximo 7 itens de navegação, consistentes (Lei de Jakob).
const itens = [
  { to: '/', label: 'Dashboard', icon: '📊' },
  { to: '/blogs', label: 'Blogs', icon: '📰' },
  { to: '/noticias', label: 'Notícias', icon: '📝' },
  { to: '/imagens', label: 'Imagens', icon: '🖼️' },
  { to: '/automacao', label: 'Automação', icon: '⏱️' },
  { to: '/configuracoes', label: 'Configurações', icon: '⚙️' },
  { to: '/logs', label: 'Logs', icon: '📜' },
];

// Ícone de logout inline (mesmo desenho do LogOut do lucide) — evita uma
// dependência nova só para um ícone, já que a navegação usa emoji.
function LogOutIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

export function Sidebar() {
  const navegar = useNavigate();
  const sair = useAuth((s) => s.sair);

  function handleLogout() {
    // sair() limpa o token do localStorage e o estado; o AuthGuard passaria a
    // redireccionar sozinho, mas a navegação explícita é imediata e não
    // depende de um re-render intermédio.
    sair();
    navegar('/login', { replace: true });
  }

  return (
    <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-slate-200 bg-white md:flex dark:border-slate-800 dark:bg-card">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <PandaLogo />
        <div>
          <div className="flex items-center gap-2">
            <div className="text-lg font-extrabold leading-none">PandaNews</div>
            {/* Versão dinâmica (injetada do package.json da raiz via vite.config) */}
            <span className="rounded border border-slate-300 px-1.5 py-0.5 font-mono text-[10px] text-slate-400 dark:border-slate-600">
              v{__APP_VERSION__}
            </span>
          </div>
          <div className="text-[11px] text-slate-500">blogs de notícias com IA</div>
        </div>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-2">
        {itens.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-panda/15 text-panda-dark dark:text-panda'
                  : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800 dark:text-slate-400 dark:hover:bg-slate-800/60 dark:hover:text-slate-200'
              }`
            }
          >
            <span>{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Rodapé fixo: info + Sair. `mt-auto` cola no fundo da coluna flex. */}
      <div className="mt-auto border-t border-slate-200 px-3 py-3 dark:border-slate-800">
        <div className="px-2 pb-2 text-[11px] text-slate-400 dark:text-slate-600">100% local · SQLite</div>
        <button
          onClick={handleLogout}
          title="Encerrar a sessão e voltar ao login"
          className="flex w-full items-center gap-3 rounded-lg px-3 py-3 text-sm font-medium text-slate-500 transition-colors hover:bg-red-50 hover:text-red-600 dark:text-slate-400 dark:hover:bg-red-500/10 dark:hover:text-red-400"
        >
          <LogOutIcon />
          Sair
        </button>
      </div>
    </aside>
  );
}
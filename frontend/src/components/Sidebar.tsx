import { NavLink } from 'react-router-dom';
import { PandaLogo } from './PandaLogo';

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

export function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-200 bg-white md:flex dark:border-slate-800 dark:bg-card">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <PandaLogo />
        <div>
          <div className="text-lg font-extrabold leading-none">PandaNews</div>
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
      <div className="px-5 py-4 text-[11px] text-slate-400 dark:text-slate-600">100% local · SQLite · v0.4.00</div>
    </aside>
  );
}

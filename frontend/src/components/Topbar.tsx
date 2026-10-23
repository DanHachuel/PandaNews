import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../lib/api';
import { useUi } from '../lib/store';
import type { Blog } from '../lib/types';
import { PandaLogo } from './PandaLogo';

export function Topbar() {
  const { theme, toggleTheme, blogAtivo, setBlogAtivo } = useUi();
  const { data: blogs } = useQuery({
    queryKey: ['blogs'],
    queryFn: () => apiGet<Blog[]>('/blogs'),
  });

  return (
    <header className="flex h-16 items-center justify-between gap-4 border-b border-slate-200 bg-white px-5 dark:border-slate-800 dark:bg-card">
      <div className="flex items-center gap-3">
        <div className="md:hidden">
          <PandaLogo size={30} />
        </div>
        <span className="hidden text-sm text-slate-500 sm:inline">Blog ativo:</span>
        <select
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-panda dark:border-slate-700 dark:bg-night dark:text-slate-200"
          value={blogAtivo ?? ''}
          onChange={(e) => setBlogAtivo(e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">Todos os blogs</option>
          {(blogs ?? []).map((b) => (
            <option key={b.id} value={b.id}>
              {b.nome}
            </option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={toggleTheme}
          title="Alternar tema claro/escuro"
          className="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-300 text-lg hover:border-slate-400 dark:border-slate-700 dark:hover:border-slate-500"
        >
          {theme === 'dark' ? '☀️' : '🌙'}
        </button>
        <div
          title="DanHachuel"
          className="flex h-10 w-10 items-center justify-center rounded-full bg-panda/15 text-sm font-bold text-panda-dark dark:text-panda"
        >
          DH
        </div>
      </div>
    </header>
  );
}

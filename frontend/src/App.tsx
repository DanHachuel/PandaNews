import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { Topbar } from './components/Topbar';
import { Dashboard } from './pages/Dashboard';
import { Blogs } from './pages/Blogs';
import { Noticias } from './pages/Noticias';
import { Imagens } from './pages/Imagens';
import { Automacao } from './pages/Automacao';
import { Configuracoes } from './pages/Configuracoes';
import { Logs } from './pages/Logs';
import { Login } from './pages/Login';
import { useAuth } from './lib/auth';

// Lei de Jakob: breadcrumbs em telas internas (padrão universal de navegação).
const ROTULOS: Record<string, string> = {
  blogs: 'Blogs',
  noticias: 'Notícias',
  imagens: 'Imagens',
  automacao: 'Automação',
  configuracoes: 'Configurações',
  logs: 'Logs',
};

function Breadcrumbs() {
  const { pathname } = useLocation();
  const [primeiro] = pathname.split('/').filter(Boolean);
  if (!primeiro) return null; // raiz (Dashboard) não precisa de trilha
  const rotulo = ROTULOS[primeiro] ?? primeiro;
  return (
    <nav className="mb-4 text-sm text-slate-500" aria-label="Breadcrumb">
      <Link to="/" className="hover:underline">
        Dashboard
      </Link>
      <span className="mx-2">/</span>
      <span className="font-semibold text-slate-700 dark:text-slate-300">{rotulo}</span>
    </nav>
  );
}

// AuthGuard aplicado no layout, não rota a rota: uma página nova nunca escapa
// da exigência de sessão. Sem token, tudo volta ao login.
function Painel() {
  const token = useAuth((s) => s.token);
  if (!token) return <Navigate to="/login" replace />;

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="mx-auto w-full max-w-6xl flex-1 p-6">
          <Breadcrumbs />
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/blogs" element={<Blogs />} />
            <Route path="/noticias" element={<Noticias />} />
            <Route path="/imagens" element={<Imagens />} />
            <Route path="/automacao" element={<Automacao />} />
            <Route path="/configuracoes" element={<Configuracoes />} />
            <Route path="/logs" element={<Logs />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<Painel />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
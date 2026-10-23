import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { Topbar } from './components/Topbar';
import { Dashboard } from './pages/Dashboard';
import { Blogs } from './pages/Blogs';
import { Noticias } from './pages/Noticias';
import { Imagens } from './pages/Imagens';
import { Automacao } from './pages/Automacao';
import { Configuracoes } from './pages/Configuracoes';
import { Logs } from './pages/Logs';

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="flex min-h-screen">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <Topbar />
            <main className="mx-auto w-full max-w-6xl flex-1 p-6">
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
      </BrowserRouter>
    </QueryClientProvider>
  );
}

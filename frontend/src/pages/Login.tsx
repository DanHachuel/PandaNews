import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PandaLogo } from '../components/PandaLogo';
import { Button, Field, inputClass } from '../components/ui';
import { API_BASE } from '../lib/api';
import { useAuth } from '../lib/auth';

/** Login local do painel — layout centralizado, cartão único (Lei de Hick). */
export function Login() {
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [erro, setErro] = useState('');
  const [enviando, setEnviando] = useState(false);
  const entrar = useAuth((s) => s.entrar);
  const navegar = useNavigate();

  async function submeter(e: React.FormEvent) {
    e.preventDefault();
    setErro('');
    setEnviando(true);
    try {
      const resp = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), senha }),
      });
      const dados = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        setErro(dados.detail || `Erro HTTP ${resp.status}`);
        return;
      }
      entrar(dados.token, dados.email ?? email.trim());
      navegar('/', { replace: true });
    } catch (exc) {
      setErro(`Não foi possível conectar: ${(exc as Error).message}`);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6">
      <div className="w-full max-w-sm rounded-2xl border border-slate-800 bg-slate-900 p-8 shadow-xl">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <PandaLogo size={56} />
          <h1 className="text-2xl font-bold text-slate-100">PandaNews</h1>
          <p className="text-sm text-slate-400">Entre com a sua conta local para acessar o painel.</p>
        </div>

        <form onSubmit={submeter} className="space-y-4">
          <Field label="E-mail">
            <input
              type="email"
              className={inputClass}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="voce@exemplo.com"
              autoComplete="username"
              required
              autoFocus
            />
          </Field>
          <Field label="Senha">
            <input
              type="password"
              className={inputClass}
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              placeholder="••••••"
              autoComplete="current-password"
              required
            />
          </Field>

          {erro && (
            <p className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-400" role="alert">
              {erro}
            </p>
          )}

          {/* Fitts: botão de acção principal com altura confortável */}
          <Button type="submit" disabled={enviando} className="h-12 w-full justify-center text-base">
            {enviando ? 'Entrando…' : 'Entrar'}
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-slate-500">
          Esqueceu a senha? Edite-a direto no banco em <code className="font-mono">~/.pandanews</code>.
        </p>
      </div>
    </div>
  );
}
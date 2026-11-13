import { tokenActual } from './auth';

const BASE = '/api/v1';

// Rota de login: não leva Authorization (é onde o token nasce).
const PUBLICAS = ['/auth/login', '/auth/status'];

async function handle<T>(res: Response): Promise<T> {
  if (res.status === 204) {
    return undefined as T;
  }
  if (!res.ok) {
    let detail = `Erro HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body && typeof body.detail === 'string') detail = body.detail;
    } catch {
      /* corpo não-JSON */
    }
    // 401 numa rota protegida = token ausente, inválido ou expirado:
    // limpa a sessão e manda de volta ao login (AuthGuard assume daí).
    if (res.status === 401) {
      const { useAuth } = await import('./auth');
      useAuth.getState().sair();
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        window.location.assign('/login');
      }
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

function headers(path: string): HeadersInit {
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  if (!PUBLICAS.includes(path)) {
    const token = tokenActual();
    if (token) h['Authorization'] = `Bearer ${token}`;
  }
  return h;
}

export function apiGet<T>(path: string): Promise<T> {
  return fetch(BASE + path, { headers: headers(path) }).then((r) => handle<T>(r));
}

export function apiSend<T>(
  path: string,
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  body?: unknown,
): Promise<T> {
  return fetch(BASE + path, {
    method,
    headers: headers(path),
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then((r) => handle<T>(r));
}

export { BASE as API_BASE };
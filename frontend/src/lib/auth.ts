import { create } from 'zustand';

const TOKEN_KEY = 'pandanews-token';
const EMAIL_KEY = 'pandanews-email';

interface AuthState {
  token: string | null;
  email: string | null;
  entrar: (token: string, email: string) => void;
  sair: () => void;
}

function lerToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function lerEmail(): string | null {
  try {
    return localStorage.getItem(EMAIL_KEY);
  } catch {
    return null;
  }
}

export const useAuth = create<AuthState>((set) => ({
  token: lerToken(),
  email: lerEmail(),
  entrar: (token, email) => {
    try {
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(EMAIL_KEY, email);
    } catch {
      /* localStorage indisponível: a sessão fica só em memória */
    }
    set({ token, email });
  },
  sair: () => {
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(EMAIL_KEY);
    } catch {
      /* nada a fazer */
    }
    set({ token: null, email: null });
  },
}));

/** Token actual — usado pelo cliente API fora dos componentes React. */
export function tokenActual(): string | null {
  return useAuth.getState().token;
}
import { create } from 'zustand';

type Theme = 'dark' | 'light';

interface UiState {
  theme: Theme;
  toggleTheme: () => void;
  blogAtivo: number | null;
  setBlogAtivo: (id: number | null) => void;
}

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark');
}

function initialTheme(): Theme {
  const saved = localStorage.getItem('pandanews-theme');
  return saved === 'light' ? 'light' : 'dark';
}

export const useUi = create<UiState>((set, get) => ({
  theme: initialTheme(),
  toggleTheme: () => {
    const next: Theme = get().theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('pandanews-theme', next);
    applyTheme(next);
    set({ theme: next });
  },
  blogAtivo: null,
  setBlogAtivo: (id) => set({ blogAtivo: id }),
}));

applyTheme(useUi.getState().theme);

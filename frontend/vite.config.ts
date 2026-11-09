import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
// Importa o package.json da raiz do projeto (versão canônica do release)
import rootPackage from '../package.json';

export default defineConfig({
  plugins: [react()],
  // Injeta a versão como constante global no bundle — badge do sidebar
  // sempre alinhada ao package.json, sem edição manual do React.
  define: {
    __APP_VERSION__: JSON.stringify(rootPackage.version),
  },
  build: { outDir: 'dist' },
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
});

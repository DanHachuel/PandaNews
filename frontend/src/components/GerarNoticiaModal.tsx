import { useEffect, useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiSend } from '../lib/api';
import type { Blog, Noticia } from '../lib/types';
import { Badge, Button, selectClass } from './ui';

const ETAPAS = ['Coletando feeds RSS', 'Redigindo com IA', 'Gerando imagem', 'Salvando'];

// Gradiente de Meta: progresso visível da geração (coletando → redigindo → imagem → salvo).
export function GerarNoticiaModal({
  open,
  blogs,
  blogInicial,
  onClose,
}: {
  open: boolean;
  blogs: Blog[];
  blogInicial?: number | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [blogId, setBlogId] = useState<number | null>(blogInicial ?? blogs[0]?.id ?? null);
  const [etapaAtiva, setEtapaAtiva] = useState(0);
  const [noticia, setNoticia] = useState<Noticia | null>(null);
  const [erro, setErro] = useState('');
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (blogInicial != null) setBlogId(blogInicial);
  }, [blogInicial]);

  const gerar = useMutation({
    mutationFn: (id: number) => apiSend<Noticia>('/noticias/gerar', 'POST', { blog_id: id }),
    onSuccess: (data) => {
      setEtapaAtiva(ETAPAS.length);
      setNoticia(data);
      queryClient.invalidateQueries({ queryKey: ['noticias'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['logs'] });
    },
    onError: (e: Error) => {
      setEtapaAtiva(0);
      setErro(e.message);
    },
  });

  useEffect(() => {
    if (gerar.isPending) {
      timer.current = setInterval(() => {
        setEtapaAtiva((f) => (f < 2 ? f + 1 : f));
      }, 4500);
    } else if (timer.current) {
      clearInterval(timer.current);
      timer.current = null;
    }
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [gerar.isPending]);

  if (!open) return null;

  function iniciar() {
    if (!blogId) return;
    setErro('');
    setNoticia(null);
    setEtapaAtiva(0);
    gerar.mutate(blogId);
  }

  const concluido = noticia !== null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-xl border border-slate-300 bg-white p-6 dark:border-slate-700 dark:bg-card"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-4 text-lg font-bold">Gerar notícia agora</h3>

        {blogs.length === 0 ? (
          <p className="mb-6 text-sm text-slate-500">
            Crie um blog primeiro (com fontes RSS) para gerar notícias.
          </p>
        ) : (
          !concluido &&
          !gerar.isPending && (
            <label className="mb-6 block">
              <span className="mb-1.5 block text-sm font-medium text-slate-500 dark:text-slate-400">Blog</span>
              <select
                className={selectClass}
                value={blogId ?? ''}
                onChange={(e) => setBlogId(e.target.value ? Number(e.target.value) : null)}
              >
                {blogs.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.nome} ({b.tema})
                  </option>
                ))}
              </select>
            </label>
          )
        )}

        {(gerar.isPending || concluido) && (
          <ul className="mb-6 space-y-2">
            {ETAPAS.map((etapa, i) => {
              const feito = concluido || i < etapaAtiva;
              const atual = !concluido && i === etapaAtiva;
              return (
                <li key={etapa} className="flex items-center gap-3 text-sm">
                  <span
                    className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                      feito
                        ? 'bg-panda text-slate-900'
                        : atual
                          ? 'bg-panda/30 text-panda'
                          : 'bg-slate-200 text-slate-500 dark:bg-slate-800'
                    }`}
                  >
                    {feito ? '✓' : atual ? '•' : ''}
                  </span>
                  <span className={feito ? 'text-slate-400 line-through' : atual ? 'font-semibold' : 'text-slate-500'}>
                    {etapa}
                  </span>
                </li>
              );
            })}
          </ul>
        )}

        {concluido && noticia && (
          <div className="mb-6 rounded-lg border border-panda/40 bg-panda/10 p-4">
            <div className="mb-1 flex items-center gap-2">
              <Badge tone="green">rascunho salvo</Badge>
              {noticia.llm_provider && <Badge tone="blue">via {noticia.llm_provider}</Badge>}
            </div>
            <p className="font-semibold">{noticia.titulo}</p>
            {!noticia.imagem_url && <Badge tone="amber">sem imagem</Badge>}
          </div>
        )}

        {erro && (
          <p className="mb-4 rounded-lg border border-amber-400/40 bg-amber-500/10 p-3 text-sm text-amber-500">
            {erro}
          </p>
        )}

        <div className="flex justify-end gap-3">
          {concluido ? (
            <Button onClick={onClose}>Fechar</Button>
          ) : (
            <>
              <Button variant="secondary" onClick={onClose}>
                Cancelar
              </Button>
              <Button onClick={iniciar} disabled={gerar.isPending || !blogId}>
                {gerar.isPending ? 'Gerando…' : 'Gerar notícia'}
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

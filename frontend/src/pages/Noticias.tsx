import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiSend } from '../lib/api';
import type { Blog, Noticia } from '../lib/types';
import { useUi } from '../lib/store';
import { Badge, Button, Card, Empty, Field, StatusBadge, inputClass, selectClass } from '../components/ui';
import { GerarNoticiaModal } from '../components/GerarNoticiaModal';

export function Noticias() {
  const queryClient = useQueryClient();
  const { blogAtivo } = useUi();
  const [status, setStatus] = useState('');
  const [gerarAberto, setGerarAberto] = useState(false);
  const [editando, setEditando] = useState<Noticia | null>(null);
  const [form, setForm] = useState({ titulo: '', resumo: '', corpo: '' });
  const [erro, setErro] = useState('');

  const { data: blogs } = useQuery({ queryKey: ['blogs'], queryFn: () => apiGet<Blog[]>('/blogs') });
  const { data: noticias, isLoading } = useQuery({
    queryKey: ['noticias', blogAtivo, status],
    queryFn: () => {
      const params = new URLSearchParams();
      if (blogAtivo) params.set('blog_id', String(blogAtivo));
      if (status) params.set('status', status);
      return apiGet<Noticia[]>(`/noticias${params.toString() ? `?${params}` : ''}`);
    },
  });

  const nomeBlog = (id: number) => blogs?.find((b) => b.id === id)?.nome ?? `Blog #${id}`;

  const patch = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) =>
      apiSend<Noticia>(`/noticias/${id}`, 'PATCH', body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['noticias'] }),
  });

  const salvarEdicao = useMutation({
    mutationFn: (n: Noticia) =>
      apiSend<Noticia>(`/noticias/${n.id}`, 'PATCH', {
        titulo: form.titulo,
        resumo: form.resumo,
        corpo: form.corpo,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['noticias'] });
      setEditando(null);
    },
    onError: (e: Error) => setErro(e.message),
  });

  const regenerar = useMutation({
    mutationFn: (id: number) => apiSend<Noticia>(`/noticias/${id}/regenerar`, 'POST'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['noticias'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold">Notícias</h1>
        <div className="flex items-center gap-3">
          <select className={`${selectClass} w-44`} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Todos os status</option>
            <option value="rascunho">Rascunho (pendente)</option>
            <option value="aprovado">Aprovado</option>
            <option value="rejeitado">Rejeitado</option>
            <option value="publicado">Publicado</option>
          </select>
          <Button onClick={() => setGerarAberto(true)} disabled={(blogs ?? []).length === 0} title={(blogs ?? []).length === 0 ? 'Crie um blog primeiro' : undefined}>
            ⚡ Gerar notícia
          </Button>
        </div>
      </div>

      <GerarNoticiaModal
        open={gerarAberto}
        blogs={blogs ?? []}
        blogInicial={blogAtivo}
        onClose={() => setGerarAberto(false)}
      />

      {isLoading ? (
        <p className="text-slate-500">Carregando…</p>
      ) : !noticias || noticias.length === 0 ? (
        <Empty
          icon="📝"
          title="Nenhuma notícia ainda"
          message="O pipeline de geração (coleta RSS → redação via LLM → imagem) chega na próxima versão; notícias geradas aparecem aqui para revisão."
        />
      ) : (
        <div className="space-y-4">
          {noticias.map((n) => (
            <Card key={n.id}>
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <StatusBadge status={n.status} />
                {n.llm_provider && <Badge tone="blue">via {n.llm_provider}</Badge>}
                <span className="text-xs text-slate-500">
                  {nomeBlog(n.blog_id)} · {new Date(n.created_at).toLocaleString('pt-BR')}
                </span>
              </div>
              <h3 className="text-lg font-bold">{n.titulo || '(sem título)'}</h3>
              {n.resumo && <p className="mt-1 text-sm text-slate-500">{n.resumo}</p>}
              {n.imagem_url ? (
                <img src={n.imagem_url} alt="" className="mt-3 max-h-48 rounded-lg" />
              ) : (
                n.status === 'rascunho' && <Badge tone="amber">sem imagem</Badge>
              )}
              <div className="mt-4 flex flex-wrap justify-end gap-2">
                {n.fonte_titulo && (
                  <Button variant="secondary" onClick={() => regenerar.mutate(n.id)} disabled={regenerar.isPending} title="Re-escrever a partir da fonte original">
                    ↻ Regenerar
                  </Button>
                )}
                <Button
                  variant="secondary"
                  onClick={() => {
                    setErro('');
                    setForm({ titulo: n.titulo, resumo: n.resumo, corpo: n.corpo });
                    setEditando(n);
                  }}
                >
                  Editar
                </Button>
                <Button variant="danger" onClick={() => patch.mutate({ id: n.id, body: { status: 'rejeitado' } })}>
                  Rejeitar
                </Button>
                <Button onClick={() => patch.mutate({ id: n.id, body: { status: 'aprovado' } })}>Aprovar</Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {editando && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={() => setEditando(null)}>
          <div
            className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-slate-300 bg-white p-6 dark:border-slate-700 dark:bg-card"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-4 text-lg font-bold">Editar notícia manualmente</h3>
            <div className="space-y-4">
              <Field label="Título">
                <input className={inputClass} value={form.titulo} onChange={(e) => setForm({ ...form, titulo: e.target.value })} />
              </Field>
              <Field label="Resumo">
                <textarea className={`${inputClass} h-auto py-2.5`} rows={2} value={form.resumo} onChange={(e) => setForm({ ...form, resumo: e.target.value })} />
              </Field>
              <Field label="Corpo">
                <textarea className={`${inputClass} h-auto py-2.5`} rows={10} value={form.corpo} onChange={(e) => setForm({ ...form, corpo: e.target.value })} />
              </Field>
            </div>
            {erro && <p className="mt-3 text-sm text-red-400">{erro}</p>}
            <div className="mt-6 flex justify-end gap-3">
              <Button variant="secondary" onClick={() => setEditando(null)}>Cancelar</Button>
              <Button onClick={() => salvarEdicao.mutate(editando)} disabled={salvarEdicao.isPending}>
                Salvar
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiSend } from '../lib/api';
import type { Blog, Configuracoes } from '../lib/types';
import { Badge, Card, Empty } from '../components/ui';

export function Automacao() {
  const queryClient = useQueryClient();

  const { data: config } = useQuery({
    queryKey: ['configuracoes'],
    queryFn: () => apiGet<Configuracoes>('/configuracoes'),
  });
  const { data: blogs } = useQuery({ queryKey: ['blogs'], queryFn: () => apiGet<Blog[]>('/blogs') });

  const salvarConfig = useMutation({
    mutationFn: (patch: Record<string, unknown>) => apiSend<Configuracoes>('/configuracoes', 'PUT', patch),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['configuracoes'] }),
  });

  const patchBlog = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      apiSend<Blog>(`/blogs/${id}`, 'PATCH', { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['blogs'] }),
  });

  const ativo = config?.scheduler_ativo ?? true;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-extrabold">Automação</h1>

      <Card>
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="font-bold">Agendador global</h2>
            <p className="mt-1 text-sm text-slate-500">
              Liga/desliga o scheduler do PandaNews. A execução automática por blog (frequência configurável) entra em
              operação na Fase 5; o estado já é persistido.
            </p>
          </div>
          <button
            onClick={() => salvarConfig.mutate({ scheduler_ativo: !ativo })}
            className={`relative h-10 w-20 shrink-0 rounded-full transition-colors ${
              ativo ? 'bg-panda' : 'bg-slate-300 dark:bg-slate-700'
            }`}
            title={ativo ? 'Clique para pausar' : 'Clique para ativar'}
          >
            <span
              className={`absolute top-1 h-8 w-8 rounded-full bg-white shadow transition-all ${
                ativo ? 'left-11' : 'left-1'
              }`}
            />
          </button>
        </div>
        <div className="mt-4 flex items-center gap-2">
          <Badge tone={ativo ? 'green' : 'neutral'}>scheduler {ativo ? 'ativo' : 'pausado'}</Badge>
          <Badge>intervalo padrão: {config?.intervalo_padrao_horas ?? 6}h</Badge>
        </div>
      </Card>

      <h2 className="pt-2 font-bold">Por blog</h2>
      {!blogs || blogs.length === 0 ? (
        <Empty icon="⏱️" title="Nenhum blog" message="Crie um blog para configurar sua frequência de geração." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {blogs.map((b) => (
            <Card key={b.id}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-semibold">{b.nome}</div>
                  <div className="text-xs text-slate-500">
                    a cada {b.frequencia_horas}h · {b.tema} · {b.regiao}
                  </div>
                </div>
                <button
                  onClick={() => patchBlog.mutate({ id: b.id, status: b.status === 'ativo' ? 'pausado' : 'ativo' })}
                  className={`relative h-8 w-16 shrink-0 rounded-full transition-colors ${
                    b.status === 'ativo' ? 'bg-panda' : 'bg-slate-300 dark:bg-slate-700'
                  }`}
                  title={b.status === 'ativo' ? 'Clique para pausar' : 'Clique para ativar'}
                >
                  <span
                    className={`absolute top-1 h-6 w-6 rounded-full bg-white shadow transition-all ${
                      b.status === 'ativo' ? 'left-9' : 'left-1'
                    }`}
                  />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

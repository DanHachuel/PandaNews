import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiSend } from '../lib/api';
import type { Blog } from '../lib/types';
import { Button, Card, ConfirmModal, Empty, Field, StatusBadge, inputClass, selectClass } from '../components/ui';

const TEMAS_LABEL: Record<string, string> = {
  geral: 'Geral',
  esporte: 'Esporte',
  politica: 'Política',
  economia: 'Economia',
  tecnologia: 'Tecnologia',
};

const FORM_VAZIO = {
  nome: '',
  tema: 'geral',
  regiao: 'Brasil',
  fontes: '',
  estilo_editorial: '',
  frequencia_horas: 6,
};

export function Blogs() {
  const queryClient = useQueryClient();
  const { data: blogs, isLoading } = useQuery({ queryKey: ['blogs'], queryFn: () => apiGet<Blog[]>('/blogs') });

  const [wizardAberto, setWizardAberto] = useState(false);
  const [editando, setEditando] = useState<Blog | null>(null);
  const [step, setStep] = useState(1);
  const [form, setForm] = useState(FORM_VAZIO);
  const [excluir, setExcluir] = useState<Blog | null>(null);
  const [erro, setErro] = useState('');

  const salvar = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      editando
        ? apiSend<Blog>(`/blogs/${editando.id}`, 'PATCH', payload)
        : apiSend<Blog>('/blogs', 'POST', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['blogs'] });
      fecharWizard();
    },
    onError: (e: Error) => setErro(e.message),
  });

  const patchStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => apiSend(`/blogs/${id}`, 'PATCH', { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['blogs'] }),
  });

  const apagar = useMutation({
    mutationFn: (id: number) => apiSend(`/blogs/${id}`, 'DELETE'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['blogs'] });
      setExcluir(null);
    },
  });

  function abrirNovo() {
    setEditando(null);
    setForm(FORM_VAZIO);
    setStep(1);
    setErro('');
    setWizardAberto(true);
  }

  function abrirEdicao(blog: Blog) {
    setEditando(blog);
    setForm({
      nome: blog.nome,
      tema: blog.tema,
      regiao: blog.regiao,
      fontes: blog.fontes_rss.join('\n'),
      estilo_editorial: blog.estilo_editorial,
      frequencia_horas: blog.frequencia_horas,
    });
    setStep(1);
    setErro('');
    setWizardAberto(true);
  }

  function fecharWizard() {
    setWizardAberto(false);
    setEditando(null);
    setStep(1);
  }

  function submeter() {
    const payload = {
      nome: form.nome.trim(),
      tema: form.tema,
      regiao: form.regiao.trim() || 'Brasil',
      fontes_rss: form.fontes.split('\n').map((l) => l.trim()).filter(Boolean),
      estilo_editorial: form.estilo_editorial,
      frequencia_horas: Number(form.frequencia_horas) || 6,
    };
    if (!payload.nome) {
      setErro('Dê um nome ao blog.');
      return;
    }
    salvar.mutate(payload);
  }

  const podeAvancar = form.nome.trim().length > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold">Blogs</h1>
        {/* Lei de von Restorff: CTA principal em verde vibrante */}
        <Button onClick={abrirNovo}>+ Novo blog</Button>
      </div>

      {isLoading ? (
        <p className="text-slate-500">Carregando…</p>
      ) : !blogs || blogs.length === 0 ? (
        <Empty
          icon="📰"
          title="Nenhum blog ainda"
          message="Crie seu primeiro blog: escolha tema, região e fontes RSS — em menos de 2 minutos."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {blogs.map((b) => (
            <Card key={b.id}>
              <div className="mb-3 flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-bold">{b.nome}</h3>
                  <div className="mt-0.5 text-xs text-slate-500">
                    {TEMAS_LABEL[b.tema] ?? b.tema} · {b.regiao}
                  </div>
                </div>
                <StatusBadge status={b.status} />
              </div>
              <div className="space-y-1 text-sm text-slate-500">
                <div>📰 {b.fontes_rss.length} fonte(s) RSS</div>
                <div>⏱️ a cada {b.frequencia_horas}h</div>
              </div>
              <div className="mt-4 flex items-center justify-end gap-2">
                <Button variant="secondary" onClick={() => patchStatus.mutate({ id: b.id, status: b.status === 'ativo' ? 'pausado' : 'ativo' })}>
                  {b.status === 'ativo' ? 'Pausar' : 'Ativar'}
                </Button>
                <Button variant="secondary" onClick={() => abrirEdicao(b)}>
                  Editar
                </Button>
                {/* Lei de Jakob: ação destrutiva em vermelho, isolada à direita */}
                <Button variant="danger" onClick={() => setExcluir(b)}>
                  Excluir
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {wizardAberto && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={fecharWizard}>
          <div
            className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl border border-slate-300 bg-white p-6 dark:border-slate-700 dark:bg-card"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-1 text-lg font-bold">{editando ? `Editar: ${editando.nome}` : 'Novo blog'}</h3>
            {/* Gradiente de Meta: etapas visíveis */}
            {!editando && (
              <div className="mb-5 flex gap-2 text-xs font-semibold">
                {['Identidade', 'Fontes RSS', 'Estilo'].map((label, i) => (
                  <div
                    key={label}
                    className={`rounded-full px-3 py-1 ${
                      step === i + 1 ? 'bg-panda text-slate-900' : step > i + 1 ? 'bg-panda/30 text-panda' : 'bg-slate-200 text-slate-500 dark:bg-slate-800'
                    }`}
                  >
                    {i + 1}. {label}
                  </div>
                ))}
              </div>
            )}

            {editando || step === 1 ? (
              <div className="space-y-4">
                <Field label="Nome do blog">
                  <input className={inputClass} value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} placeholder="Ex.: Notícias do Acre" />
                </Field>
                <div className="grid grid-cols-2 gap-4">
                  <Field label="Tema">
                    <select className={selectClass} value={form.tema} onChange={(e) => setForm({ ...form, tema: e.target.value })}>
                      {Object.entries(TEMAS_LABEL).map(([k, v]) => (
                        <option key={k} value={k}>{v}</option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Região">
                    <input className={inputClass} value={form.regiao} onChange={(e) => setForm({ ...form, regiao: e.target.value })} placeholder="Ex.: São Paulo, Brasil, Espanha" />
                  </Field>
                </div>
              </div>
            ) : null}

            {editando || step === 2 ? (
              <div className="mt-4">
                <Field label="Fontes RSS" hint="Uma URL por linha">
                  <textarea
                    className={`${inputClass} h-auto py-2.5`}
                    rows={4}
                    value={form.fontes}
                    onChange={(e) => setForm({ ...form, fontes: e.target.value })}
                    placeholder={'https://exemplo.com/feed\nhttps://outro.com/rss'}
                  />
                </Field>
              </div>
            ) : null}

            {editando || step === 3 ? (
              <div className="mt-4 space-y-4">
                <Field label="Estilo editorial" hint="Prompt base para o LLM (tom, extensão, público)">
                  <textarea
                    className={`${inputClass} h-auto py-2.5`}
                    rows={3}
                    value={form.estilo_editorial}
                    onChange={(e) => setForm({ ...form, estilo_editorial: e.target.value })}
                    placeholder="Ex.: notícias diretas em português do Brasil, tom jornalístico, 3 parágrafos"
                  />
                </Field>
                <Field label="Frequência de geração (horas)">
                  <input
                    type="number"
                    min={1}
                    max={168}
                    className={inputClass}
                    value={form.frequencia_horas}
                    onChange={(e) => setForm({ ...form, frequencia_horas: Number(e.target.value) })}
                  />
                </Field>
              </div>
            ) : null}

            {erro && <p className="mt-4 text-sm text-red-400">{erro}</p>}

            <div className="mt-6 flex justify-between gap-3">
              {!editando && step > 1 ? (
                <Button variant="secondary" onClick={() => setStep(step - 1)}>← Voltar</Button>
              ) : (
                <span />
              )}
              {!editando && step < 3 ? (
                <Button onClick={() => setStep(step + 1)} disabled={!podeAvancar}>Avançar →</Button>
              ) : (
                <Button onClick={submeter} disabled={salvar.isPending}>
                  {editando ? 'Salvar alterações' : 'Criar blog'}
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      <ConfirmModal
        open={excluir !== null}
        title={`Excluir "${excluir?.nome}"?`}
        message="O blog e todas as suas notícias serão removidos. Esta ação não pode ser desfeita."
        onConfirm={() => excluir && apagar.mutate(excluir.id)}
        onCancel={() => setExcluir(null)}
      />
    </div>
  );
}

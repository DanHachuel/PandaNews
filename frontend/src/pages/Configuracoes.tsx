import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiSend } from '../lib/api';
import type { Configuracoes } from '../lib/types';
import { Badge, Button, Card, Expander, Field, inputClass } from '../components/ui';

type TestResult = { ok: boolean; detail?: string; latency_ms?: number; model?: string };

const NOME_PROVEDOR: Record<string, string> = { nvidia: 'NVIDIA NIM', google: 'Google Gemini' };

export function Configuracoes() {
  const queryClient = useQueryClient();
  const { data: config } = useQuery({
    queryKey: ['configuracoes'],
    queryFn: () => apiGet<Configuracoes>('/configuracoes'),
  });

  const [secrets, setSecrets] = useState({ nvidia_api_key: '', google_api_key: '', supabase_service_role_key: '' });
  const [form, setForm] = useState({
    nvidia_base_url: '',
    nvidia_model: '',
    google_base_url: '',
    google_model: '',
    llm_fallback_ordem: 'nvidia,google',
    supabase_url: '',
    intervalo_padrao_horas: 6,
    meta_diaria: 3,
  });
  const [testes, setTestes] = useState<Record<string, TestResult>>({});
  const [msg, setMsg] = useState('');
  const [schemaSql, setSchemaSql] = useState('');

  useEffect(() => {
    if (!config) return;
    setForm({
      nvidia_base_url: config.nvidia_base_url,
      nvidia_model: config.nvidia_model,
      google_base_url: config.google_base_url,
      google_model: config.google_model,
      llm_fallback_ordem: config.llm_fallback_ordem,
      supabase_url: config.supabase_url,
      intervalo_padrao_horas: config.intervalo_padrao_horas,
      meta_diaria: config.meta_diaria,
    });
  }, [config]);

  const salvar = useMutation({
    mutationFn: (payload: Record<string, unknown>) => apiSend<Configuracoes>('/configuracoes', 'PUT', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['configuracoes'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      setMsg('Configurações salvas com sucesso.');
      setSecrets({ nvidia_api_key: '', google_api_key: '', supabase_service_role_key: '' });
    },
    onError: (e: Error) => setMsg(`Falha ao salvar: ${e.message}`),
  });

  const testar = useMutation({
    mutationFn: (provider: string) => apiSend<TestResult>('/llm/test', 'POST', { provider }),
    onSuccess: (result, provider) => setTestes((t) => ({ ...t, [provider]: result })),
  });

  const testarSupabase = useMutation({
    mutationFn: () => apiSend<TestResult>('/configuracoes/testar-supabase', 'POST'),
  });

  const verSchema = useMutation({
    mutationFn: () => apiGet<{ sql: string }>('/configuracoes/schema-supabase'),
    onSuccess: (d) => setSchemaSql(d.sql),
  });

  const migrar = useMutation({
    mutationFn: () => apiSend<{ ok: boolean; migrados?: Record<string, number>; detail?: string }>('/configuracoes/migrar-supabase', 'POST'),
    onSuccess: () => setMsg(''),
  });

  function salvarTudo() {
    const payload: Record<string, unknown> = { ...form };
    if (secrets.nvidia_api_key.trim()) payload.nvidia_api_key = secrets.nvidia_api_key.trim();
    if (secrets.google_api_key.trim()) payload.google_api_key = secrets.google_api_key.trim();
    if (secrets.supabase_service_role_key.trim()) payload.supabase_service_role_key = secrets.supabase_service_role_key.trim();
    setMsg('');
    salvar.mutate(payload);
  }

  function mover(provider: string, dir: -1 | 1) {
    const ordem = form.llm_fallback_ordem.split(',').map((s) => s.trim());
    const i = ordem.indexOf(provider);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= ordem.length) return;
    [ordem[i], ordem[j]] = [ordem[j], ordem[i]];
    setForm({ ...form, llm_fallback_ordem: ordem.join(',') });
  }

  const placeholderSecret = (info: { configured: boolean; preview: string }) =>
    info.configured ? `${info.preview} — deixe vazio para manter` : 'Não configurado';

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold">Configurações</h1>
        {/* Lei de von Restorff: salvar em verde vibrante */}
        <Button onClick={salvarTudo} disabled={salvar.isPending || !config}>
          Salvar configurações
        </Button>
      </div>

      {msg && (
        <p className={`text-sm ${msg.startsWith('Falha') ? 'text-red-400' : 'text-panda'}`}>{msg}</p>
      )}

      {/* Lei de Hick/Miller: revelação progressiva em blocos de até 7 campos */}
      <div className="space-y-4">
        <Expander title="NVIDIA NIM (provedor primário)" defaultOpen>
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="API Key">
              <input
                type="password"
                className={inputClass}
                value={secrets.nvidia_api_key}
                onChange={(e) => setSecrets({ ...secrets, nvidia_api_key: e.target.value })}
                placeholder={config ? placeholderSecret(config.nvidia_api_key) : ''}
              />
            </Field>
            <Field label="Base URL">
              <input className={inputClass} value={form.nvidia_base_url} onChange={(e) => setForm({ ...form, nvidia_base_url: e.target.value })} />
            </Field>
            <Field label="Modelo">
              <input className={inputClass} value={form.nvidia_model} onChange={(e) => setForm({ ...form, nvidia_model: e.target.value })} />
            </Field>
            <div className="flex items-end gap-2">
              <Button variant="secondary" onClick={() => testar.mutate('nvidia')} disabled={testar.isPending}>
                Testar conexão
              </Button>
              {testes.nvidia && (
                <Badge tone={testes.nvidia.ok ? 'green' : 'red'}>
                  {testes.nvidia.ok ? `ok · ${testes.nvidia.latency_ms}ms` : 'falhou'}
                </Badge>
              )}
            </div>
          </div>
          {testes.nvidia && !testes.nvidia.ok && <p className="mt-3 text-xs text-red-400">{testes.nvidia.detail}</p>}
        </Expander>

        <Expander title="Google Gemini (provedor de fallback)">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="API Key">
              <input
                type="password"
                className={inputClass}
                value={secrets.google_api_key}
                onChange={(e) => setSecrets({ ...secrets, google_api_key: e.target.value })}
                placeholder={config ? placeholderSecret(config.google_api_key) : ''}
              />
            </Field>
            <Field label="Base URL">
              <input className={inputClass} value={form.google_base_url} onChange={(e) => setForm({ ...form, google_base_url: e.target.value })} />
            </Field>
            <Field label="Modelo">
              <input className={inputClass} value={form.google_model} onChange={(e) => setForm({ ...form, google_model: e.target.value })} />
            </Field>
            <div className="flex items-end gap-2">
              <Button variant="secondary" onClick={() => testar.mutate('google')} disabled={testar.isPending}>
                Testar conexão
              </Button>
              {testes.google && (
                <Badge tone={testes.google.ok ? 'green' : 'red'}>
                  {testes.google.ok ? `ok · ${testes.google.latency_ms}ms` : 'falhou'}
                </Badge>
              )}
            </div>
          </div>
          {testes.google && !testes.google.ok && <p className="mt-3 text-xs text-red-400">{testes.google.detail}</p>}
        </Expander>

        <Expander title="Ordem de fallback dos provedores">
          <ul className="space-y-2">
            {form.llm_fallback_ordem.split(',').map((p, i, arr) => (
              <li key={p} className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-2.5 dark:border-slate-700">
                <span className="font-semibold">
                  {i + 1}. {NOME_PROVEDOR[p.trim()] ?? p}
                </span>
                <span className="flex gap-2">
                  <Button variant="secondary" onClick={() => mover(p.trim(), -1)} disabled={i === 0} title="Subir na prioridade">↑</Button>
                  <Button variant="secondary" onClick={() => mover(p.trim(), 1)} disabled={i === arr.length - 1} title="Descer na prioridade">↓</Button>
                </span>
              </li>
            ))}
          </ul>
        </Expander>

        <Expander title="Banco de dados (SQLite local → Supabase opcional)">
          <div className="mb-4 space-y-3 rounded-lg border border-slate-200 p-4 dark:border-slate-700">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="green">Backend ativo: SQLite local</Badge>
              {config?.supabase_detectado ? (
                <Badge tone="blue">credenciais Supabase detectadas</Badge>
              ) : (
                <Badge>credenciais Supabase não configuradas</Badge>
              )}
            </div>
            <p className="text-xs text-slate-500">
              100% local por padrão. O Supabase é opcional: informe o projeto + <code>service_role_key</code>, teste a
              conexão, crie as tabelas com o schema SQL e migre seus dados quando quiser. O app continua funcionando
              localmente de forma independente.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" onClick={() => testarSupabase.mutate()} disabled={testarSupabase.isPending}>
                Testar conexão
              </Button>
              <Button variant="secondary" onClick={() => verSchema.mutate()} disabled={verSchema.isPending}>
                Ver schema SQL
              </Button>
              <Button
                onClick={() => migrar.mutate()}
                disabled={migrar.isPending || !config?.supabase_detectado}
                title={!config?.supabase_detectado ? 'Configure as credenciais do Supabase primeiro' : 'Copiar dados do SQLite para o Supabase'}
              >
                {migrar.isPending ? 'Migrando…' : 'Migrar dados do SQLite'}
              </Button>
            </div>
            {testarSupabase.data && (
              <p className={`text-xs ${testarSupabase.data.ok ? 'text-panda' : 'text-amber-500'}`}>
                {testarSupabase.data.detail}
                {testarSupabase.data.ok && ` (credencial em: ${(testarSupabase.data as { credencial_em?: string }).credencial_em})`}
              </p>
            )}
            {migrar.data?.ok && migrar.data.migrados && (
              <p className="text-xs text-panda">
                Migrado: {Object.entries(migrar.data.migrados).map(([t, n]) => `${t} (${n})`).join(' · ')}
              </p>
            )}
            {migrar.data && !migrar.data.ok && <p className="text-xs text-red-400">{migrar.data.detail}</p>}
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Supabase URL" hint="Detectada automaticamente quando SUPABASE_URL está no ambiente">
              <input className={inputClass} value={form.supabase_url} onChange={(e) => setForm({ ...form, supabase_url: e.target.value })} placeholder="https://xxxx.supabase.co" />
            </Field>
            <Field label="Service Role Key">
              <input
                type="password"
                className={inputClass}
                value={secrets.supabase_service_role_key}
                onChange={(e) => setSecrets({ ...secrets, supabase_service_role_key: e.target.value })}
                placeholder={config ? placeholderSecret(config.supabase_service_role_key) : ''}
              />
            </Field>
          </div>
        </Expander>

        <Expander title="Agendamento">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Intervalo padrão de geração (horas)" hint="Aplicado a novos blogs; cada blog pode ter seu próprio intervalo">
              <input
                type="number"
                min={1}
                max={168}
                className={`${inputClass} w-40`}
                value={form.intervalo_padrao_horas}
                onChange={(e) => setForm({ ...form, intervalo_padrao_horas: Number(e.target.value) })}
              />
            </Field>
            <Field label="Meta diária de notícias" hint="Usada no Dashboard ('faltam X notícias para bater a meta')">
              <input
                type="number"
                min={0}
                max={100}
                className={`${inputClass} w-40`}
                value={form.meta_diaria}
                onChange={(e) => setForm({ ...form, meta_diaria: Number(e.target.value) })}
              />
            </Field>
          </div>
        </Expander>
      </div>

      {schemaSql && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={() => setSchemaSql('')}>
          <div
            className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-slate-300 bg-white p-6 dark:border-slate-700 dark:bg-card"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-2 font-bold">Schema SQL para o Supabase</h3>
            <p className="mb-4 text-xs text-slate-500">
              Execute este SQL no SQL Editor do painel do Supabase antes de migrar. Ele cria as tabelas blogs, noticias,
              configuracoes e logs com os mesmos campos do banco local.
            </p>
            <pre className="overflow-x-auto rounded-lg bg-night p-4 text-xs text-emerald-300 dark:bg-slate-900">
              <code>{schemaSql}</code>
            </pre>
            <div className="mt-4 flex justify-end">
              <Button onClick={() => setSchemaSql('')}>Fechar</Button>
            </div>
          </div>
        </div>
      )}

      <Card>
        <p className="text-xs text-slate-500">
          Nada de travas de pré-registro: as credenciais só são exigidas no momento da ação que precisa delas.
          Sem validação, tudo nesta página é opcional.
        </p>
      </Card>
    </div>
  );
}

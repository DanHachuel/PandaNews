import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet } from '../lib/api';
import type { Blog, Dashboard } from '../lib/types';
import { Badge, Button, Card } from '../components/ui';
import { GerarNoticiaModal } from '../components/GerarNoticiaModal';

export function Dashboard() {
  const [gerarAberto, setGerarAberto] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => apiGet<Dashboard>('/dashboard'),
    refetchInterval: 15000,
  });
  const { data: blogs } = useQuery({ queryKey: ['blogs'], queryFn: () => apiGet<Blog[]>('/blogs') });

  if (isLoading || !data) {
    return <p className="text-slate-500">Carregando…</p>;
  }

  const max = Math.max(1, ...data.geracao_7dias.map((d) => d.total));
  const onb = data.onboarding;
  const onbItens = [
    { feito: onb.llm_configurado, label: 'Configure um provedor de LLM (NVIDIA ou Gemini)', to: '/configuracoes' },
    { feito: onb.tem_blog, label: 'Crie seu primeiro blog', to: '/blogs' },
    { feito: onb.tem_noticia, label: 'Gere a primeira notícia', to: '/noticias' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-extrabold">Dashboard</h1>
        {/* Lei de von Restorff: ação principal em verde vibrante (Lei de Fitts: grande) */}
        <Button onClick={() => setGerarAberto(true)} disabled={(blogs ?? []).length === 0} title={(blogs ?? []).length === 0 ? 'Crie um blog primeiro' : undefined}>
          ⚡ Gerar notícia agora
        </Button>
      </div>

      <GerarNoticiaModal open={gerarAberto} blogs={blogs ?? []} onClose={() => setGerarAberto(false)} />

      {/* Efeito Zeigarnik: checklist de onboarding com progresso visível */}
      <Card>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-bold">Primeiros passos</h2>
          <span className="text-sm text-slate-500">{onb.concluidos} de 3 concluídos</span>
        </div>
        <div className="mb-4 h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
          <div
            className="h-full rounded-full bg-panda transition-all"
            style={{ width: `${(onb.concluidos / 3) * 100}%` }}
          />
        </div>
        <ul className="space-y-2">
          {onbItens.map((item) => (
            <li key={item.label} className="flex items-center justify-between gap-3">
              <span className={`text-sm ${item.feito ? 'text-slate-400 line-through' : ''}`}>{item.label}</span>
              {item.feito ? (
                <Badge tone="green">✓ feito</Badge>
              ) : (
                <Link to={item.to} className="text-sm font-semibold text-panda hover:underline">
                  fazer agora →
                </Link>
              )}
            </li>
          ))}
        </ul>
      </Card>

      {/* Lei de Miller: 4 blocos de estatística */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Blogs" value={data.blogs_total} hint={`${data.blogs_ativos} ativo(s)`} />
        <Stat label="Notícias hoje" value={data.noticias_hoje} hint={`${data.noticias_total} no total`} />
        <Stat label="Pendentes de revisão" value={data.noticias_pendentes} hint="status rascunho" />
        <Stat label="Erros registrados" value={data.erros_total} hint="pipeline e blogs" />
      </div>

      {/* Gradiente de Meta: geração nos últimos 7 dias */}
      <Card>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-bold">Geração de notícias — últimos 7 dias</h2>
          <Badge tone={data.scheduler_ativo ? 'green' : 'neutral'}>
            scheduler {data.scheduler_ativo ? 'ativo' : 'pausado'}
          </Badge>
        </div>
        <div className="flex h-40 items-end gap-2">
          {data.geracao_7dias.map((d) => (
            <div key={d.data} className="flex flex-1 flex-col items-center gap-1">
              <div
                className="w-full rounded-t-md bg-panda/70"
                style={{ height: `${Math.max(4, (d.total / max) * 100)}%` }}
                title={`${d.data}: ${d.total} notícia(s)`}
              />
              <span className="text-[10px] text-slate-500">{d.data.slice(5)}</span>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <h2 className="mb-3 font-bold">Últimos erros</h2>
        {data.ultimos_erros.length === 0 ? (
          <p className="text-sm text-slate-500">Nenhum erro registrado. 🎉</p>
        ) : (
          <ul className="space-y-2">
            {data.ultimos_erros.map((e) => (
              <li key={e.id} className="flex items-start justify-between gap-3 text-sm">
                <span className="text-slate-500">{e.mensagem}</span>
                <Badge tone="red">{e.etapa}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: number; hint: string }) {
  return (
    <Card className="text-center">
      <div className="text-3xl font-extrabold text-panda">{value}</div>
      <div className="mt-1 text-sm font-semibold">{label}</div>
      <div className="text-xs text-slate-500">{hint}</div>
    </Card>
  );
}

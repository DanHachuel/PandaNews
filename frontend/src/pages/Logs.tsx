import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../lib/api';
import type { LogItem } from '../lib/types';
import { Badge, Card, Empty, selectClass } from '../components/ui';

export function Logs() {
  const [status, setStatus] = useState('');
  const [etapa, setEtapa] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['logs', status, etapa],
    queryFn: () => {
      const params = new URLSearchParams();
      if (status) params.set('status', status);
      if (etapa) params.set('etapa', etapa);
      return apiGet<LogItem[]>(`/logs${params.toString() ? `?${params}` : ''}`);
    },
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-extrabold">Logs</h1>

      <div className="flex flex-wrap items-center gap-3">
        <select className={`${selectClass} w-44`} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Todos os status</option>
          <option value="sucesso">Sucesso</option>
          <option value="erro">Erro</option>
        </select>
        <select className={`${selectClass} w-44`} value={etapa} onChange={(e) => setEtapa(e.target.value)}>
          <option value="">Todas as etapas</option>
          <option value="blog">Blog</option>
          <option value="coleta">Coleta</option>
          <option value="redacao">Redação</option>
          <option value="imagem">Imagem</option>
          <option value="publicacao">Publicação</option>
        </select>
      </div>

      {isLoading ? (
        <p className="text-slate-500">Carregando…</p>
      ) : !data || data.length === 0 ? (
        <Empty
          icon="📜"
          title="Nenhum log ainda"
          message="Execuções do pipeline (coleta, redação, imagem, publicação) aparecem aqui conforme o scheduler roda."
        />
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-slate-700">
                <th className="pb-2 pr-4">Quando</th>
                <th className="pb-2 pr-4">Etapa</th>
                <th className="pb-2 pr-4">Status</th>
                <th className="pb-2">Mensagem</th>
              </tr>
            </thead>
            <tbody>
              {data.map((l) => (
                <tr key={l.id} className="border-b border-slate-100 last:border-0 dark:border-slate-800">
                  <td className="py-2 pr-4 text-slate-500">{new Date(l.created_at).toLocaleString('pt-BR')}</td>
                  <td className="py-2 pr-4">{l.etapa}</td>
                  <td className="py-2 pr-4">
                    <Badge tone={l.status === 'erro' ? 'red' : 'green'}>{l.status}</Badge>
                  </td>
                  <td className="py-2 text-slate-500">{l.mensagem}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiSend } from '../lib/api';
import type { ImagemItem } from '../lib/types';
import { Badge, Button, Card, Empty, Field, inputClass } from '../components/ui';

export function Imagens() {
  const queryClient = useQueryClient();
  const [prompt, setPrompt] = useState('');
  const [resultado, setResultado] = useState<{ ok: boolean; url?: string; detail?: string } | null>(null);

  const { data: imagens, isLoading } = useQuery({
    queryKey: ['imagens'],
    queryFn: () => apiGet<ImagemItem[]>('/imagens'),
  });

  const gerar = useMutation({
    mutationFn: (texto: string) => apiSend<{ ok: boolean; url?: string; detail?: string }>('/imagens/gerar', 'POST', { prompt: texto }),
    onSuccess: (data) => {
      setResultado(data);
      if (data.ok) {
        setPrompt('');
        queryClient.invalidateQueries({ queryKey: ['imagens'] });
        queryClient.invalidateQueries({ queryKey: ['noticias'] });
      }
    },
    onError: (e: Error) => setResultado({ ok: false, detail: e.message }),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-extrabold">Imagens</h1>

      {isLoading ? (
        <p className="text-slate-500">Carregando…</p>
      ) : !imagens || imagens.length === 0 ? (
        <Empty
          icon="🖼️"
          title="Galeria vazia"
          message="Imagens geradas pelo pipeline (e manualmente abaixo) aparecem aqui, reutilizáveis nas notícias."
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {imagens.map((img) => (
            <Card key={img.noticia_id} className="p-3">
              {/* Lei de Fitts: imagem clicável amplia (link) */}
              <a href={img.url} target="_blank" rel="noreferrer">
                <img src={img.url} alt={img.titulo} className="h-44 w-full rounded-lg object-cover" />
              </a>
              <p className="mt-2 line-clamp-2 text-sm font-medium">{img.titulo}</p>
              <p className="text-xs text-slate-500">{new Date(img.created_at).toLocaleString('pt-BR')}</p>
            </Card>
          ))}
        </div>
      )}

      <Card>
        <h2 className="mb-1 font-bold">Gerar imagem manualmente</h2>
        <p className="mb-4 text-sm text-slate-500">
          Prompt livre para a Gemini Image (requer API key do Google configurada em Configurações).
        </p>
        <div className="space-y-4">
          <Field label="Prompt visual">
            <textarea
              className={`${inputClass} h-auto py-2.5`}
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Ex.: estádio lotado ao entardecer, fotojornalismo"
            />
          </Field>
          <Button onClick={() => prompt.trim() && gerar.mutate(prompt.trim())} disabled={gerar.isPending || !prompt.trim()}>
            {gerar.isPending ? 'Gerando…' : 'Gerar imagem'}
          </Button>
          {resultado && !resultado.ok && (
            <p className="rounded-lg border border-red-400/40 bg-red-500/10 p-3 text-sm text-red-400">{resultado.detail}</p>
          )}
          {resultado?.ok && resultado.url && (
            <div className="rounded-lg border border-panda/40 bg-panda/10 p-3">
              <Badge tone="green">imagem gerada</Badge>
              <img src={resultado.url} alt="Imagem gerada" className="mt-2 max-h-56 rounded-lg" />
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

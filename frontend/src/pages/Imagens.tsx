import { Card, Empty, Field, Button, inputClass } from '../components/ui';

export function Imagens() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-extrabold">Imagens</h1>

      <Empty
        icon="🖼️"
        title="Galeria vazia"
        message="Imagens fotojornalísticas geradas pelo Gemini Image aparecem aqui, junto com o notícia de origem. A geração automática chega com o pipeline de notícias (próxima versão)."
      />

      <Card>
        <h2 className="mb-1 font-bold">Gerar imagem manualmente</h2>
        <p className="mb-4 text-sm text-slate-500">
          Chega com o pipeline de imagens (Fase 3) — a chamada à Gemini Image API será disparada a partir deste
          formulário.
        </p>
        <div className="space-y-4 opacity-50">
          <Field label="Prompt visual">
            <textarea className={`${inputClass} h-auto py-2.5`} rows={3} placeholder="Ex.: estádio lotado ao entardecer, fotojornalismo" disabled />
          </Field>
          <Button disabled>Gerar imagem</Button>
        </div>
      </Card>
    </div>
  );
}

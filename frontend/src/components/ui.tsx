import { ReactNode, useState } from 'react';

// Lei de Fitts: botões primários grandes (h-10+) e destrutivos isolados.
export function Button({
  children,
  onClick,
  variant = 'primary',
  type = 'button',
  disabled,
  title,
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'danger';
  type?: 'button' | 'submit';
  disabled?: boolean;
  title?: string;
}) {
  const base =
    'inline-flex items-center justify-center gap-2 rounded-lg px-4 h-10 text-sm font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed';
  const styles = {
    primary: 'bg-panda text-slate-900 hover:bg-panda-dark',
    secondary:
      'bg-transparent border border-slate-300 text-slate-700 hover:border-slate-400 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-500',
    danger: 'bg-red-600 text-white hover:bg-red-700',
  } as const;
  return (
    <button type={type} className={`${base} ${styles[variant]}`} onClick={onClick} disabled={disabled} title={title}>
      {children}
    </button>
  );
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-card ${className}`}
    >
      {children}
    </div>
  );
}

export function Badge({
  children,
  tone = 'neutral',
}: {
  children: ReactNode;
  tone?: 'neutral' | 'green' | 'amber' | 'red' | 'blue';
}) {
  const tones = {
    neutral: 'bg-slate-200 text-slate-600 dark:bg-slate-700/60 dark:text-slate-300',
    green: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400',
    amber: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400',
    red: 'bg-red-100 text-red-600 dark:bg-red-500/15 dark:text-red-400',
    blue: 'bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-400',
  } as const;
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${tones[tone]}`}>
      {children}
    </span>
  );
}

// Efeito von Restorff: rascunho destaca em âmbar; aprovado/publicado em verde/azul.
export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, 'neutral' | 'green' | 'amber' | 'red' | 'blue'> = {
    rascunho: 'amber',
    aprovado: 'green',
    publicado: 'blue',
    rejeitado: 'red',
    ativo: 'green',
    pausado: 'neutral',
  };
  return <Badge tone={map[status] ?? 'neutral'}>{status}</Badge>;
}

// Lei de Jakob: confirmação modal para ações destrutivas.
export function ConfirmModal({
  open,
  title,
  message,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onCancel}>
      <div
        className="w-full max-w-md rounded-xl border border-slate-300 bg-white p-6 dark:border-slate-700 dark:bg-card"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-2 text-lg font-bold">{title}</h3>
        <p className="mb-6 text-sm text-slate-500 dark:text-slate-400">{message}</p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onCancel}>
            Cancelar
          </Button>
          <Button variant="danger" onClick={onConfirm}>
            Excluir
          </Button>
        </div>
      </div>
    </div>
  );
}

// Lei de Hick / Miller: revelação progressiva em blocos de até 7 itens.
export function Expander({
  title,
  children,
  defaultOpen = false,
}: {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-card">
      <button
        className="flex w-full items-center justify-between px-5 py-4 text-left font-semibold"
        onClick={() => setOpen(!open)}
      >
        <span>{title}</span>
        <span className={`text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`}>▾</span>
      </button>
      {open && <div className="border-t border-slate-200 px-5 py-5 dark:border-slate-800">{children}</div>}
    </div>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-slate-500 dark:text-slate-400">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-400 dark:text-slate-500">{hint}</span>}
    </label>
  );
}

export const inputClass =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-800 placeholder-slate-400 outline-none focus:border-panda h-10 dark:border-slate-700 dark:bg-night dark:text-slate-200 dark:placeholder-slate-500';

export const selectClass = inputClass;

export function Empty({ icon, title, message }: { icon: string; title: string; message: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 px-6 py-14 text-center dark:border-slate-700">
      <div className="mb-3 text-4xl">{icon}</div>
      <h3 className="mb-1 font-semibold">{title}</h3>
      <p className="max-w-sm text-sm text-slate-500">{message}</p>
    </div>
  );
}

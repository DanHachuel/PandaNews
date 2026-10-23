export interface SecretInfo {
  configured: boolean;
  preview: string;
}

export interface Blog {
  id: number;
  nome: string;
  tema: string;
  regiao: string;
  fontes_rss: string[];
  estilo_editorial: string;
  frequencia_horas: number;
  status: string;
  created_at: string;
}

export interface Noticia {
  id: number;
  blog_id: number;
  titulo: string;
  corpo: string;
  resumo: string;
  imagem_url: string;
  status: string;
  llm_provider: string;
  created_at: string;
}

export interface LogItem {
  id: number;
  blog_id: number | null;
  etapa: string;
  status: string;
  mensagem: string;
  created_at: string;
}

export interface Configuracoes {
  nvidia_api_key: SecretInfo;
  nvidia_base_url: string;
  nvidia_model: string;
  google_api_key: SecretInfo;
  google_base_url: string;
  google_model: string;
  llm_fallback_ordem: string;
  db_backend: string;
  supabase_url: string;
  supabase_service_role_key: SecretInfo;
  scheduler_ativo: boolean;
  intervalo_padrao_horas: number;
}

export interface Dashboard {
  blogs_total: number;
  blogs_ativos: number;
  noticias_total: number;
  noticias_hoje: number;
  noticias_pendentes: number;
  erros_total: number;
  scheduler_ativo: boolean;
  geracao_7dias: { data: string; total: number }[];
  ultimos_erros: LogItem[];
  onboarding: {
    llm_configurado: boolean;
    tem_blog: boolean;
    tem_noticia: boolean;
    concluidos: number;
  };
}

"""Camada de dados do PandaNews (Fase 1).

SQLite local por padrão (data/pandanews.db) via SQLAlchemy 2.0, com detecção
automática de Supabase quando SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY estão
definidas no ambiente. Tabelas: blogs, noticias, configuracoes, logs.
"""

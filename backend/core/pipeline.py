"""Pipeline de notícias do PandaNews (Fase 3).

Coleta RSS -> filtragem por relevância -> rascunho via LLM -> imagem via Gemini
-> revisão humana opcional -> publicação. Disparado por APScheduler conforme a
frequência de cada blog ou manualmente pela interface.
"""

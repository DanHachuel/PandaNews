"""Router de LLM do PandaNews (Fase 1).

Fallback ordenado configurável (padrão: NVIDIA NIM -> Google Gemini) usando
llmswitch-client: roteamento por prioridade com circuit breaker. Retorna o
texto gerado e o provedor que respondeu (registrado em noticias.llm_provider).
"""

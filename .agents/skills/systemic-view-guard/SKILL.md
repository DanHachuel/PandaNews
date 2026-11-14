---
name: systemic-view-guard
description: Evitar que uma alteração local quebre dependências ocultas entre frontend, backend e launcher. Leia antes de mudar assinatura de função, endpoint, schema do banco ou o ciclo de vida do processo.
---

# systemic-view-guard

**Propósito:** correção de um módulo que quebra outro é a regressão mais comum deste projeto.
Antes de alterar, veja o sistema inteiro.

## Mapa de dependências

```
frontend/src/            React — consome a API REST (apiGet/apiSend em src/lib/api.ts)
   │
backend/app/routers/     Endpoints FastAPI — dependem de backend/core/
   │
backend/core/            Regras de negócio: llm_router, pipeline, wordpress_publisher,
   │                     image_gen, database, scheduler, auth, proc, supabase_db
   │
bin/cli.js + scripts/    Launcher: install, start, build, kill — controla o ciclo de vida do
                         processo e o runtime em ~/.pandanews/runtime
```

- `~/.pandanews/runtime` é onde o código **realmente roda** em produção: uma correção no
  repositório que não muda a versão do pacote pode não chegar lá (o `start` só actualiza a cópia
  quando a versão muda).
- `backend/core/config.py` (`DEFAULT_LLM_BASE_URLS`, `DEFAULT_LLM_MODELS`) é lido pelo router, pelo
  frontend (via GET /configuracoes) e pelos testes — mudar o default muda a UI.
- `backend/core/llm_router.py` é usado pelos routers (`configuracoes.py`) **e** pelo pipeline.

## Regras

1. **Mudou assinatura?** Actualize todos os chamadores. Ex.: `publish_to_wordpress(db, noticia)` é
   chamado pelo endpoint `POST /noticias/{id}/publicar`, pelo scheduler e pelos testes.
2. **Mudou endpoint ou o JSON de resposta?** O frontend espera o mesmo formato
   (`frontend/src/lib/types.ts`); actualize os dois lados na mesma tarefa.
3. **Mudou schema do banco?** Há migração leve em `database._migrate()` para bancos existentes e o
   `supabase_db.SCHEMA_SQL` precisa do mesmo campo.
4. **Mudou o launcher ou o ciclo de vida?** Revalide o isolamento de processos
   (`node scripts/test-start-isolation.mjs`) e o ciclo de vida
   (lock `~/.pandanews/pandanews.pid`, `pandanews kill`).
5. **Mudou o prompt do LLM?** O parser (`pipeline._parse_resposta_llm`) e as validações de conteúdo
   dependem do formato pedido.

## Verificação antes de commitar

```bash
node scripts/test-start-isolation.mjs
python backend/tests/test_llm_fallback.py
python backend/tests/test_seo_auth.py
npm run build --prefix frontend
```

Se um teste falha por causa da sua mudança de assinatura, o conserto é actualizar o chamador — não
enfraquecer o teste.
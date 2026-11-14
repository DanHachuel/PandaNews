---
name: llm-resilience-guard
description: Garantir que a geração de notícias nunca pare por falha de API externa. Leia antes de tocar em backend/core/llm_router.py, no pipeline de geração, nos provedores LLM ou no teste de conexão.
---

# llm-resilience-guard

**Propósito:** a notícia tem de ser gerada sempre — falha de provedor troca de provedor, nunca
estoura na tela do usuário.

## 1. Fallback implacável

`backend/core/llm_router.py:gerar_texto()` percorre `llm_fallback_ordem` (default `nvidia,google`)
e captura **`Exception`** — não importa se é HTTP 4xx/5xx (inclusive 404/410 de modelo
descontinuado), timeout, queda de rede ou JSON inválido:

```python
except Exception as exc:  # noqa: BLE001 — fallback implacável: TUDO troca de provedor
```

- O incidente é registrado no log (`logger = logging.getLogger("uvicorn.error.pandanews")`) no
  formato exigido: `Erro na NVIDIA ({e}). Acionando Google Gemini...`.
- O próximo provedor assume **na mesma iteração**; a notícia nasce sem tela de erro.
- Se todos falharem, o erro é explícito: `RuntimeError` com "Todos os provedores de LLM falharam
  (...)" — nunca silêncio.
- O provedor devolvido ao banco/UI mantém o rótulo `gemini` (id de exibição), não o id interno
  `google`.

## 2. Sanitização de modelos (hotfix 0.5.03)

O PandaNews fala com a NVIDIA por **HTTP direto**
(`POST https://integrate.api.nvidia.com/v1/chat/completions`) — não passa por proxy. Prefixos de
convenção de outras ferramentas (LiteLLM: `nvidia_nim/`) **não são reconhecidos** pela API e
geram erro de modelo não encontrado.

- Use `limpar_nome_modelo()` (`llm_router.py`, com `PREFIXOS_PROXY`) antes de montar o payload:
  ```python
  modelo = limpar_nome_modelo(cfg["model"])
  payload = {"model": modelo, "messages": [...], "temperature": 0.7, "max_tokens": max_tokens}
  ```
- A barra dentro do id (`mistralai/mistral-large-4-1t-a52b`) é legítima e **não** é removida —
  apenas o prefixo de proxy.
- A sanitização vale também para leitura/escrita em Configurações e para a lista do endpoint
  `/configuracoes/llm/nvidia/models` (id limpo dos dois lados, para `modelo_atual_disponivel` não
  acusar falso "fora do catálogo").
- Ids de modelo têm fim de vida: o default já queimou `meta/llama-3.3-70b-instruct` (410 Gone) e
  `meta/llama-3.1-nemotron-70b-instruct` (404). Confirme o catálogo ao vivo antes de trocar o
  default em `backend/core/config.py:DEFAULT_LLM_MODELS`.

## 3. Dependências fantasmas — proibidas

É **proibido** importar biblioteca que não esteja em `backend/requirements.txt`. O caso real: o
código importava `from openai import ...` sem `openai` declarado — em instalação nova o backend
morria com `ImportError` antes de qualquer chamada. Use `httpx` (já é dependência) ou `requests`.

Estrutura da chamada (réplica do projeto Thunderbolt, que funciona):

```
POST {base_url}/chat/completions
Authorization: Bearer <api_key>
Content-Type:  application/json
Accept:        application/json
{"model": ..., "messages": [...], "max_tokens": ..., "temperature": ...}
```

A Base URL é normalizada por `_normalizar_base_url()` — `/v1`, `/v1/models` e
`/v1/chat/completions` são aceitos sem duplicar o sufixo (evita 404).

## 4. Validação real do "Testar Conexão"

`llm_router.py:test_provider()` faz um `chat/completions` de verdade com `max_tokens=1` — **não**
apenas lista modelos. A string de erro do provedor volta no JSON para o frontend exibir:

- 401/403 → mensagem de credencial explícita;
- 404/410 → `degraded: True` (a chave pode ser válida, mas o modelo saiu do catálogo) com instrução
  de trocar pelo botão ↻;
- outros >= 400 → código e corpo devolvidos.

**Antes de commitar.** rode `python backend/tests/test_llm_fallback.py` (35 verificações).
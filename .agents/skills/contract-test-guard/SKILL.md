---
name: contract-test-guard
description: Garantir que os testes validem comportamento real (payload HTTP, flags de processo, rotas protegidas). Leia antes de escrever ou alterar qualquer teste do projeto.
---

# contract-test-guard

**Propósito:** teste que só olha função mockada não pega regressão. Os testes do PandaNews validam
o **contrato** — o JSON que sai, a flag que nasce no processo, o status HTTP que volta.

## 1. Teste o payload HTTP, não o mock

Para integrações externas (NVIDIA, Gemini, WordPress), intercepte a requisição **real** e valide o
JSON enviado:

```python
class _ClientCapturador:
    def post(self, endpoint, headers=None, json=None):
        payloads_enviados.append(json)      # captura o que iria para a NVIDIA
        return _RespostaHttp(200, {...})
```

- **Prefira substituir apenas o `httpx.Client`** e deixar a construção da URL, dos headers e do
  `raise_for_status()` rodarem de verdade — foi assim que o teste de fallback pegou o 410 no caminho
  HTTP completo.
- Contratos já verificados por teste neste projeto:
  - `payload["model"] == "mistralai/mistral-large-4-1t-a52b"` — prefixo `nvidia_nim/` fora
    (`backend/tests/test_llm_fallback.py`, secção 5);
  - imagem do WordPress em **binário**, `featured_media` com o `id` devolvido pelo
    `POST /wp-json/wp/v2/media` (`backend/tests/test_seo_auth.py`).
- Se um mock devolve dados que a API real não devolveria, o teste passa e a produção quebra.

## 2. Teste de UI e rotas protegidas

- Rota protegida **sem token** → esperar `401`.
- Rota protegida **com token válido** → esperar `200`.
- Erro de credencial tem de voltar em texto compreensível para a tela (a string do provedor vai no
  JSON, não só um código).

## 3. Regressão: cada bug corrigido ganha um teste que falha se a causa voltar

| Regressão | Teste que a prende |
|---|---|
| Janela CMD / flag de spawn removida | `scripts/test-start-isolation.mjs` (51 verificações; falha se `windowsHide` sumir de qualquer spawn) |
| `subprocess.run` direto no backend Python | mesmo teste (varre `backend/**/*.py`) |
| Modelo NVIDIA com prefixo de proxy | `backend/tests/test_llm_fallback.py` secção 5 |
| Fallback não aciona o Gemini no 410 | `backend/tests/test_llm_fallback.py` (log `Erro na NVIDIA (...). Acionando Google Gemini...`) |
| Artigo sem `<h2>` sendo publicado | `backend/tests/test_seo_auth.py` |

Verificação por mutação: antes de confiar no teste, quebre a causa (remova a flag, devolva o modelo
com prefixo, mude o status para 200) e confirme que o teste falha. Teste que nunca falha não é
teste.

## 4. Como os testes rodam

Sem pytest, sem servidor, sem dependências extras — `python backend/tests/<arquivo>.py`, com stubs
de `backend.core.database` quando o ORM não é necessário (ver `test_llm_fallback.py` e
`test_seo_auth.py`). Todos são agregados ao CI em `.github/workflows/publish-npm.yml`.

**Antes de commitar.** rode os três: `test_llm_fallback.py`, `test_seo_auth.py` e
`node scripts/test-start-isolation.mjs`.
---
name: surgical-scope-guard
description: Impedir refatorações não solicitadas e alterações em arquivos sensíveis. Leia antes de começar qualquer tarefa de bugfix ou feature pequena.
---

# surgical-scope-guard

**Propósito:** a tarefa é o que foi pedido. Nada mais.

## 1. Regra do menor arquivo possível

- Bug no frontend → mexa só em `frontend/`. Não mexa em `backend/`, `requirements.txt`, `scripts/`.
- Bug de sanitização de modelo → mexa em `backend/core/llm_router.py` e nos testes. Não reformate o
  router inteiro.
- Docs/skill → mexa só em `.agents/` e no CHANGELOG. **Não altere código funcional do app.**

## 2. Proibição de refatoração estética

- Não renomeie variáveis, não reordene imports, não troque aspas simples por duplas, não
  "modernize" código antigo sem necessidade técnica.
- Altere **apenas as linhas estritamente necessárias** à tarefa.
- Não corrija ortografia de comentários/alterações de outro autor no meio do diff.
- Um diff grande em tarefa pequena é sinal de violação desta skill — revise antes de commitar.

## 3. Arquivos sensíveis (não altere sem autorização explícita)

- `package.json` — versão e `bin` só mudam em release;
- `backend/requirements.txt` — dependência nova precisa de justificativa forte (dependência fantasma
  já derrubou o backend);
- `scripts/start.js`, `scripts/install.js` — ciclo de vida do processo, risco de janela CMD/EBUSY;
- `.github/workflows/publish-npm.yml` — esteira de publicação;
- `AGENTS.md` — regras permanentes do projeto.

## 4. Como saber se está no escopo

Antes de escrever, responda: *este arquivo é necessário para o critério de aceitação?*
Se a resposta for não, feche o arquivo.

**Exceção legítima:** documentar uma mudança no `CHANGELOG.md` e a entrada de regra no `AGENTS.md`
são obrigatórias por regra do projeto — não são "refatoração".
---
name: parallel-session-guard
description: Evitar colisões entre sessões de IA simultâneas no mesmo repositório. Leia antes de commitar, rebasear ou publicar qualquer versão do npm.
---

# parallel-session-guard

**Propósito:** o usuário corre várias sessões de IA em paralelo no mesmo repositório. Colisão de
versão ou de trabalho não comittado já causou retrabalho — estas regras impedem que se repita.

## 1. Verificação pré-commit (obrigatória)

Antes de **qualquer** `git commit`:

```bash
git fetch origin
git status -sb          # main está ahead/behind de origin/main?
git log --oneline origin/main -3
```

- Se `origin/main` avançou, faça `git rebase origin/main` **antes** de commitar.
- Se houver arquivos modificados que **não são da sua tarefa**, **pare e reporte** — provavelmente
  são de outra sessão. Não commite, não descarte (`checkout --`, `reset --hard`), não "conserte".

## 2. Colisão de versão

Antes de publicar, confirme o que já existe no registry:

```bash
npm view @danhachuel/pandanews versions --json
npm view @danhachuel/pandanews dist-tags --json
```

- **Regra de ouro: a versão já publicada no `latest` vence.** O seu trabalho é rebaseado por cima
  dela e renumera para o patch seguinte.
- Exemplo real: a 0.5.05 já estava publicada por outra sessão → a sessão seguinte renumou para
  0.5.06.
- Convenção visual: PATCH com dois dígitos (`0.5.06`), nunca acima de 99; ao estourar, avança o
  MINOR e o PATCH reinicia em `00`. O npm normaliza para a versão canônica (`0.5.06` → `0.5.6`).

## 3. Ao integrar trabalho de outra sessão

- Se a outra sessão já comittou, apenas rebaseie e siga.
- Se ela **não** tem entrada no CHANGELOG, documente-a retroactivamente (regra do AGENTS.md:
  nenhuma versão sai sem registo).
- Se deixou duas entradas para a mesma versão, deduplique mantendo a mais completa.

## 4. Push obrigatório

Sempre que a sessão criar commits, `git push origin main` imediatamente — nunca deixar trabalho
apenas no disco local. Não perguntar ao usuário se deve fazer push: faça sempre.

## 5. Publicação sempre via GitHub Actions

Nunca `npm publish` local. Sequência:

1. bump de versão (`package.json` + `backend/app/main.py`) → commit → push;
2. dispatch manual do workflow *Publish npm package* com `dist_tag=next`;
3. push da tag `vX.Y.ZZ` → o workflow verifica o tarball e promove a versão a `latest`.

**Antes da tag.** confirme que `latest`/`next` apontam para a versão esperada.
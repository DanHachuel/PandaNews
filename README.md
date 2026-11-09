# PandaNews

SaaS **local** (roda no navegador) para criação e automação de múltiplos blogs de notícias com IA.

- Blogs multi-tenant com tema (esporte, política, economia, tecnologia, geral) e recorte regional
- Coleta de feeds RSS → redação via LLM com fallback **NVIDIA NIM → Google Gemini**
- Imagens fotojornalísticas via Gemini Image
- Fluxo editorial: rascunho → revisão humana opcional → aprovado/publicado
- 100% local por padrão (SQLite + arquivos), com Supabase opcional
- Agendamento automático por blog (APScheduler)

## Instalação e uso — um único comando

CMD / MobaXterm:

```
npx.cmd --yes --prefer-online @danhachuel/pandanews
```

Shell (PowerShell, Linux, macOS):

```
npx --yes @danhachuel/pandanews
```

Na primeira execução o PandaNews instala **tudo junto, automaticamente**: runtime Python portátil, dependências do backend e banco de dados local (SQLite). Nenhum Python, pip ou outra dependência pré-instalada é necessária — apenas **Node.js >= 20**.

Opcional — pré-instalar antes do primeiro uso:

```
npx.cmd --yes --prefer-online @danhachuel/pandanews install
npx --yes @danhachuel/pandanews install
```

O runtime fica em `~/.pandanews` (sobrescreva com a variável de ambiente `PANDANEWS_HOME`) — **upgrades de versão não reinstalam** o que já existe: o instalador detecta Python, dependências e dados já presentes e só instala o que falta.

### Atualizar de versão

**Recomendado (mais rápido em qualquer sistema):**

```
npm.cmd install -g @danhachuel/pandanews@latest
pandanews
```

**Com `npx` também funciona:**

```
npx.cmd --yes --prefer-online @danhachuel/pandanews@latest
```

**Sobre o EBUSY do `npx` no Windows** — em versões antigas, actualizar por `npx` falhava com `npm error code EBUSY` / `syscall rename`. A causa: o `npx` baixa o pacote para uma pasta de cache própria e, ao terminar, tenta renomear/apagar essa pasta — mas o backend, que corre em background (destacado, sobrevive ao fechamento do terminal), ainda segurava ficheiros dentro dela.

**Isso está corrigido desde a 0.5.02**: o servidor **nunca** corre de dentro do cache do `npx`. O comando `install` copia o código para um runtime permanente em `~/.pandanews/runtime`, e o `start` actualiza essa cópia quando a versão muda, subindo backend e UI sempre a partir daí. O cache do `npx` fica livre para ser renomeado.

Ainda assim, `npm install -g` evita o download repetido a cada execução e por isso é a via recomendada.

### Encerrar o app em background

O backend roda destacado e **sobrevive ao fechamento do terminal** — incluindo o Ctrl+C. Para encerrá-lo sem reiniciar a máquina:

```
npx.cmd --yes --prefer-online @danhachuel/pandanews@latest kill
```

(o atalho `pandanews stop` também funciona). O comando lê o lock global `~/.pandanews/pandanews.pid`, encerra o backend e o launcher **por código**, sem abrir nenhuma janela de terminal, e limpa o lock.

Ao iniciar uma nova versão, o launcher **encerra a instância anterior automaticamente** antes de subir — não é preciso matar à mão.

## Status (versão 0.4.00)

- **Pipeline completo**: coleta RSS → redação via LLM (fallback NVIDIA → Gemini) → imagem fotojornalística via Gemini Image → rascunho para revisão
- **Scheduler ativo**: um job por blog ativo (frequência configurável), toggle global em Automação e execução imediata (⚡ Gerar notícia agora)
- **Supabase opcional**: detecção automática de credenciais, teste de conexão, schema SQL e migração SQLite → Supabase — o app segue 100% local por padrão
- **Meta diária** no Dashboard ("faltam X notícias") e breadcrumbs em todas as telas internas
- Páginas legais/de verificação em `legal/` (LGPD), meta diária configurável e revisão das 7 leis de usabilidade concluídas
- Produto alinhado ao plano mestre: Fases 0 a 6 concluídas

- `npx @danhachuel/pandanews` instala tudo junto (Python portátil + dependências + banco local) e sobe o backend em 127.0.0.1:8000 com página em 127.0.0.1:4030 — se a porta estiver ocupada, usa a seguinte automaticamente (4031, 4032, ...)
- A UI React completa (Dashboard, Blogs, Notícias, Imagens, Automação, Configurações) e o pipeline de notícias chegam nas próximas versões (Fases 1 a 3 do plano — ver `CHANGELOG.md`)

## Regras do projeto

Versionamento (PATCH de dois dígitos), release via GitHub Actions, CHANGELOG obrigatório e demais regras permanentes estão em [`AGENTS.md`](AGENTS.md).

## Licença

MIT — veja [LICENSE](LICENSE).

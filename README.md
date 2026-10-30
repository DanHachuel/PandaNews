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

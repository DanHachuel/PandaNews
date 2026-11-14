---
name: wordpress-seo-guard
description: Proteger a conta Google AdSense do usuário e garantir publicações corretas no WordPress. Leia antes de tocar no prompt do LLM, no pipeline de geração, no publicador WordPress ou no endpoint de publicação.
---

# wordpress-seo-guard

**Propósito:** publicar no WordPress sem perder a conta AdSense do usuário e sem quebrar o blog.

## 1. Estrutura HTML semântica (diretriz AdSense)

- O prompt de redação (`backend/core/pipeline.py:_prompt_redacao`) exige **HTML semântico**:
  `<h2>`, `<h3>`, `<p>`, `<ul>` — nunca texto puro com quebras de linha.
- Textos sem `<h2>` são **bloqueados**: `pipeline.conteudo_publicavel()` só aprova conteúdo com
  heading e parágrafo; `wordpress_publisher.validar_conteudo()` levanta antes do envio.
- `<h2>` é o mínimo aceitável; a hierarquia `<h2>` → `<h3>` dá a estrutura que o AdSense e o SEO
  exigem.

## 2. Tamanho do conteúdo

- **Mínimo de 1500 palavras** exigido no prompt; teto de tokens da redação elevado para **4000**.
- O backend bloqueia a publicação com **menos de 300 palavras** (`contar_palavras()`), que é a
  diretriz dura do AdSense — artigo fino reprova o site.
- Nunca afrouxe esses limites para "fazer passar": ajuste o prompt ou o teto de tokens, não a
  validação.

## 3. Upload de imagem em 2 etapas

A API REST do WordPress **não** aceita imageminline no post — o fluxo é:

1. `POST /wp-json/wp/v2/media` com o **binário** (`Content-Type` do arquivo, corpo em bytes) →
   devolve o `id` da mídia (`wordpress_publisher._upload_midia()`);
2. `POST /wp-json/wp/v2/posts` com `featured_media: <id da etapa 1>`, `status: 'publish'` e a
   categoria resolvida pelo tema do blog (busca ou cria — `resolver_categoria()`).

Detalhes que já quebraram antes: a imagem precisa ser lida do disco local (`_imagem_local()`), o
`id` tem de ser o devolvido pela etapa 1 (nunca um palpita) e a categoria é resolvida pelo **tema**
do blog, não por id fixo.

## 4. Autenticação

- **Basic Auth** com a **Application Password** gerada no painel do WordPress
  (`wordpress_url`, `wordpress_user`, `wordpress_app_password` salvos no banco, mascarados na UI).
- **Nunca** a senha de login do administrador; nunca commitar ou logar credencial.
- Conexão é testada de verdade: `GET /wp-json/wp/v2/users/me`
  (`wordpress_publisher.testar_conexao()`), não só "salvou sem erro".

## 5. Boas práticas de publicação

- Republicação é bloqueada (HTTP 400 "Já publicado") via `noticias.wordpress_post_id`.
- Após publicar: `status=publicado` + link do post devolvido ao frontend.
- Credenciais são validadas **no momento da ação** (regra do AGENTS.md: sem travas de pré-registo).

**Antes de commitar.** rode `python backend/tests/test_seo_auth.py` (prompt, bloqueio sem `<h2>`,
payload WordPress e login).
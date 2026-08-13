# Handoff pro Vergueiro — estado do projeto em 2026-08-12

Este arquivo existe pra te (ou pra sua IA) atualizar rápido sobre o que já foi feito, o que está rodando e o que falta, sem precisar reconstruir o contexto do zero. Leia também `AGENTS.md` (regras obrigatórias do repo) e `docs/BACKLOG.md` antes de codar.

## O que já está pronto

### Issue #15 — Autenticação (Thiago, backend + frontend)
PR: https://github.com/DELTA-42-FORCE/delta-force/pull/41 (aberto, aguardando aprovação/merge em `develop`)

- Login com conta interna, sessão via token opaco (não é cookie, não é JWT — token fica no `localStorage` do navegador e vai no header `Authorization: Bearer <token>`).
- Sem tela/rota de cliente (decisão confirmada no levantamento de requisitos).

### Issue #16 — Gerenciar usuários autorizados (Thiago, backend + frontend)
Branch: `feature/15-autenticacao-backend` (ainda não tem PR próprio — segue em cima da branch do #15 porque depende do código dela).

- CRUD de usuário: criar, listar, editar nome/papel, ativar/desativar — só administrador acessa.
- Papel simples: `is_admin` (true/false). **Não implementa matriz de permissões fina** — isso depende da issue #14, que está bloqueada esperando o administrador aprovar o catálogo.
- Um admin não consegue desativar a própria conta (trava de segurança óbvia).

## Contrato da API (o que o frontend pode chamar)

```
POST /auth/login    {email, password} → 200 {session_token, expires_at, user:{id,email,full_name,is_admin}} | 401
GET  /auth/me        Bearer <token> → 200 {id,email,full_name,is_admin} | 401
POST /auth/logout    Bearer <token> → 204 | 401

POST   /users                Bearer <token admin> {email,full_name,password,is_admin} → 201 | 401 | 403 | 409 (email duplicado)
GET    /users                Bearer <token admin> → 200 [ {id,email,full_name,is_active,is_admin}, ... ] | 401 | 403
PATCH  /users/{id}           Bearer <token admin> {full_name?, is_admin?} → 200 | 401 | 403 | 404
POST   /users/{id}/activate   Bearer <token admin> → 200 | 401 | 403 | 404
POST   /users/{id}/deactivate Bearer <token admin> → 200 | 401 | 403 | 404 | 409 (admin tentando se autodesativar)
```

## Estrutura do frontend já criada

```
apps/web/src/
  lib/apiClient.ts        cliente HTTP genérico (fetch + tratamento de erro + ApiError)
  auth/
    AuthContext.tsx        contexto React: guarda token/usuário, restaura sessão do localStorage
    LoginPage.tsx           tela de login
    authApi.ts              chamadas de /auth/*
  users/
    UsersPage.tsx           tela de gestão de usuários (só aparece se is_admin)
    usersApi.ts             chamadas de /users/*
  App.tsx                   junta tudo: loading da sessão → login → app autenticado
```

**Ainda não existe:** roteador (react-router ou similar). Só tem duas "telas" (login e usuários) trocadas por condicional em `App.tsx`. Se a próxima etapa (cadastro de clientes, documentos, etc.) precisar de mais de 2-3 telas, aí sim vale considerar introduzir um roteador — não antes disso, pra não violar a regra do `AGENTS.md` de não adicionar dependência sem necessidade demonstrada.

Sem gerenciamento de estado global (Redux/Zustand/etc.) — o `AuthContext` nativo do React resolve por enquanto.

## Como rodar localmente

```bash
cp .env.example .env
cp apps/web/.env.example apps/web/.env
just install
just infra-up        # sobe Postgres, MinIO, Mailpit (precisa Docker Desktop instalado)
just api-migrate      # aplica as migrations (cria tabelas users e sessions)
just check            # roda tudo: lint, tipos, testes de API e web
```

Pra rodar só a interface: `cd apps/web && npm run dev` (porta 5173). A API sobe com `cd apps/api && uv run fastapi dev src/crm_api/main.py` (porta 8000).

## O que está bloqueado / pendente

- **Issue #14** (catálogo de campos do cliente, documentos aceitos, matriz de permissões fina) — bloqueada, esperando decisão do administrador/cliente. Praticamente todo o resto do MVP (cadastro de clientes, documentos, checklist, e-mail) depende disso.
- **Issue #26** (LGPD/operação de produção) — também bloqueada, mesma razão.
- Reunião de amanhã (2026-08-13) deve trazer mais requisitos — depois dela, dá pra desbloquear #14 e o time segue pra cadastro de clientes (#18/#19) e documentos (#21/#22).

## Se você (ou sua IA) for pegar a próxima etapa

1. Puxe `develop` atualizado (depois que o PR #41 for aprovado e mergeado).
2. Confira `docs/BACKLOG.md` e as issues no GitHub pra ver o que desbloqueou.
3. Siga o fluxo de `AGENTS.md`: branch a partir de `develop`, rebase antes de codar, `just check` antes de pedir review.
4. Reaproveite `apps/web/src/lib/apiClient.ts` e o padrão de `AuthContext` pra qualquer tela nova que precise do token de sessão.

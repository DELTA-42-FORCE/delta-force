## Resumo

- adiciona fundação append-only de auditoria e migration reversível `0004`;
- registra eventos de setup, login, consulta do proprietário, logout, negações e
  consulta da própria trilha;
- garante commit atômico entre mutações de autenticação e seus eventos;
- expõe `GET /audit/events` autenticado com paginação keyset estável;
- restringe ação, tipo de recurso e contexto a catálogos/allowlists sem PII.

## Base empilhada

Este PR deve usar `feature/15-autenticacao-backend` como base enquanto a PR #41
estiver aberta. Depois que #41 for integrada, rebasear em `origin/develop`,
repetir todos os gates e retargetar o PR.

## Segurança

- sem senha, token/hash, e-mail submetido, Authorization, corpo, IP ou user
  agent no evento/contexto técnico;
- consulta da trilha exige proprietário autenticado e também é auditada;
- ator autenticado é preservado por FK `ON DELETE RESTRICT`;
- falha do append desfaz setup, login/sessão ou logout/revogação correspondente.

## Verificação

- Black: PASS, 71 arquivos;
- Flake8: PASS;
- pytest unitário: 93 passed, 12 deselected;
- PostgreSQL/migrations: 12 passed, 93 deselected;
- upgrade até `0004` e ciclo reversível cobertos;
- `git diff --check`: PASS.

## Limite deliberado

Eventos de clientes, documentos, importação, PDF, e-mail e backup serão
adicionados pelas issues que implementarem esses fluxos. Falha técnica que já
causou rollback não é persistida por transação independente nesta fundação.

Este PR não deve usar `Closes #17` enquanto a issue ainda enumerar eventos das
features futuras.

Refs #17

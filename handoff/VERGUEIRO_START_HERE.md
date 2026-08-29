# Vergueiro — comece por aqui

Estado confirmado em **29 de agosto de 2026**. Leia primeiro `AGENTS.md`,
`docs/adr/0003-sqlite-como-persistencia-local.md`, `docs/MVP_PLAN.md` e
`handoff/PROJECT_CONTINUATION.md`. Use somente dados sintéticos e não faça merge
automático.

## O que já está em `develop`

`origin/develop` está em `2384618` e já contém código real do produto:

- primeira conta, login, sessão e logout do proprietário;
- interface de primeiro acesso, login e painel;
- auditoria append-only, consulta autenticada e histórico na interface;
- ADR 0003 aceita: SQLite em arquivo e filesystem privado são os alvos tanto do
  desenvolvimento quanto da entrega;
- pasta digital flexível: somente o nome é obrigatório na criação do cliente;
  os demais dados e documentos são opcionais.

O limite máximo de PDF/JPEG, o remetente/provedor de e-mail e a proteção do
backup continuam pendentes. Não invente esses valores.

## Decisões novas do Caio

Na PR #48, Caio confirmou a direção técnica:

- Tauri 2 direto como shell;
- React existente dentro da janela;
- FastAPI empacotada como sidecar;
- SQLite em arquivo;
- Tauri limitado a janela, supervisão do sidecar e integrações nativas
  indispensáveis;
- regras, autenticação, auditoria e dados continuam no FastAPI;
- instalação manual simples, sem launcher ou atualizador próprios;
- não haverá especialista Rust fixo, mas toda alteração em Tauri/CI Windows terá
  autor responsável e revisão de pelo menos outro integrante.

## Estado das PRs

### PR #48 — ADR Windows

- branch: `chore/43-arquitetura-windows`, head atual `437c352`;
- base: `develop`;
- estado atual: `CONFLICTING` e `CHANGES_REQUESTED`, porque `develop` avançou;
- Caio considerou os bloqueios anteriores atendidos e pediu a sincronização com
  a ADR 0003/#54, a confirmação de Tauri e a atualização dos gates;
- próximo passo: rebasear sobre `origin/develop`, corrigir somente a documentação
  solicitada, executar os checks, fazer push com `--force-with-lease` e pedir
  nova revisão;
- **não fazer merge sem autorização nova e explícita de Thiago**.

### PR #49 — spike Windows

- branch: `chore/43-windows-spike`, head `5539583`;
- continua isolada e não será integrada em `develop`;
- não rebasear, não retargetar, não resolver conflitos e não reutilizar seus
  lockfiles;
- após o aceite da ADR, deve ser fechada sem merge; preservar somente evidência
  sanitizada que o time julgar útil.

### PR #55 — decisão SQLite

- foi integrada em `develop` como `2384618`;
- fechou a issue #14 e aceitou a ADR 0003;
- a implementação ficou na issue #54, que está aberta e `status: ready`.

## Trabalho de código que pode começar

A issue **#54 — Portar a persistência para SQLite local** é o próximo recorte
seguro e deve nascer de `origin/develop`, nunca da PR #49. Ela cobre:

- driver SQLite assíncrono e configuração de banco em arquivo;
- models e migrations portáveis;
- concorrência segura na criação do primeiro proprietário;
- `foreign_keys`, WAL, timeout de lock e `synchronous=FULL`;
- migrations, autenticação e auditoria com fechamento/reabertura;
- `integrity_check`, `foreign_key_check`, comandos locais e CI sem Docker.

Depois da #54 revisada, seguir #18 e #19 para modelo/API/telas da pasta flexível
de cliente. Documentos (#21/#22/#23), importação (#45) e ficha PDF (#34) vêm
depois; upload não pode ser liberado antes da definição do limite máximo.

## Ordem recomendada

1. Atualizar a PR #48 conforme o último comentário do Caio e pedir revisão.
2. Em branch nova baseada em `origin/develop`, implementar a issue #54.
3. Após revisão da #54, implementar #18 e #19.
4. Tratar filesystem/documentos, checklist, importação e ficha PDF.
5. Implementar e-mail somente após #46; backup somente após as decisões da #44.
6. Encerrar com operação/LGPD e teste ponta a ponta #27.

Os passos 1 e 2 podem avançar em branches separadas, mas mudanças em arquivos
compartilhados devem ser coordenadas. Não faça merge automático.

## Comandos de retomada

```powershell
git fetch origin --prune
git status --short --branch
git worktree list
git log --oneline --decorate -8 origin/develop
gh pr view 48 --repo DELTA-42-FORCE/delta-force
gh pr view 49 --repo DELTA-42-FORCE/delta-force
gh issue view 54 --repo DELTA-42-FORCE/delta-force
gh issue list --repo DELTA-42-FORCE/delta-force --state open --limit 100
```

Para iniciar a #54, crie uma branch curta a partir de `origin/develop` e siga os
critérios da issue. Antes de revisão, execute `just check` e registre migrations,
testes, limitações e decisões pendentes.

O `package-lock.json` não rastreado na raiz do checkout de Thiago é alheio ao
projeto: não adicionar, remover ou sobrescrever.

# Vergueiro — comece por aqui

Estado confirmado em **22 de agosto de 2026**. Leia primeiro `AGENTS.md` e
`handoff/PROJECT_CONTINUATION.md`. Não faça merge automático e use somente dados
sintéticos.

## O que já está em `develop`

`origin/develop` está em `c111f0c` e já contém:

- PR #41: setup/login/logout e autenticação segura do proprietário;
- PR #50: interface responsiva de primeiro acesso, login e painel;
- PR #51: auditoria append-only e consulta autenticada;
- PR #52: atividade recente, histórico, paginação e filtros da auditoria;
- PR #53: proposta/questionário para homologar o catálogo cadastral.

Essas entregas são código real do produto, não apenas mockup. A API possui 98
testes unitários/não integração e a web possui 23 testes Vitest no estado atual.

## PRs abertas

### PR #48 — arquitetura Windows

- branch: `chore/43-arquitetura-windows`;
- head esperado: `7f7d6a9`;
- base: `develop`;
- estado: mergeável e cinco checks verdes;
- revisão: nova revisão pedida a `CaioSTAM`; o GitHub ainda mostra
  `CHANGES_REQUESTED` da revisão anterior;
- regra: **não fazer merge sem autorização explícita de Thiago**.

A ADR 0002 continua **Proposta**. A revisão retirou Windows 11 Pro/BitLocker e
recovery code dos fatos do cliente, reduziu o MVP para Tauri direto + sidecar e
removeu launcher, updater, manifesto e gerações próprios. Também registra que:

- não existe banco PostgreSQL do cliente a converter;
- a primeira instalação deverá nascer em SQLite vazio;
- a migration `0003` falha hoje no SQLite sem batch/copy-and-move;
- PostgreSQL e SQLite precisam de uma matriz real de integração durante a
  transição;
- assinatura, proteção do disco, WebView2 e proteção/recuperação do backup ainda
  são decisões/gates futuros.

### PR #49 — spike Windows

- branch: `chore/43-windows-spike`, head `5539583`;
- base: PR #48;
- estado: `CONFLICTING` e `CHANGES_REQUESTED`, sem CI;
- regra: manter isolada; **não rebasear para `develop`, não retargetar e não
  resolver o conflito agora**.

Depois que a ADR for aceita, o time decidirá se preserva apenas relatório/digest
na issue #43, move o experimento para outro repositório ou abre um recorte mínimo
novo. Não reutilize os quase 10 mil linhas e lockfiles da #49 como produto.

## O que bloqueia novo código do MVP

- **#14 / #18–#23 / #34 / #45:** o catálogo de campos, obrigatoriedade, tipos de
  documento e tamanho máximo ainda precisa ser respondido/homologado pelo
  cliente. “Mesmos dados do gov.br” não é schema suficiente.
- **#43 / #44:** a ADR Windows ainda aguarda revisão; backup depende também de
  decisão de proteção/recuperação e revisão criptográfica.
- **#46 / #24–#25:** o cliente ainda não informou e-mail/provedor remetente.

Não invente essas regras para começar telas ou migrations. O próximo módulo
funcional seguro é #18 somente depois da homologação completa da #14.

## Próximos passos seguros

1. Conferir se Caio respondeu na PR #48; corrigir somente novos achados
   verificáveis e nunca alterar o status da ADR por conta própria.
2. Se a PR #48 for aprovada, avisar Thiago. Não fazer merge sem nova autorização.
3. Depois do merge autorizado da #48, criar/vincular uma issue pequena para o
   adapter SQLite, migrations portáveis e shell mínimo; a PR deve nascer de
   `develop`, não da spike #49.
4. Obter do cliente as respostas de
   `docs/QUESTIONARIO_CATALOGO_CLIENTE.md` e o remetente/provedor de e-mail.
5. Homologar #14 antes de implementar #18; em seguida seguir #19 e #20.
6. Reescrever a proposta de backup #44 depois da decisão Windows; a branch antiga
   contém hipóteses que a revisão da #48 devolveu para decisão pendente.

## Comandos para recuperar o estado

```powershell
git fetch origin --prune
git status --short --branch
git worktree list
git log --oneline --decorate -8 origin/develop
gh pr view 48 --repo DELTA-42-FORCE/delta-force
gh pr checks 48 --repo DELTA-42-FORCE/delta-force
gh pr view 49 --repo DELTA-42-FORCE/delta-force
gh issue view 14 --repo DELTA-42-FORCE/delta-force
gh issue view 43 --repo DELTA-42-FORCE/delta-force
gh issue view 46 --repo DELTA-42-FORCE/delta-force
```

O `package-lock.json` não rastreado na raiz do checkout de Thiago é alheio ao
projeto: não adicionar, remover ou sobrescrever. Antes de parar, registre branch,
commit, testes, bloqueios e próximo comando neste handoff.

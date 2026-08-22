# Vergueiro — comece por aqui

Este guia registra o ponto exato deixado por Thiago/Codex em **22 de agosto de
2026**. A fonte completa é `handoff/PROJECT_CONTINUATION.md`. Não faça merge
automático e nunca use dados reais de cliente nos ambientes de desenvolvimento,
testes, prints, commits ou PRs.

## O que já foi desenvolvido

- autenticação segura do proprietário no backend: PR #41;
- primeira interface visível de setup/login/painel/logout: PR #50;
- auditoria append-only, migration e consulta autenticada: PR #51;
- painel “Atividade recente” ligado à auditoria real: branch
  `feature/17-auditoria-web`, commit `4ba1e54`, ainda sem PR;
- spike do aplicativo local Windows: PR #49 sobre a ADR da PR #48;
- propostas/questionários separados para catálogo, remetente e backup.

Você (`SecVergueiro`) está solicitado como revisor nas PRs #49, #50 e #51. Caio
continua solicitado nas PRs #41 e #48 porque há revisão anterior ou decisão
arquitetural pendente.

## Ver a entrega mais nova

```powershell
git fetch origin --prune
git switch feature/17-auditoria-web
git pull --rebase
Set-Location apps/web
npm ci
npm test -- --run
npm run lint
npm run typecheck
npm run build
```

O commit esperado é `4ba1e54`. Foram obtidos 16 testes Vitest verdes, ESLint,
TypeScript, build Vite e validação visual mobile/desktop. O endpoint usado é
`GET /audit/events?limit=5`; o bearer fica somente em memória, e IDs/contextos
internos são descartados antes de entrar no estado da interface.

## Ordem segura de integração

1. Revisar #41 e resolver a revisão antiga; integrar somente com aprovação.
2. Rebasear/retargetar #50 e #51 para `develop`, repetir gates e aguardar CI.
3. Integrar #50 e #51 com revisão humana.
4. Somente depois, limpar a pilha da interface de auditoria:

```powershell
git fetch origin --prune
git switch feature/17-auditoria-web
git branch backup/17-auditoria-web-before-rebase
git rebase --onto origin/develop b883852
just web-check
git push --force-with-lease
```

O hash `b883852` é o cherry-pick temporário da interface #15. O comando acima
deve ser executado apenas quando #50 e #51 já estiverem em `develop`; ele mantém
somente a mudança própria `4ba1e54`. Depois disso, revisar o diff contra
`origin/develop` e abrir uma PR pequena. Se a história remota tiver mudado, não
rode o rebase por hipótese: inspecione `git log --graph` e ajuste o plano.

## O que ainda bloqueia novos módulos

- clientes/documentos/PDF: falta homologar o catálogo explícito de campos,
  obrigatoriedade e tamanho máximo; “os mesmos dados do gov.br” não é schema;
- Windows/SQLite: a ADR #43 continua proposta e requer aprovação técnica;
- backup em HD: depende da ADR Windows, respostas de recuperação/criptografia e
  revisão criptográfica;
- mala direta: falta o provedor/remetente que o cliente disse que enviaria.

Não invente essas decisões para acelerar. Enquanto aguardam resposta, o trabalho
útil é revisar as PRs abertas, limpar as pilhas após os merges e confirmar os
gates. O `package-lock.json` não rastreado na raiz do checkout do Thiago é alheio
ao projeto e não deve ser adicionado.

## Comandos para recuperar o contexto

```powershell
git fetch origin --prune
git status --short --branch
git worktree list
gh pr view 41 --repo DELTA-42-FORCE/delta-force
gh pr view 48 --repo DELTA-42-FORCE/delta-force
gh pr view 49 --repo DELTA-42-FORCE/delta-force
gh pr view 50 --repo DELTA-42-FORCE/delta-force
gh pr view 51 --repo DELTA-42-FORCE/delta-force
```

Antes de qualquer alteração, leia `AGENTS.md`, a issue e os documentos citados
nele. Preserve mudanças de Caio/Thiago/Vergueiro e registre no handoff o commit,
os testes executados e qualquer decisão ainda pendente.

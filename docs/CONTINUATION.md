# Continuação do projeto

Este arquivo permite retomar o trabalho sem depender do histórico de uma
conversa. Antes de agir, leia `AGENTS.md` e confirme o estado atual no GitHub;
os dados abaixo são um retrato de **14 de setembro de 2026**.

## Estado confirmado

- `origin/develop` estava em `9be8cb2`, após o merge da PR #79.
- Acesso local, clientes, documentos PDF/JPEG, status documental, ficha PDF,
  importação assistida, auditoria, modelos de mensagem e triagem estão
  integrados.
- O envio real de e-mail, backup/restauração e aceite final do instalador ainda
  não estão concluídos.
- Use somente dados sintéticos. Não copie banco, documento, senha, token ou
  `.env` de cliente para branch, PR, issue ou log.

## Pull requests em revisão

1. **#80 — E2E da preparação de comunicação** (`e10a5de`): classifica o
   documento, cria modelo, consulta a triagem e verifica auditoria. O envio
   continua explicitamente ignorado por depender de #25/#46.
2. **#81 — texto de progresso do painel** (`218998e`): remove a orientação
   antiga que apresentava clientes como etapa futura e mantém o bloqueio do
   remetente visível.

Ambas foram abertas pela conta `ThiagoCarvlh`, portanto precisam da aprovação
de outra pessoa. Não use aprovação própria nem bypass administrativo. Depois do
primeiro merge, atualize a outra branch sobre `develop`, aguarde todos os checks
novamente e só então faça squash merge.

```powershell
git fetch origin --prune
gh pr list --state open --json number,title,reviewDecision,mergeStateStatus,statusCheckRollup
gh pr view 80 --json latestReviews,reviewDecision,mergeStateStatus,statusCheckRollup
gh pr view 81 --json latestReviews,reviewDecision,mergeStateStatus,statusCheckRollup
gh pr checks 80 --watch
gh pr checks 81 --watch
```

Quando a PR estiver aprovada, atualizada e com todos os checks verdes:

```powershell
gh pr merge 80 --squash
git fetch origin --prune
gh pr update-branch 81 --rebase
```

O número acima é somente a ordem sugerida. Se #81 for integrada primeiro,
atualize #80 da mesma forma. Nunca execute o merge enquanto houver
`CHANGES_REQUESTED`, check pendente/falho ou estado `BEHIND`.

## Bloqueios que não devem ser inventados

- **#24:** faltam homologar variáveis de modelo e onde cadastrar/validar o
  e-mail opcional do cliente.
- **#46:** o cliente ainda precisa informar remetente, provedor SMTP/API,
  autenticação, limites de envio e regra de falha/reenvio. Isso bloqueia #25.
- **#44:** o HD externo foi confirmado, mas a estratégia de senha/chave de
  criptografia ainda precisa de aprovação. Não implemente backup desprotegido.
- **ADR 0002/#43:** a issue #43 foi fechada como concluída, porém
  `docs/adr/0002-aplicativo-local-windows.md`, `docs/ARCHITECTURE.md` e
  `docs/CLIENT_DECISIONS.md` ainda registram a ADR como **Proposta**. O time deve
  reconciliar essa divergência antes de tratar a arquitetura como aceita.
- **#26:** depende da decisão arquitetural reconciliada e da entrega #44.
- **#27:** permanece aberta até envio/histórico, backup/restauração e aceite em
  instalação Windows limpa.

## Próxima sequência segura

1. Obter revisão e integrar #80/#81.
2. Confirmar com o time o status real da ADR 0002.
3. Obter do cliente/time as decisões de #44 e #46.
4. Implementar #25 somente após #46; implementar #44 somente após a decisão de
   criptografia e a reconciliação da ADR.
5. Completar #26 e executar o aceite final de #27 em Windows limpo.

Para qualquer nova entrega, crie worktree/branch curta a partir de
`origin/develop`, rode `just check`, abra PR para `develop` e solicite revisão:

```powershell
git fetch origin --prune
git worktree add -b feature/ISSUE-resumo storage/worktrees/ISSUE-resumo origin/develop
Set-Location storage/worktrees/ISSUE-resumo
just install
just check
```

Não altere nem apague arquivos não rastreados da worktree principal: eles podem
pertencer ao desenvolvedor local.

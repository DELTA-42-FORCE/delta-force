# Continuação do projeto

Este arquivo permite retomar o trabalho sem depender do histórico de uma
conversa. Antes de agir, leia `AGENTS.md`, execute `git fetch origin --prune` e
confirme no GitHub os heads, as revisões e os checks. Retrato atualizado em
**21 de setembro de 2026**; os hashes abaixo são referências históricas, não
substituem essa conferência.

## Estado integrado em develop

- Último `origin/develop` conferido: `625b608`.
- #94 (ADR 0004 de backup), #95 (ADR 0005 de e-mail), #96 (contratos e
  parcelamento), #97 (e-mail opcional, prévia e `{{nome}}`), #101 (`just audit`
  multiplataforma) e #102 (decisões técnicas) estão integradas.
- Autenticação local, clientes, documentos PDF/JPEG, status, importação,
  ficha PDF, auditoria e modelos de mensagem também estão integrados.
- Use somente dados sintéticos. Nunca publique dados de cliente, documento,
  banco, senha, token, credencial SMTP ou `.env` real.

## Pull requests e dependências

### #105 → #103 — envio e histórico de e-mail

- [#103](https://github.com/DELTA-42-FORCE/delta-force/pull/103): branch
  `codex/25-email-sending-history`, base `develop`, head conferido `ece6410`.
  Os sete checks desse head estavam verdes, mas a revisão ainda solicitava
  alterações. Não aprovar o head atual sem tratar os bloqueios.
- [#105](https://github.com/DELTA-42-FORCE/delta-force/pull/105): branch
  `fix/103-final-state-machine`, base empilhada #103, head publicado `adc96d9`.
  Corrige dois bloqueios P1 restantes da revisão: reserva transacional das
  tentativas de envio e conciliação de tentativas pendentes após interrupção.
  `just check` local passou (325 testes API, 48 integrações SQLite e 138 web).
  Na última consulta, o GitHub mostrava workflow concluído sem jobs para o
  branch empilhado; executar CI efetivo no head integrado.
- A [#104](https://github.com/DELTA-42-FORCE/delta-force/pull/104) foi fechada
  como substituída; suas correções foram incorporadas à #103. Não tentar
  integrá-la novamente.
- A #105 precisa de revisão. Depois de integrá-la à branch #103, revalidar a
  #103 no novo head e resolver somente as discussões efetivamente atendidas.

### #99 — backup cifrado e restauração

- [#99](https://github.com/DELTA-42-FORCE/delta-force/pull/99): branch
  `codex/44-encrypted-backup-restore`, base empilhada #103, head publicado
  `98143f2`. Ainda depende da integração/revisão da cadeia de e-mail.
- Implementa backup AES-256-GCM versionado, senha efêmera, validação de mídia
  externa por handles, snapshot consistente, geração completa com ponteiro e
  journal, restauração em instalação vazia e substituição de dados existentes
  com autenticação e confirmação `SUBSTITUIR DADOS`. A migration do backup é
  `20260920_0017`.
- Evidência local no head publicado: `just check` (353 testes API, 46
  integrações SQLite e 141 web), `just desktop-test` (10 Python e 8 Rust) e
  `just audit` sem vulnerabilidade bloqueante. Essa evidência não é aceite
  físico nem substitui CI/revisão do futuro head rebaseado.
- Após integrar #103 em `develop`, rebasear #99, preservar migrations e
  vínculos de retry/auditoria, repetir os gates e obter nova aprovação.

### #100 — operação, LGPD e aceite Windows

- [#100](https://github.com/DELTA-42-FORCE/delta-force/pull/100): branch
  `codex/26-operations-lgpd`, base empilhada #99. Contém
  `docs/OPERATION_MANUAL.md`, `docs/WINDOWS_ACCEPTANCE_CHECKLIST.md` e este
  guia. A branch foi rebaseada sobre `98143f2` para alinhar os textos à ADR
  0004; confira o head publicado depois desta atualização.
- Caio solicitou separar fatos confirmados, recursos ainda em PR e aceite
  físico. O manual é orientação preliminar, não comprovação de entrega nem
  parecer jurídico. A PR precisa de nova revisão depois da atualização.
- O smoke antigo do instalador é evidência histórica. O aceite #27 requer
  build final em Windows limpo, HD externo real, SMTP de teste autorizado e
  registro da origem/hash/assinatura do instalador.

## Sequência segura

1. Revisar #105 e integrá-la somente na branch da #103 após aprovação.
2. Rodar os checks efetivos e revisar #103 no novo head; integrar em `develop`
   somente após aprovação.
3. Rebasear #99 no novo `origin/develop`, repetir `just check`,
   `just desktop-test` e `just audit`, obter nova aprovação e integrar.
4. Rebasear #100 na base final, revisar manual/checklist e executar o aceite
   físico #27 no build do commit candidato.
5. Manter #25, #44, #26 e #27 abertas até seus respectivos gates reais.

Não usar merge automático. Em rebase já publicado, usar somente
`git push --force-with-lease`, depois de conferir que o remoto não avançou.

## Gates externos e operacionais

- Falta a conta/provedor real para testar SMTP. Credenciais nunca entram no
  repositório nem no GitHub.
- Custódia da senha do backup, pessoa autorizada a restaurar, frequência e
  retenção no HD, proteção do equipamento e recuperação da conta exigem
  definição/validação no aceite; não inventar dados pessoais ou política.
- O aceite final exige Windows limpo, HD externo de teste, conta SMTP e
  destinatário sintéticos/autorizados, origem/hash do instalador e decisão
  sobre assinatura/distribuição.
- Exclusão integral auditada de cliente não existe nesta versão. Não apagar
  dados manualmente; solicitação real de titular exige triagem e procedimento
  aprovado pelo responsável pelo tratamento.

## Ambiente local

Worktree para #99/#100:

    C:\Users\thiag\.codex\worktrees\mvp-finalization\delta-force

Worktree para #105:

    C:\Users\thiag\.codex\worktrees\email-reliability\delta-force

A worktree principal contém um `package-lock.json` não rastreado que pode
pertencer ao desenvolvedor. Não o alterar nem apagar.

Antes de qualquer aprovação/merge:

    git fetch origin --prune
    gh pr view NUMERO --repo DELTA-42-FORCE/delta-force --json headRefOid,baseRefName,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup
    just check

Se `gh` falhar por autenticação expirada, consultar o GitHub na sessão
autorizada do proprietário; não trocar para a conta de outro colaborador.
Confirme que revisão e checks pertencem ao head atual. Para o instalador, o
job **Desktop Windows — sidecar and installer** é obrigatório.

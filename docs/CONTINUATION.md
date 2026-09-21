# Continuação do projeto

Este arquivo permite retomar o trabalho sem depender do histórico de uma
conversa. Antes de agir, leia AGENTS.md, execute git fetch origin --prune e
confirme o estado no GitHub. Este retrato foi atualizado em **20 de setembro de
2026**, após o rebase e a correção de segurança da PR #99.

## Estado integrado em develop

- origin/develop está em 625b608.
- **#94:** ADR 0004 de backup/restauração aceita.
- **#95:** ADR 0005 de envio seguro e credencial efêmera aceita.
- **#96:** contratos e parcelamento integrados; migrations agora seguem uma
  única cadeia.
- **#97:** e-mail opcional do cliente, prévia e variável {{nome}} integrados.
- **#101:** just audit funciona em Linux e PowerShell.
- **#102:** decisões técnicas do time para e-mail e backup registradas.
- Autenticação local, clientes, documentos PDF/JPEG, status, importação,
  ficha PDF, auditoria, modelos de mensagem e contratos também estão integrados.
- Use somente dados sintéticos. Nunca copie banco, documento, senha, token,
  credencial SMTP ou .env real para branch, PR, issue, teste ou log.

## Pull requests abertas

### #103 — envio e histórico de e-mail

- URL: https://github.com/DELTA-42-FORCE/delta-force/pull/103
- Branch: codex/25-email-sending-history; base: develop.
- Head conferido: aacb4d5.
- Os sete checks do GitHub estão verdes, mas a revisão continua em
  **changes requested**.
- Não aprovar enquanto o head não corrigir:
  1. entrega SENT nunca pode ser repetida;
  2. credencial SMTP não pode usar/autosalvar a senha do CRM;
  3. falhas inequivocamente anteriores a DATA não podem virar UNKNOWN;
  4. repetição de UNKNOWN precisa referenciar tentativa e Message-ID prévios;
  5. auditoria do lote precisa começar antes do primeiro efeito e concluir/falhar
     com contagens;
  6. constraints ORM precisam permanecer em paridade com o catálogo migrado.

### #99 — backup cifrado e restauração

- URL: https://github.com/DELTA-42-FORCE/delta-force/pull/99
- Branch: codex/44-encrypted-backup-restore; base empilhada: #103.
- Head publicado: adc265d; estado atual da cadeia: mergeável, aguardando
  nova revisão.
- O rebase preservou contratos/e-mail e renumerou o backup para
  20260920_0017.
- Os três bloqueios anteriores foram corrigidos: junction/reparse point,
  UNC/dispositivo antes de I/O e compensação do arquivo quando auditoria/commit
  falham.
- Evidência do novo head: just check com 340 testes unitários, 46 integrações
  SQLite e 139 testes web; just desktop-test com 10 testes Python e 8 Rust;
  just audit sem vulnerabilidade bloqueante.
- A PR entrega restauração em instalação vazia. A substituição autenticada de
  dados existentes prevista na ADR 0004 ainda não foi implementada; por isso a
  PR referencia #44, mas não deve fechá-la.
- Depois do merge de #103, rebasear #99 sobre origin/develop, repetir todos os
  gates e obter nova aprovação do head resultante.

### #100 — operação, LGPD e aceite Windows

- URL: https://github.com/DELTA-42-FORCE/delta-force/pull/100
- Branch: codex/26-operations-lgpd; base empilhada: #99.
- Contém docs/OPERATION_MANUAL.md e docs/WINDOWS_ACCEPTANCE_CHECKLIST.md.
- Esta branch foi rebaseada localmente sobre adc265d; confirme o head publicado
  e os checks antes de revisar.
- O smoke antigo do instalador é evidência histórica, não substitui o aceite do
  build final numa máquina Windows limpa, HD externo real e SMTP autorizado.

## Sequência segura

1. Caio/Vergueiro corrigem a #103; revisar o novo head e somente então aprovar.
2. Integrar #103 em develop após aprovação e checks do mesmo commit.
3. Rebasear #99 sobre o novo origin/develop, rodar just check,
   just desktop-test e just audit, então obter nova aprovação.
4. Implementar em PR separada a restauração autenticada sobre dados existentes,
   com confirmação reforçada, geração anterior recuperável e testes de queda.
5. Rebasear #100 sobre a base final, revisar manual/checklist e executar o aceite
   #27 com build do commit candidato.
6. Manter #25, #44, #26 e #27 abertas até seus respectivos gates reais.

Nunca use merge automático. Em rebase já publicado, use somente
git push --force-with-lease.

## Gates externos e operacionais

- O cliente ainda precisa fornecer o remetente/provedor real para o teste SMTP.
  Não registrar a credencial no repositório nem no GitHub.
- Custódia da senha do backup, pessoa autorizada a restaurar, frequência,
  retenção no HD, BitLocker/proteção do equipamento e recuperação da conta devem
  ser registrados no aceite/manual sem inventar dados pessoais.
- O aceite final exige Windows limpo, HD externo de teste, conta SMTP e
  destinatário sintéticos/autorizados, origem/hash do instalador e decisão sobre
  assinatura/distribuição.
- A exclusão integral auditada de cliente não existe nesta versão. Não apagar
  dados manualmente; uma solicitação real de titular exige triagem e procedimento
  aprovado.

## Ambiente local e continuidade

A worktree usada para as PRs #99/#100 é:

    C:\Users\thiag\.codex\worktrees\mvp-finalization\delta-force

A worktree principal contém um package-lock.json não rastreado que pode
pertencer ao desenvolvedor. Não alterar nem apagar esse arquivo.

Antes de qualquer aprovação ou merge:

    git fetch origin --prune
    gh pr view NUMERO --repo DELTA-42-FORCE/delta-force --json headRefOid,baseRefName,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup
    just check

Confirme que o head não mudou desde a revisão e que todos os checks pertencem ao
mesmo commit. Para desktop/instalador, o job
**Desktop Windows — sidecar and installer** é obrigatório.

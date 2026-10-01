# Continuação do projeto

Este arquivo é um retrato de **30 de setembro de 2026**. Ele ajuda a retomar o
trabalho, mas não substitui a checagem dos estados atuais no GitHub. Leia
`AGENTS.md`, a issue escolhida e `skills/delta-force-development/SKILL.md` antes
de iniciar uma tarefa.

## Estado confirmado

- O produto continua sendo um aplicativo local Windows, para um único
  proprietário, com SQLite local e documentos em filesystem privado.
- O fluxo de trabalho normal não usa PR para `develop`: reivindique a issue no
  Project, crie branch curta de `origin/develop`, faça preflight, rode
  `just check`, publique para CI e integre o mesmo commit por fast-forward após
  todos os checks obrigatórios passarem. Se `develop` avançar depois da
  publicação, crie uma branch nova da ponta atual e reaplique os commits; não
  reescreva a branch publicada nem use force push. PR continua obrigatória para
  integrar em `main`.
- `#110` (validação da restauração em staging) foi integrada diretamente em
  `develop` no commit `b351d9b` depois de `just check` e dos sete checks remotos,
  incluindo build e smoke test Windows. A antiga PR #116 foi fechada sem merge.
- A PR #113 foi fechada após seu conteúdo documental ainda válido ser
  sincronizado com a base atual; as instruções antigas de PR para `develop` e
  os retratos de estado desatualizados não foram reaplicados.
- Não use dados reais do cliente, senhas, tokens ou `.env` em testes, issues,
  branches ou logs.

## Backup e restauração

- A ADR 0004 define o contêiner criptográfico DFCRMBK1 v1, scrypt e AES-256-GCM.
- #106 (codec), #108 (snapshot consistente) e #110 (validação isolada) estão
  concluídas.
- #109 está concluída: publicação segura em mídia externa Windows, incluindo
  verificação pelo handle do arquivo publicado (`34798cc`).
- #111 está concluída: ativação com journal durável e rollback (`51b6aa2`).
- #112 implementa rotas autenticadas, tela de cópia/revisão/confirmação e
  lembrete opcional. Contrato e operação em `docs/BACKUP_FLOW.md`; a integração
  exige CI verde, incluindo os testes do fluxo, build e smoke Windows. Confira
  na issue o SHA e o resultado atuais antes de retomar trabalho.
- #44 é a issue guarda-chuva e permanece **In progress** até concluir as
  entregas técnicas e os gates operacionais de #26/#27.
- Custódia/recuperação da senha, frequência/retenção do HD, proteção do
  equipamento e recuperação de conta são decisões operacionais pendentes para
  o manual e o aceite; não invente respostas nem bloqueie o código já definido.

## E-mail e aceite

- #24 está integrada. A fundação de envio/histórico da #25 existe, mas o envio
  real continua dependente dos dados públicos de remetente/provedor/volume da
  #46; nunca registre credenciais.
- #46 está **Blocked** até resposta do cliente.
- #26 (manual, operação e resposta a incidentes) e #27 (aceite ponta a ponta em
  Windows limpo e HD de teste) continuam **Blocked** pelos gates externos e pela
  conclusão do backup. Use dados sintéticos e mídia de teste.

## Próxima sequência

1. Conferir a conclusão dos checks e integração de #112, sem contornar gates.
2. Revisar o fluxo em `docs/BACKUP_FLOW.md` e preparar o manual operacional.
3. Atualizar #26 e executar #27 em Windows limpo; então concluir a guarda-chuva
   #44.
4. Retomar o envio real somente quando o cliente fornecer os dados não secretos
   da #46 e o adaptador puder ser configurado com credencial protegida.

## Checklist rápido antes de qualquer integração

```bash
git fetch origin
git switch -c feature/ISSUE-resumo origin/develop
just check
git push -u origin HEAD
```

Antes de publicar a branch, sincronize-a com `origin/develop` por rebase. Depois
de publicada, não reescreva seu histórico: se a base avançar, use uma branch
nova e reaplique os commits. Integre somente quando o SHA testado for exatamente
o SHA publicado e todos os checks obrigatórios estiverem verdes. Atualize o
Project e feche a issue apenas após a integração e o aceite.

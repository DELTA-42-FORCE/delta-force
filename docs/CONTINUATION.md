# Continuação do projeto

Este arquivo permite retomar o trabalho sem depender do histórico de uma
conversa. Antes de agir, leia `AGENTS.md`, execute `git fetch origin --prune` e
confirme PRs, revisões e checks no GitHub. Este retrato é de **19 de setembro de
2026** e não autoriza merge automático.

## Estado do MVP

- `origin/develop` estava em `923a6aa` antes das entregas empilhadas abaixo.
- Autenticação do proprietário, clientes, documentos PDF/JPEG, status manual,
  importação assistida, ficha PDF, auditoria, modelos e triagem já estavam em
  `develop`.
- A PR **#97**, branch `codex/24-email-client-template-vars`, adiciona e-mail
  opcional validado ao cliente, variável única `{{nome}}`, prévia autenticada e
  testes. Ela depende de revisão; não foi mesclada por este agente.
- A PR **#96** de contratos também nasceu do mesmo `develop` e usa o identificador
  de migration `20260919_0014`. Se ela for integrada primeiro, a #97 precisa ser
  rebaseada e suas migrations `0014`/`0015` renumeradas; se a #97 entrar primeiro,
  a #96 é que precisa ser rebaseada e renumerada. Nunca mantenha dois heads com o
  mesmo identificador.
- A branch `codex/25-email-sending-history` parte da #97 e acrescenta SMTP
  configurável, credencial efêmera, envio individual, proteção contra repetição,
  histórico, auditoria, interface e E2E sintético. Consulte no GitHub a PR dessa
  branch e seus checks antes de revisar ou continuar.
- Nenhuma senha, token ou dado real foi versionado. Os testes usam somente dados
  e transportes sintéticos; o envio real fica para aceite controlado.

## Decisões encerradas

- O proprietário preenche os dados públicos do remetente no aplicativo e
  informa a senha/senha de aplicativo a cada sessão de envio; ela nunca é
  persistida ou incluída no backup.
- O transporte do MVP é SMTP com TLS/STARTTLS. Sem TLS existe apenas para
  Mailpit em loopback, quando habilitado explicitamente no desenvolvimento.
- O envio é individual, com limite configurável de 1 a 100 (padrão 50), falha
  isolada e confirmação para repetir sucesso ou resultado desconhecido.
- Backup usa HD externo e senha digitada. O padrão técnico aprovado para o MVP é
  arquivo versionado criptografado, sem recuperação de senha pela equipe,
  lembrete após sete dias e restauração somente em instalação vazia.

Os detalhes e a separação entre resposta do cliente e decisão técnica delegada
estão em `docs/CLIENT_DECISIONS.md`.

## Próxima sequência segura

1. Revisar a PR da branch `codex/25-email-sending-history`, confirmar que a base
   é a branch da #97 enquanto ela não estiver integrada e rodar `just check`.
2. Após aprovação/merge da #97, atualizar a base da PR de envio para `develop`,
   resolver somente conflitos reais e repetir todos os checks.
3. Coordenar a ordem com a PR #96 e renumerar migrations na segunda PR antes do
   merge, preservando upgrade/downgrade e um único head Alembic.
4. Implementar **#44** em branch própria: ADR, backup criptografado consistente,
   validação completa e restauração atômica somente em instalação vazia.
5. Concluir **#26** com manual de operação, LGPD, incidente e procedimento de
   backup/restauração.
6. Executar **#27** em Windows limpo: instalar, criar conta, cadastrar cliente,
   anexar/abrir documento, gerar ficha, enviar e-mail de teste autorizado,
   criar backup, restaurar e verificar desinstalação/atualização manual.

## Alertas para quem continuar

- Não use conta SMTP, banco, documento ou destinatário real em teste, screenshot,
  issue, log ou PR.
- Não mescle PR sem revisão humana e checks verdes.
- Restauração é operação destrutiva: nunca aponte testes para o diretório real
  do aplicativo nem implemente substituição de instalação com dados no MVP.
- A senha do backup não pode ser armazenada, logada, recuperada pela equipe nem
  derivada da senha de login.
- O histórico de envio mantém a fotografia de assunto/corpo mesmo depois da
  exclusão de um modelo; por isso o identificador do modelo não bloqueia essa
  exclusão.
- `package-lock.json` não rastreado na worktree principal pertence ao ambiente
  do desenvolvedor e não deve ser apagado ou incluído sem investigação.

## Comandos de retomada

```powershell
git fetch origin --prune
git status --short --branch
gh pr list --state open --limit 30
just install
just check
```

Para nova entrega, use branch curta baseada na dependência correta. Enquanto as
PRs empilhadas não forem integradas, preserve explicitamente a ordem; depois,
rebaseie sobre `origin/develop` com `--force-with-lease`, nunca `--force`.

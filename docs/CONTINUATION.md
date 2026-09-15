# Continuação do projeto

Este arquivo permite retomar o trabalho sem depender do histórico de uma
conversa. Antes de agir, leia `AGENTS.md` e confirme o estado atual no GitHub;
os dados abaixo são um retrato de **14 de setembro de 2026, após a integração da
PR #87**.

## Estado confirmado

- `origin/develop` estava em `a972a38`, após o merge da PR #87.
- Acesso local, clientes, documentos PDF/JPEG, status documental, ficha PDF,
  importação assistida, auditoria, modelos de mensagem e triagem estão
  integrados.
- O E2E da preparação de comunicação, o texto de progresso do painel e a
  inicialização do SQLite no aplicativo Windows instalado também estão
  integrados.
- As GitHub Actions obrigatórias usam versões com runtime Node 24; o Node 22 da
  aplicação permanece inalterado.
- O envio real de e-mail, backup/restauração e o aceite completo do MVP em uma
  instalação Windows limpa ainda não estão concluídos. Confirme no GitHub as
  PRs abertas antes de iniciar ou integrar qualquer trabalho.
- Use somente dados sintéticos. Não copie banco, documento, senha, token ou
  `.env` de cliente para branch, PR, issue ou log.

## Últimas integrações

- **#79:** interface de modelos e triagem, sem envio real.
- **#80:** E2E da preparação de comunicação, cobrindo status documental,
  criação de modelo, triagem e auditoria.
- **#81:** texto de progresso do painel alinhado ao estado atual.
- **#82:** handoff inicial para continuidade do projeto.
- **#83:** inclusão do driver SQLite no sidecar instalado e smoke test cauteloso
  do instalador Windows.
- **#84:** consulta autenticada de modelo por ID e cobertura HTTP do ciclo CRUD.
- **#87:** atualização das GitHub Actions para runtime Node 24, preservando
  versões, caches, permissões e comandos da aplicação.

## Bloqueios que não devem ser inventados

- **#24:** CRUD, triagem e interface estão integrados; faltam homologar as
  variáveis de modelo e onde cadastrar/validar o e-mail opcional do cliente.
- **#46:** o cliente ainda precisa informar remetente, provedor SMTP/API,
  autenticação, limites de envio e regra de falha/reenvio. Isso bloqueia #25.
- **#44:** o HD externo e o uso de senha digitada pelo proprietário foram
  confirmados; formato criptográfico, custódia e recuperação da senha ainda
  precisam ser definidos. Não implemente backup desprotegido.
- **ADR 0002/#43:** a arquitetura está **Aceita** e a issue #43 está concluída.
  A PR #48 aprovou Tauri 2, React, FastAPI empacotada como sidecar e
  SQLite/filesystem privado; a integração essencial foi entregue pela #57.
  Permanecem pendentes somente os gates operacionais e de release registrados
  na própria ADR, como proteção do equipamento, assinatura e recuperação do
  backup.
- **#26:** depende das decisões operacionais restantes e da entrega #44.
- **#27:** permanece aberta até envio/histórico, backup/restauração e aceite em
  instalação Windows limpa.
- **#88:** está pronta para desenvolvimento e deve tornar falhas de inicialização
  do aplicativo Windows diagnosticáveis sem persistir segredos ou dados do
  cliente. As falhas intermitentes observadas nas PRs #85/#87 passaram no
  rerun, mas o código 101 isolado não informa sua causa.

## Próxima sequência segura

1. Implementar #88 e validar novamente o smoke test do instalador Windows.
2. Obter do cliente/time as decisões de #24, #44 e #46.
3. Implementar #25 somente após #46 e implementar #44 somente após definir o
   formato criptográfico e a recuperação da senha.
4. Completar #26 e executar o aceite final de #27 em Windows limpo.

### Informações necessárias para destravar #46

- endereço e nome de exibição do remetente;
- provedor já contratado ou disponível e se a integração será SMTP ou API;
- forma autorizada de armazenar a credencial fora do repositório e do backup;
- limite esperado de destinatários por lote;
- comportamento aprovado para falha parcial e reenvio.

Não registre senha, token ou segredo em issue, PR ou arquivo versionado.

### Informações necessárias para destravar #44

- decisão confirmada: o backup poderá usar senha digitada pelo proprietário;
- onde a senha ou chave de recuperação será guardada fora do computador e do HD
  de backup;
- quem poderá executar a restauração em um computador substituto;
- procedimento aceito para perda da senha/chave.

Não implemente um backup desprotegido nem uma chave vinculada somente ao
computador perdido: ambos contrariam a recuperação por HD externo.

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

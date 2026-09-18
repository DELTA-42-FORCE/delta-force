# Continuação do projeto

Este arquivo permite retomar o trabalho sem depender do histórico de uma
conversa. Antes de agir, leia `AGENTS.md` e confirme o estado atual no GitHub;
os dados abaixo são um retrato de **18 de setembro de 2026, após a abertura das
PRs #94 e #95**.

## Estado confirmado

- `origin/develop` estava em `923a6aa`, após o merge da PR #92.
- Acesso local, clientes, documentos PDF/JPEG, status documental, ficha PDF,
  importação assistida, auditoria, modelos de mensagem e triagem estão
  integrados.
- O E2E da preparação de comunicação, o texto de progresso do painel e a
  inicialização do SQLite no aplicativo Windows instalado também estão
  integrados.
- As GitHub Actions obrigatórias usam versões com runtime Node 24; o Node 22 da
  aplicação permanece inalterado.
- As falhas de inicialização do aplicativo instalado agora produzem diagnóstico
  sanitizado, e a PR #92 reforça upload/download de documentos, auditoria da
  importação, limites técnicos e auditoria de dependências.
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
- **#89:** diagnóstico sanitizado para falhas de inicialização do desktop
  empacotado; nenhum segredo, dado pessoal ou caminho privado é persistido.
- **#90:** registro das confirmações do cliente sobre parcelamento futuro, sem
  ampliar o MVP atual.
- **#91:** registro objetivo das perguntas que ainda bloqueiam e-mail (#46) e
  backup (#44).
- **#92:** reforço de documentos, importação, limites de campos, dependências e
  tolerância da primeira abertura no Windows; os sete checks passaram na revisão
  integrada, inclusive o smoke test do instalador.

## Bloqueios que não devem ser inventados

- **#24:** CRUD, triagem e interface estão integrados; faltam homologar as
  variáveis de modelo e onde cadastrar/validar o e-mail opcional do cliente.
- **#46:** o cliente ainda precisa informar remetente, provedor/conta e os
  mecanismos de envio autorizados pelo provedor, além do volume/frequência e da
  confirmação do fluxo individual com reenvio só das falhas. O time escolhe o
  adaptador e a guarda segura da credencial; isso não deve ser delegado ao
  cliente. A proposta técnica está na PR #95 e ainda aguarda revisão.
- **#44:** o HD externo e o uso de senha digitada pelo proprietário foram
  confirmados; ainda faltam decisões operacionais sobre custódia/recuperação da
  senha, responsáveis, frequência, retenção, modo de restauração e proteção dos
  equipamentos. O formato criptográfico, snapshot consistente e restauração
  atômica são decisões do time; a proposta técnica está na PR #94 e ainda
  aguarda revisão. Não implemente backup desprotegido.
- **ADR 0002/#43:** a arquitetura está **Aceita** e a issue #43 está concluída.
  A PR #48 aprovou Tauri 2, React, FastAPI empacotada como sidecar e
  SQLite/filesystem privado; a integração essencial foi entregue pela #57.
  Permanecem pendentes somente os gates operacionais e de release registrados
  na própria ADR, como proteção do equipamento, assinatura e recuperação do
  backup.
- **#26:** depende das decisões operacionais restantes e da entrega #44.
- **#27:** permanece aberta até envio/histórico, backup/restauração e aceite em
  instalação Windows limpa.
- As PRs #94 e #95 propõem as decisões técnicas de backup e e-mail. Não trate
  proposta como decisão aceita antes da revisão e do merge. Ainda não há issue
  MVP de implementação com `status: ready`; não retire `status: blocked` nem
  implemente baseado em hipótese.

## Próxima sequência segura

1. Revisar as propostas técnicas das PRs #94 e #95 sem antecipar o aceite.
2. Obter do cliente as decisões operacionais de #24, #44 e #46.
3. Implementar #25 somente após #46 e implementar #44 somente após as decisões
   técnica e operacional correspondentes serem aprovadas.
4. Completar #26 e executar o aceite final de #27 em Windows limpo.

### Informações necessárias para destravar #46

- endereço e nome de exibição do remetente;
- provedor/conta já utilizada e se oferece SMTP com senha de aplicativo ou outro
  mecanismo de envio autorizado;
- volume aproximado de destinatários por lote e frequência esperada;
- confirmação de envio individual, com registro das falhas e reenvio somente
  dos destinatários que falharam.

O time escolherá SMTP ou API conforme o provedor e definirá a guarda por Windows
Credential Manager/DPAPI ou entrada por sessão. Não registre senha, token ou
segredo em issue, PR, banco, backup ou arquivo versionado.

### Informações necessárias para destravar #44

- decisão confirmada: o backup poderá usar senha digitada pelo proprietário;
- onde a senha ou chave de recuperação será guardada fora do computador e do HD
  de backup;
- quem poderá executar a restauração em um computador substituto;
- procedimento aceito para perda da senha/chave;
- frequência do backup e necessidade de lembrete no aplicativo;
- quantidade de versões ou período de retenção no HD;
- uso da restauração apenas em instalação vazia ou também sobre dados existentes;
- proteção atual do Windows e do HD, como senha e BitLocker;
- forma esperada de recuperar a conta do CRM se a senha de login também for
  perdida após a troca do computador.

Não implemente um backup desprotegido nem uma chave vinculada somente ao
computador perdido: ambos contrariam a recuperação por HD externo. Formato
criptográfico, snapshot consistente e restauração atômica pertencem ao time e
não são perguntas para o cliente.

Para qualquer nova entrega, crie worktree/branch curta a partir de
`origin/develop`, rode `just check`, abra PR para `develop` e solicite revisão:

```powershell
git fetch origin --prune
git worktree add -b feature/ISSUE-resumo storage/worktrees/ISSUE-resumo origin/develop
Set-Location storage/worktrees/ISSUE-resumo
just install
just check
```

Antes de aprovar ou mesclar uma PR, confirme que ela continua baseada no
`origin/develop` atual, que o `headRefOid` não mudou desde a revisão e que todos
os checks obrigatórios pertencem a esse mesmo commit. Para mudanças no desktop,
o job **Desktop Windows — sidecar and installer** é obrigatório.

Não altere nem apague arquivos não rastreados da worktree principal: eles podem
pertencer ao desenvolvedor local.

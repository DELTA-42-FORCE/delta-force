# Continuação do projeto

Este arquivo permite retomar o trabalho sem depender do histórico de uma
conversa. Antes de agir, leia `AGENTS.md` e confirme o estado atual no GitHub;
os dados abaixo são um retrato de **25 de setembro de 2026, após as integrações
das PRs #103 e #114**.

## Estado confirmado

- `origin/develop` está em `cc9f1af`, após o merge da PR #114.
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
- A PR #103 integrou a fundação de envio/histórico; o envio real continua
  aguardando os dados do remetente/provedor (#46). A implementação de
  backup/restauração está decomposta nas issues #106 e #108–#112. O aceite
  completo em instalação Windows limpa continua pendente (#26/#27).
- A PR #114 implementou a #106 e foi aprovada, teve os sete checks concluídos
  com sucesso (incluindo o instalador Windows) e foi integrada em 25/09/2026.
  A PR #113 contém esta atualização documental e ainda precisa corrigir a
  inconsistência apontada na revisão antes de ser aprovada.
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
- **#94 e #95:** ADRs aceitas para o formato de backup cifrado (0004) e o
  adaptador/guarda de credenciais de e-mail (0005).
- **#96:** contratos e parcelamento da etapa posterior ao MVP, com valores em
  centavos, vencimentos civis, pagamentos, cancelamento, auditoria e interface.
- **#97:** conclusão do cadastro de e-mail opcional e renderização de modelos.
- **#101:** `just audit` portátil para Linux e PowerShell, executando todos os
  scanners obrigatórios e agregando falhas sem atualizar dependências.
- **#102:** decisões do time sobre envio individual, resultado SMTP desconhecido,
  lembrete de backup e restauração com proteção dos dados existentes.
- **#103:** envio individual, histórico auditável, proteção contra repetição e
  tratamento de resultado incerto; todos os sete checks passaram, incluindo
  integração SQLite e instalador Windows.
- **#114:** codec criptográfico DFCRMBK1 v1 implementado em streaming, conforme
  ADR 0004, com validação de quadros e escrita sem sobrescrever destino
  existente; revisão independente e sete checks aprovados antes do merge.

## Bloqueios que não devem ser inventados

- **#46:** o cliente ainda precisa informar remetente, provedor/conta e os
  mecanismos de autenticação permitidos e volume esperado. A ADR 0005 e a PR
  #103 já definiram e integraram a arquitetura de envio seguro; não enviar
  mensagens reais antes da configuração autorizada.
- **#44:** HD externo e senha digitada pelo proprietário foram confirmados. A
  ADR 0004 está aceita e definiu DFCRMBK1 v1, KDF, cifra, snapshot e restauração
  recuperável. A entrega foi dividida em #106 e #108–#112; detalhes operacionais
  pendentes para o manual/aceite em #26/#27 não bloqueiam iniciar #106.
- **ADR 0002/#43:** a arquitetura está **Aceita** e a issue #43 está concluída.
  A PR #48 aprovou Tauri 2, React, FastAPI empacotada como sidecar e
  SQLite/filesystem privado; a integração essencial foi entregue pela #57.
  Permanecem pendentes somente os gates operacionais e de release registrados
  na própria ADR, como proteção do equipamento, assinatura e recuperação do
  backup.
- **#26:** manual, operação local e resposta a incidentes; completar após a
  implementação de backup e as respostas operacionais restantes.
- **#27:** permanece aberta até envio/histórico, backup/restauração e aceite em
  instalação Windows limpa.
- **PRs #99 e #100:** fechadas sem merge; o código grande de backup não será
  integrado em bloco. #104/#105 foram fechadas após correções/reorganização da
  base da #103. Neste retrato, #113 permanece aberta aguardando correção e
  aprovação.
- Project: #44 em andamento, #106 concluída e #108–#112 bloqueadas até a
  integração do codec e a conclusão de suas dependências.
  Reconfirme o Project antes de alterar status.

## Próxima sequência segura

1. Desenvolver #108 e #110 em branches/PRs separadas, ambas a partir da
   `origin/develop` atualizada após o merge da #114.
2. Continuar #109 após #108 e #111 após #110.
3. Desenvolver #112 após #109 e #111, cobrindo o fluxo autenticado do aplicativo.
4. Obter os dados públicos do remetente na #46 antes de homologar o envio real
   da #25; não registrar credenciais em issues, PRs ou arquivos.
5. Atualizar o manual/operação em #26 e executar o aceite de ponta a ponta em
   Windows limpo e HD de teste pela #27.

### Informações necessárias para destravar #46

- endereço e nome de exibição do remetente;
- provedor/conta já utilizada e se oferece SMTP com senha de aplicativo ou outro
  mecanismo de envio autorizado;
- volume aproximado de destinatários por lote e frequência esperada;

O envio individual, o tratamento de falhas e a guarda segura da credencial já
foram decididos nas ADR 0005 e #102. O time escolherá SMTP ou API conforme os
mecanismos permitidos pelo provedor. Não registre senha, token ou segredo em
issue, PR, banco, backup ou arquivo versionado.

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
criptográfico, snapshot consistente e restauração atômica com rollback já estão
definidos na ADR 0004 e serão implementados em #106 e #108–#112. Essas respostas
operacionais calibram o manual e o aceite; não bloqueiam o codec.

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

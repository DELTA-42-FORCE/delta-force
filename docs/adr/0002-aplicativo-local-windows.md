# ADR 0002 — Shell, empacotamento e ciclo de vida do aplicativo local Windows

**Status:** Proposta

**Issue:** #43

**Data:** 22 de agosto de 2026 (última revisão em 26 de agosto de 2026)

**Decisor técnico:** Caio São Thiago — direção Tauri aprovada em comentário
técnico na PR #48 (26/08/2026), condicionada aos ajustes de sincronização
documental descritos abaixo antes da mudança formal de status para **Aceita**.

Esta ADR decide somente shell, empacotamento, primeira execução, atualização,
desinstalação e diretórios privados finais do aplicativo Windows. A
persistência de dados (SQLite em arquivo e filesystem privado) já foi decidida
pela [ADR 0003](0003-sqlite-como-persistencia-local.md) e pela issue #54; esta
ADR não repete nem reabre essa escolha. Enquanto permanecer como **Proposta**,
Tauri, Rust e PyInstaller não fazem parte do produto nem podem alterar seus
lockfiles. A PR #49 continua um experimento isolado e não deve ser integrada ou
usada como aprovação implícita da arquitetura.

## Evidências e classificação

### Fatos confirmados com o cliente

A issue #43 e `CLIENT_DECISIONS.md` confirmam somente que o CRM:

- será usado pelo proprietário em um computador Windows;
- deve abrir como aplicativo com ícone, sem exigir navegador aberto;
- manterá dados e documentos no próprio computador;
- fará backup e restauração por HD externo.

Esses fatos não definem edição do Windows, criptografia do disco, framework
desktop, banco de produção, instalador, assinatura ou credencial de recuperação.

### Critérios técnicos do projeto

São critérios de aceite e segurança, não respostas do cliente:

- a instalação não pode exigir que o proprietário administre Docker, Python,
  banco, serviço ou porta;
- a API e os documentos não podem ficar acessíveis pela rede local ou por URL
  pública permanente;
- autenticação, autorização, auditoria e proteção de dados sensíveis continuam
  obrigatórias no servidor;
- instalação, atualização e desinstalação não podem apagar dados silenciosamente;
- SQLite em arquivo e filesystem privado são a persistência-alvo definida pela
  ADR 0003; PostgreSQL e MinIO são apenas a fundação legada que a issue #54 está
  removendo, não a infraestrutura de desenvolvimento permanente.

### Hipóteses em avaliação

- Tauri direto, usando apenas seu shell e bundler padrão, pode reaproveitar a
  interface React com menos operação no computador do cliente;
- uma API FastAPI empacotada pode preservar as regras atuais sem exigir Python
  instalado, desde que lifecycle, isolamento e build sejam comprovados.

### Decisões técnicas e operacionais pendentes

- computador final, versão/edição/arquitetura do Windows e filesystem;
- proteção dos dados em repouso no equipamento final, inclusive se BitLocker,
  Device Encryption ou outra solução será exigida;
- responsável, orçamento, certificado e custódia para assinatura de releases;
- formato, criptografia, credencial e procedimento de recuperação do backup
  (#44);
- estratégia de distribuição do WebView2 no equipamento final.

Essas escolhas são gates futuros de implementação ou release. Não são fatos
confirmados pelo cliente e não bloqueiam a comparação arquitetural desta ADR.

### Regra de colaboração para Rust/Tauri e CI Windows

Não haverá especialista fixo nem responsável permanente por Rust/Tauri. Em vez
disso, toda PR que alterar código Tauri, o supervisor Rust ou o CI Windows deve
ter um autor responsável e revisão de aprovação de pelo menos outro integrante
do time antes do merge. Essa regra substitui a antiga pendência de nomear um
responsável técnico único e vale a partir do aceite desta ADR.

## Contexto atual

O desenvolvimento usa React/Vite e FastAPI. A persistência-alvo é SQLite em
arquivo com filesystem privado para documentos, decidida pela ADR 0003 e
implementada pela issue #54, que porta o adaptador, as migrations, a
autenticação e a auditoria já integradas. Esta ADR parte desse resultado como
dado e não depende da conclusão da #54 para decidir shell e empacotamento; ela
depende apenas de #54 estar concluída antes de qualquer instalação real.

## Decisão proposta para o MVP

Se aceita, a implementação seguirá este recorte:

```text
Atalho do Windows
        |
        v
Tauri 2 / React — janela e supervisor mínimo
        | inicia e encerra
        v
FastAPI empacotada — 127.0.0.1, porta dinâmica, um worker
        |                         |
        v                         v
SQLite local             filesystem privado
dados/metadados          documentos PDF/JPEG
```

### Shell e empacotamento

- Usar Tauri 2 diretamente como janela e supervisor. O núcleo Rust fica limitado
  a iniciar/encerrar o processo da API, garantir instância única, entregar o
  segredo da execução e aplicar os controles nativos indispensáveis. Regras de
  negócio permanecem em Python.
- Empacotar FastAPI com PyInstaller `onedir`, sem Python instalado pelo cliente.
  A árvore deve ser um recurso privado do aplicativo e testada em Windows limpo.
- Usar o bundle NSIS padrão gerado pelo Tauri como proposta de instalador por
  usuário. Customização fica limitada a nome, ícone, atalhos e preservação do
  diretório de dados; a prova do instalador e do WebView2 pertence à #27.
- Não criar launcher separado, manifesto assinado próprio, atualizador próprio,
  protocolo A/B de versões, journal de ativação ou sistema de gerações no MVP.
  Esses mecanismos só voltam a ser considerados mediante risco demonstrado e
  nova decisão.
- O MVP recebe atualizações manualmente por um novo instalador. A aplicação
  mantém binários separados dos dados, exige backup verificado antes de migration
  incompatível e não abre para escrita quando a migration falha. Não há downgrade
  automático de schema.

### Comunicação local

- A API existe somente enquanto o aplicativo está aberto, não é serviço Windows
  e faz bind apenas em `127.0.0.1` com porta dinâmica e um worker.
- O núcleo nativo gera um segredo aleatório para cada instância e o escreve uma
  única vez no `stdin` herdado do processo filho imediatamente após iniciá-lo.
  O segredo bruto não chega ao React nem passa por URL, argumento de processo,
  variável de ambiente, arquivo permanente ou log.
- O próprio núcleo nativo usa o segredo uma única vez para inicializar a API e
  obter uma capability vinculada à instância atual. Somente essa capability
  chega ao React, por um comando IPC interno e restrito do shell, depois que a
  janela estiver pronta; ela permanece apenas em memória e expira quando a API
  ou o shell encerra.
- Toda chamada da janela à API exige a capability e, quando aplicável, a sessão
  autenticada do proprietário. A API recusa segredo reutilizado, capability de
  outra instância e chamadas de processo ou origem local não autorizados.
- Validar `Host` e `Origin` por allowlist exata, aplicar CSP restritiva, não
  carregar scripts remotos e não expor OpenAPI/diagnóstico detalhado na build de
  produção.
- O supervisor deve encerrar a API no fechamento normal e no encerramento
  forçado do shell. A issue de integração desktop deverá provar que não deixa
  processo órfão e cobrir os invariantes do bootstrap, inclusive tentativas por
  processo e origem local não autorizados.

### Diretórios privados finais

O arquivo SQLite e a árvore de documentos definidos pela ADR 0003 ficam fora dos
binários, em diretório privado resolvido por API de Known Folders sob
`LocalAppData`, fora da pasta do instalador, OneDrive, rede e mídia removível.
Permissões Windows e proteção em repouso precisam ser verificadas antes de
dados reais; o mecanismo exato permanece pendente. Os gates de compatibilidade
do banco (foreign keys, journaling, timeout de lock, `synchronous=FULL`) são
responsabilidade da #54 e da ADR 0003, não desta ADR.

### Primeira execução, atualização e desinstalação

1. Criar diretórios privados e um arquivo SQLite candidato, ainda sem dados reais.
2. Executar a cadeia Alembic até `head`; validar versão, `integrity_check` e
   `foreign_key_check`; somente então publicar o arquivo como banco ativo.
3. Iniciar a API e liberar `POST /auth/setup` somente após o health check. Reinício
   depois de falha deve retomar ou descartar apenas o candidato incompleto.
4. Em atualização manual, o instalador não toca nos dados. Antes de uma nova
   versão migrar o schema e liberar escrita, a issue de implementação deverá
   escolher e provar uma cópia consistente por SQLite Backup API ou por conexão
   fechada com checkpoint completo. A #27 valida o procedimento; falha mantém o
   aplicativo bloqueado para escrita e exige recuperação explícita pela #44.
5. A desinstalação remove binários e atalhos, mas preserva dados e documentos. A
   remoção definitiva é fluxo separado, autenticado e explicitamente confirmado.

Esse recorte usa apenas um candidato temporário durante criação/migration; não
introduz o protocolo geral de gerações, manifestos e atualização da versão
anterior da ADR.

### Fronteira do backup

A issue #44 deve garantir um snapshot consistente de banco, metadados e
documentos, gravá-lo no HD externo e comprovar restauração em outro computador.
Criptografia, formato, KDF, credencial e custódia ainda serão decididos nela.
Nenhum dado real pode ser usado antes de essa proteção e a restauração serem
aprovadas e testadas.

## Alternativas consideradas

### Shell e distribuição

| Alternativa | Implementação/CI | Suporte no cliente | Resultado |
| --- | --- | --- | --- |
| Tauri direto + FastAPI `onedir` + instalador padrão/manual | Dois builds por release (Rust/C++ e Python), supervisor pequeno e job Windows obrigatório | Baixo: uma janela e nenhum serviço administrado | **Aprovada**, com revisão obrigatória de outro integrante em PRs de Rust/CI Windows; sem launcher/updater próprios |
| Shell Python com WebView + PyInstaller | Um empacotamento Python, mas adiciona bridge, integração .NET/WebView e nova prova de segurança/lifecycle | Potencialmente baixo; renderer e empacotamento ainda sem evidência | Alternativa se o time não sustentar Rust; exige micro-spike antes de trocar |
| Electron + FastAPI `onedir` | Builds Node/Chromium e Python; dois runtimes para auditar e atualizar | Baixo na operação, maior pacote e dois ciclos de patch | Fallback, não escolhido para o MVP |
| Navegador/PWA + agente local | Build menor, mas ainda exige instalar, iniciar e proteger um processo local | Pode expor navegador/perfil e lifecycle ao proprietário | Não escolhida: atende pior à experiência pedida; não é rejeição confirmada pelo cliente |
| Tauri + launcher/manifesto/updater/gerações próprios | Outra raiz nativa e matriz de testes de interrupção em cada release | Alto custo de diagnóstico e recuperação | Removida do MVP; risco não demonstrado |

Tauri direto é a proposta porque reaproveita React/FastAPI e o experimento já
produziu evidência limitada de janela, sidecar e lifecycle. Essa evidência não
aprova a stack nem substitui CI do produto. A regra de colaboração acima
substitui a exigência de um responsável fixo por Rust/CI Windows como condição
de aceite.

A comparação de persistência (SQLite/filesystem vs. PostgreSQL/MinIO locais) já
foi decidida pela [ADR 0003](0003-sqlite-como-persistencia-local.md); não é
reaberta aqui.

## Transição PostgreSQL → SQLite

A ADR 0003 e a issue #54 são a fonte da decisão e dos requisitos de
implementação da transição de persistência (driver, migrations, advisory lock,
gates de teste nos dois dialetos e remoção de PostgreSQL/MinIO da fundação).
Esta ADR não repete esses gaps e requisitos; ela só depende da #54 estar
concluída antes da primeira instalação real, e trata PostgreSQL/MinIO apenas
como fundação legada em remoção, nunca como ambiente de desenvolvimento
permanente ou alvo obrigatório após a transição.

## Segurança e limites

- Loopback, CORS e uma janela desktop não substituem autenticação/autorização.
- Tokens, senhas, capability, dados pessoais e caminhos com nome de cliente não
  entram em argumentos, URLs, logs ou `localStorage`.
- A proposta não promete proteção contra malware, administrador local ou sessão
  Windows desbloqueada.
- A proteção contra perda/roubo do equipamento depende da decisão pendente sobre
  criptografia em repouso; dados reais permanecem bloqueados até sua aprovação.
- Assinatura de código e proteção do backup são gates de release separados, não
  mecanismos já aprovados por esta ADR.

## Destino do spike da PR #49

A PR #49 permanece aberta, isolada sobre a branch da ADR e sem merge. Ela prova
somente comportamento sintético de janela Tauri, sidecar, loopback, capability,
encerramento e operações SQLite artificiais. Não prova instalador, WebView2 em
máquina limpa, migrations do CRM, assinatura real, backup ou restauração.

A PR #49 não será mergeada nem terá lockfiles ou código reaproveitados como
implementação. Depois do aceite desta ADR, ela deve ser fechada sem merge,
preservando na issue #43 apenas o relatório sanitizado, o digest e a referência
ao commit experimental que forem úteis à issue de integração desktop que virá a
seguir.

## Consequências

### Positivas

- atende janela/ícone sem instalar serviços administrativos;
- reaproveita React e FastAPI;
- remove launcher, updater e protocolo de gerações customizados do MVP;
- mantém banco e documentos fora dos binários, na persistência já decidida pela
  ADR 0003;
- substitui a exigência de um responsável fixo de Rust/CI Windows por revisão
  obrigatória de outro integrante em cada PR que os altere.

### Custos e riscos

- ainda adiciona Rust/Tauri, PyInstaller e CI Windows;
- atualização manual depende de backup/restauração aprovados na #44;
- distribuição real depende das decisões de equipamento, proteção em repouso e
  assinatura;
- sem responsável fixo de Rust, a exigência de revisão por outro integrante em
  toda PR de Tauri/CI Windows precisa ser sustentada na prática.

## Gates para mudar o status para Aceita

1. Revisar e aprovar a separação entre fatos, hipóteses e pendências.
2. Aprovar explicitamente o recorte Tauri direto ou solicitar a comparação curta
   com shell Python; nenhuma opção é adotada por silêncio.
3. Confirmar que os gates de shell/sidecar/instalador/lifecycle Windows desta
   ADR não duplicam nem reabrem a decisão de persistência já aceita pela ADR
   0003/#54.
4. Registrar a aprovação técnica na PR #48 e somente então alterar o status para
   **Aceita**.
5. Definir o destino da PR #49 (fechar sem merge, preservando só a evidência
   sanitizada útil).

Aceitar esta ADR autoriza abrir a issue de integração desktop. Não autoriza
dados reais, merge da spike, distribuição, assinatura ou mudança de backup.

## Gates posteriores de implementação e release

| Responsável | Provas posteriores |
| --- | --- |
| #54 (já aceita pela ADR 0003) | driver e migrations SQLite portáveis, concorrência da primeira conta, autenticação, auditoria e CI SQLite |
| Issue de integração desktop a criar | shell mínimo, bootstrap/capability por IPC, lifecycle do sidecar e build Windows; validar no runtime local a autenticação da #15 e a auditoria da #17 já integradas |
| #21/#45 | armazenamento privado, validação e importação assistida de PDF/JPEG |
| #44 | snapshot consistente, proteção escolhida e restauração por HD em outro PC |
| #27 | computador/Windows alvo, instalador, WebView2, assinatura decidida, atualização manual, desinstalação e restauração ponta a ponta |

## Rollback da decisão

Antes de dados reais, abandonar Tauri exige somente remover a implementação
experimental e registrar nova decisão de shell; a persistência segue a ADR 0003
e não é afetada por esse rollback. Depois da primeira entrega, trocar shell,
banco ou layout exige nova ADR, backup verificado, conversor versionado e
ensaio de rollback; nunca converter o único conjunto de dados do cliente
in-place.

## Referências primárias

- [Tauri — sidecars](https://v2.tauri.app/develop/sidecar/)
- [Tauri — instalador Windows e WebView2](https://v2.tauri.app/distribute/windows-installer/)
- [PyInstaller — manual](https://pyinstaller.org/en/stable/)
- [pywebview — arquitetura](https://pywebview.flowrl.com/guide/architecture)
- [pywebview — empacotamento](https://pywebview.flowrl.com/guide/freezing)
- [SQLite — usos apropriados](https://www.sqlite.org/whentouse.html)
- [SQLite — Online Backup API](https://www.sqlite.org/backup.html)
- [SQLite — como evitar corrupção](https://www.sqlite.org/howtocorrupt.html)
- [Microsoft — Known Folder IDs](https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid)

# ADR 0002 — Aplicativo local Windows e persistência no dispositivo

**Status:** Proposta

**Issue:** #43

**Data:** 20 de agosto de 2026

**Aprovadores:** responsável pelo produto — proposta e spike autorizados em 20
de agosto de 2026; aprovação técnica pendente

Enquanto esta ADR permanecer como **Proposta**, Tauri, Rust, PyInstaller,
SQLite e outras dependências não podem ser incorporados ao produto nem aos seus
lockfiles. O time pode registrar no PR uma autorização restrita para um spike
isolado, descartável, não distribuível e somente com dados sintéticos. Essa
autorização não aprova dependências de produção nem muda o status da ADR; serve
apenas para obter as evidências técnicas descritas abaixo.

## Contexto

O cliente confirmou que o CRM:

- será usado somente pelo proprietário, em um computador Windows;
- deve abrir como aplicativo com ícone, sem navegador exposto ao usuário;
- manterá dados e documentos no próprio computador;
- deverá fazer backup e restauração por HD externo;
- não pode exigir Docker, Python, banco ou serviço administrado manualmente.

O desenvolvimento atual usa React/Vite, FastAPI, PostgreSQL, MinIO e Docker
Compose. PostgreSQL e MinIO foram definidos como infraestrutura de
desenvolvimento enquanto a arquitetura de produção permanecia pendente. Para o
volume esperado — um proprietário e aproximadamente 500 documentos legados —
executar e atualizar PostgreSQL e MinIO no computador do cliente cria mais
processos, portas, credenciais e pontos de recuperação do que o produto exige.

O sistema manipulará dados pessoais e documentos sensíveis. O instalador, os
processos locais, a persistência, o backup e a atualização fazem parte da
fronteira de segurança.

## Escopo e não objetivos

Esta ADR propõe:

- shell, instalador e processo de execução no Windows;
- banco e armazenamento documental de produção;
- isolamento local, diretórios e proteção em repouso;
- primeira execução, atualização, desinstalação e recuperação;
- contrato que a issue #44 deverá implementar para backup/restauração.

Não fazem parte desta decisão:

- implementar agora o produto ou trocar suas dependências, além do spike
  isolado que o time autorizar explicitamente;
- definir cifra, KDF, formato e custódia final da chave do backup (#44);
- escolher o provedor de e-mail (#46);
- suportar vários usuários, rede local, celular ou portal de cliente.

## Modelo de ameaça e limites

Esta arquitetura deve proteger contra perda/roubo ou retirada do disco, leitura
por outro usuário padrão do Windows, processo ou página local tentando abusar da
API de loopback, pacote adulterado e interrupção durante gravação, backup,
restauração ou atualização.

Ela **não** promete proteger dados já abertos contra malware ou administrador
local, comprometimento da conta Windows atual, acesso físico a uma sessão
desbloqueada, comprometimento do sistema operacional ou das chaves de release,
nem falha simultânea do computador e do único HD de backup. Esses riscos exigem
higiene do Windows, bloqueio de tela, antimalware, custódia das chaves e cópias
fisicamente separadas; não podem ser mascarados por DACL, BitLocker, loopback ou
capability.

## Direcionadores da decisão

Em ordem de prioridade:

1. instalação e uso por usuário comum, sem Docker ou administração técnica;
2. dados e API não expostos à rede local;
3. proteção contra leitura após perda ou retirada do disco;
4. backup portátil, criptografado, autenticado e restaurável em outro PC;
5. snapshot consistente de banco, metadados e documentos;
6. atualização, falha e desinstalação sem perda silenciosa;
7. baixo custo de suporte para um único usuário;
8. reaproveitamento de React/Vite, FastAPI e regras existentes;
9. cadeia de release reproduzível e assinada;
10. testes executados no mesmo banco e armazenamento usados em produção.

## Decisão proposta

### Plataforma e instalador

- Adotar **Windows 11 Pro x64 ainda atendido pela Microsoft** como perfil padrão,
  equivalente ao notebook de referência inspecionado em 20 de agosto de 2026.
  O notebook definitivo ainda não foi escolhido e deverá comprovar esse perfil,
  volume NTFS e BitLocker ativo antes de receber dados reais. Windows 10 e
  Windows 11 Home não são alvos do MVP.
- Usar **Tauri 2** como shell da interface React/Vite.
- Distribuir instalador **NSIS por usuário (`currentUser`)**, sem serviço do
  Windows e sem elevação no runtime. Não usar MSIX no MVP: o ciclo de dados do
  pacote e as restrições de loopback entre processos empacotados e não
  empacotados adicionariam riscos desnecessários.
- Incluir o instalador offline do WebView2 Evergreen para que a instalação não
  dependa da rede. O runtime permanece atualizável pelo mecanismo da Microsoft;
  não será fixada uma versão vulnerável dentro do CRM.
- Assinar instalador e executáveis com Authenticode e timestamp e assinar o
  manifesto de release com a chave ancorada no launcher. Certificados e chaves
  privadas pertencem ao processo seguro de release, nunca ao repositório nem ao
  computador do cliente.

### Topologia de processos

```text
Atalho do Windows
        |
        v
crm-launcher.exe — bootstrap mínimo, assinado e sem WebView/rede
        | valida journal, ponteiro e manifesto assinado da versão
        v
Tauri 2 — janela React e supervisor do processo filho
        | inicia, monitora e encerra
        v
crm-api.exe — FastAPI/Python empacotada com PyInstaller onedir
        | loopback, porta dinâmica, um worker
        +--------------------+--------------------+
        v                    v
     SQLite           filesystem privado
  dados/metadados        documentos PDF/JPEG
```

- Empacotar a API com **PyInstaller em modo `onedir`**. O usuário não instala
  Python. Evitar `onefile`, que extrai arquivos temporários e torna lifecycle,
  antivírus, assinatura e diagnóstico menos previsíveis. Como o `onedir` é uma
  árvore e o `externalBin` do Tauri representa um executável, instalar a árvore
  completa como recurso privado e versionado, com manifesto de hashes, e
  resolver o entrypoint por caminho imutável. Não depender de arquivo auxiliar
  no diretório gravável de dados; o empacotamento deve ser provado em VM limpa.
- Usar um launcher nativo mínimo e assinado como raiz operacional. Ele valida um
  manifesto de release assinado por chave pública embutida, recupera transição
  interrompida e inicia somente a versão apontada por estado durável válido.
  Rotação dessa raiz ou atualização do próprio launcher exige instalador NSIS
  manual assinado, backup do launcher anterior e teste de interrupção; não faz
  parte do atualizador comum do MVP.
- O núcleo Rust, e não JavaScript genérico da WebView, inicia o sidecar com uma
  lista fechada de argumentos. Não expor uma permissão de shell arbitrária ao
  frontend.
- Manter o sidecar em Windows Job Object com `KILL_ON_JOB_CLOSE`, ou primitiva
  equivalente comprovada, para que crash/kill do shell encerre o backend além do
  fluxo gracioso.
- Permitir uma única instância. Fechar a janela solicita shutdown gracioso da
  API e encerra o filho se ele não responder. Nova abertura recupera com
  segurança uma finalização anterior incompleta.
- O backend existe somente enquanto o aplicativo está aberto; não é serviço do
  Windows e não cria regra de firewall.

### Comunicação entre shell e API

- O próprio sidecar faz bind exclusivamente em `127.0.0.1:0`, com um único
  worker, e devolve a porta efetivamente reservada ao núcleo Rust por pipe
  herdado privado. O shell não escolhe/libera previamente a porta, evitando
  janela de TOCTOU.
- Criar, a cada execução, um segredo de bootstrap gerado por CSPRNG com pelo
  menos 256 bits, uso único e TTL curto. O shell o entrega ao sidecar por canal
  herdado/entrada padrão, nunca por argumento, ambiente, arquivo ou log.
- O núcleo Rust, antes de expor a WebView, usa o segredo em um único
  `POST /runtime/bootstrap` para obter uma capability aleatória da execução. Essa
  é a única requisição sem capability: exige o segredo one-shot, fecha após
  sucesso ou TTL e nunca fica disponível novamente naquela execução. A WebView
  recebe somente a capability em memória, nunca o segredo.
- Exigir a capability em **toda outra** requisição, inclusive
  `GET /auth/setup`, `POST /auth/setup` e `POST /auth/login`. Recursos protegidos
  exigem também a sessão e a autorização do proprietário. Bootstrap reutilizado,
  capability de outra execução e requisição sem capability são recusados.
  Loopback e CORS não são controles de autenticação.
- Validar `Host` e `Origin` por allowlist exata, aplicar CSP restritiva, não
  carregar scripts remotos e desabilitar OpenAPI/Swagger e endpoints de
  diagnóstico detalhado na build de produção.
- Não aceitar listener em `0.0.0.0`, IPv6 público, interface LAN ou porta fixa.

### Persistência de produção

- Usar **SQLite** para dados operacionais e metadados. É um banco embutido, sem
  processo, porta, conta administrativa ou inicialização separada, adequado ao
  uso local por um único proprietário. Manter journaling habilitado e
  `synchronous=FULL`; nunca usar journal/sincronização `OFF`. Alterar esses
  parâmetros exige nova evidência de durabilidade no Windows alvo.
- Usar **filesystem privado com blobs imutáveis** para documentos. O banco guarda
  somente metadados e identificadores opacos; nome original nunca define o
  caminho. Substituição cria outro blob e exclusão começa como operação lógica;
  coleta física só ocorre quando nenhuma geração retida o referencia.
- Não pressupor transação atômica entre SQLite e NTFS. Para gravar documento:
  escrever em arquivo temporário no mesmo volume, validar e descarregar os
  buffers; renomear para um identificador final novo e imutável; somente então
  confirmar o metadado em transação no SQLite. Se a transação falhar, remover ou
  colocar o arquivo final em quarentena. Na inicialização, reconciliar órfãos e
  referências sem arquivo, sem expor conteúdo inconsistente nem sobrescrever
  documento existente. Criação, substituição, exclusão e retry/importação usam
  identificador idempotente e restrição no banco; testar queda em cada janela do
  protocolo.
- SQLite e filesystem tornam-se alvos obrigatórios de integração e release.
  PostgreSQL e MinIO podem permanecer durante a transição como infraestrutura
  de desenvolvimento, mas nenhuma funcionalidade é considerada pronta sem
  testes no caminho de produção. Código específico de dialeto fica isolado.
- A implementação deverá portar os pontos PostgreSQL-específicos já existentes:
  URL/driver, tipo UUID, advisory lock da primeira conta e migrations. O
  invariante de proprietário único deve ser garantido por transação e restrição
  do esquema, não apenas pela interface.

Esta proposta escolhe SQLite para produção; não autoriza manter PostgreSQL ou
MinIO ocultos como sidecars. Se o spike provar que SQLite é inviável, o time
precisará de uma nova decisão que demonstre instalação, atualização e backup de
PostgreSQL — não de uma troca silenciosa.

### Diretórios e proteção local

Resolver diretórios pela Known Folder API. Não concatenar caminho a partir de
texto fornecido pelo usuário e não guardar dados dentro da pasta do instalador.

```text
FOLDERID_UserProgramFiles\DeltaForce\CRM\
  launcher\
  versions\<versão>\

FOLDERID_LocalAppData\DeltaForce\CRM\
  data\objects\<id-opaco>
  data\generations\<id>\crm.sqlite3
  data\generations\<id>\objects.manifest (somente depois de selada)
  state\activation-a
  state\activation-b
  state\transition-journal
  state\secrets\
  recovery\generations\
  staging\
  logs\
```

Em operação normal, somente a geração ativa é mutável. Durante modo manutenção,
ela fica bloqueada e uma única candidata não selada pode ser alterada; o SQLite
da geração em uso é a fonte única das referências a blobs, sem manifesto
paralelo concorrente. Para migration ou restauração, criar/importar a candidata
**não selada** pela SQLite Backup API. Ela permanece não selada durante migration
e health check.
Somente depois, extrair as referências do SQLite final, escrever, descarregar e
verificar o manifesto e então selar a candidata. Apenas geração selada pode
entrar no commit de ativação, e gerações seladas nunca são alteradas. Coleta
física usa a união dos manifests selados com uma leitura transacional da geração
ativa e falha fechada — qualquer divergência impede a exclusão.

Um registro de ativação com sequência monotônica e checksum associa **versão do
binário + geração dos dados**; dois slots e um journal de transição permitem
escolher o último commit durável após queda. Escrever, descarregar e verificar o
slot inativo antes de ativá-lo por primitiva Windows comprovada no spike. Todo
estado persistente que uma migration puder mudar deve estar dentro da geração;
segredos DPAPI são versionados separadamente e migrations de schema não os
alteram.

- Os diretórios devem estar em volume NTFS local, fora de OneDrive,
  compartilhamento de rede e mídia removível. Em cada criação, abertura,
  backup/restauração ou ativação sensível, abrir por handle, consultar caminho
  final e identidade do volume e rejeitar junction/reparse point inesperado;
  validar o texto do caminho antes da abertura não basta contra TOCTOU.
- Aplicar DACL protegida ao usuário Windows atual e `SYSTEM`, com herança
  desabilitada, e verificar a ACL efetiva depois da criação; não conceder
  `Everyone`, `Users` ou `Authenticated Users`. Um segundo usuário padrão não
  pode listar, ler, alterar ou excluir os dados.
- Proteger segredos locais ligados à máquina, como futura credencial SMTP, com
  DPAPI `CurrentUser` ou mecanismo equivalente. Tokens de sessão permanecem
  somente em memória.
- **Dados reais só podem ser ativados com BitLocker/Device Encryption ativo em
  todo volume que contenha `data`, `state`, `recovery`, `staging` ou `logs`**, ou
  depois que outra ADR aprove criptografia local equivalente. Verificar essa
  proteção em toda inicialização, antes de abrir a API com dados reais, e exigir
  confirmação de que a chave de recuperação está sob custódia do proprietário
  em local separado; o CRM nunca coleta essa chave. Estado `Off`, `Suspended` ou
  `Unknown` bloqueia a abertura dos dados e mostra orientação segura. ACL
  sozinha não protege um disco retirado ou computador roubado.
- Logs usam IDs técnicos, contagens e códigos de erro; nunca CPF, nome, token,
  senha, conteúdo, caminho com nome de cliente ou credencial. Aplicar rotação e
  limite de tamanho.

### Primeira execução

1. Validar Windows/arquitetura, WebView2, volume local, DACL, espaço e proteção
   de disco.
2. Criar os diretórios e a primeira geração de banco/schema sem dados reais.
3. Iniciar a API, concluir migrations e health check antes de abrir o fluxo.
4. Consultar `GET /auth/setup`; quando necessário, permitir uma única criação
   do proprietário por `POST /auth/setup`.
5. Não persistir senha ou token em argumento, ambiente, arquivo, URL, log ou
   `localStorage`.

Falha em qualquer passo deixa diagnóstico sanitizado e estado retomável; não
recria banco nem apaga diretórios automaticamente.

### Backup e restauração — contrato para #44

A #44 definirá algoritmo, formato, KDF, parâmetros e experiência de recuperação,
mas deverá obedecer a este contrato:

- entrar em modo de manutenção que bloqueia mutações; criar o snapshot SQLite
  pela Online Backup API em conexão controlada e congelar o manifesto de blobs
  referenciado. Nunca copiar cru um banco aberto separado de seu journal/WAL;
- produzir **um artefato versionado, criptografado e autenticado**, com manifesto
  e hashes protegidos dentro do conteúdo cifrado;
- resolver o destino por volume e caminho canônicos, rejeitar rede, nuvem e o
  mesmo volume físico dos dados de origem, confirmar com o proprietário que o
  volume escolhido é o HD externo e pré-validar espaço. Abrir por handle e
  revalidar caminho final, reparse point, filesystem e identidade do volume no
  momento de cada etapa;
- aceitar somente destino NTFS ou exFAT. FAT32 é recusado por seu limite de
  arquivo; a interface orienta usar outro HD sem formatá-lo automaticamente;
- escrever em nome exclusivo com sufixo `.partial`, nunca sobrescrever backup
  anterior, descarregar buffers e só então publicar outro nome definitivo.
  Flush em HD/USB é melhor esforço: desconexão ou firmware defeituoso pode
  corromper até o filesystem. Em falha, não reportar sucesso e tratar o parcial
  como suspeito; depois de ejeção segura e reconexão, revalidar identidade do
  volume e hash do artefato completo antes de marcá-lo como verificado;
- não gravar banco, documento, manifesto com PII ou segredo em claro no HD;
- usar credencial/recovery code portátil, confirmado e guardado separadamente
  do computador e do HD. DPAPI não pode ser a única chave, pois a restauração
  precisa funcionar em outra máquina/conta Windows;
- não migrar sessões ou segredos ligados à máquina; solicitá-los novamente após
  a restauração;
- decriptar, validar versão, integridade, espaço e schema em staging, importar
  blobs sem sobrescrever os existentes e construir uma geração candidata sem
  tocar na geração ativa;
- ativar a geração restaurada somente após validação completa pelo journal e
  ponteiro durável; manter a geração anterior inativa e recuperável;
- orientar a desconectar e guardar o HD separadamente após o backup.

Copiar o arquivo SQLite e os documentos de forma independente, sem bloquear
mutações, não constitui backup consistente.

### Atualização, downgrade e desinstalação

- O MVP começa com instalador NSIS versionado e assinado, aplicado com
  confirmação do proprietário. Atualização automática fica adiada até existir
  canal HTTPS e custódia aprovada da chave do updater.
- Separar dados dos binários. Instalar cada release em diretório imutável sob
  `FOLDERID_UserProgramFiles\DeltaForce\CRM\versions\<versão>` e usar um launcher
  estável que lê o registro de ativação durável e valida o manifesto assinado da
  versão. O manifesto cobre toda a árvore `onedir`; sua assinatura ancora na
  chave pública embutida no launcher. Manter versão e geração anteriores até a
  nova versão concluir o commit de ativação.
- Antes de migration incompatível, verificar espaço e criar a geração candidata
  sem alterar a anterior. A sequência é: instalar a versão ainda inativa; fechar
  a API; validar a geração anterior; clonar somente o banco; iniciar a candidata
  não selada em modo manutenção; migrar e executar health check; gerar/verificar
  o manifesto final e selar; gravar o journal; e só então fazer commit do par
  versão+geração no registro de ativação.
- Pacote adulterado, publicador diferente, assinatura inválida ou downgrade não
  autorizado são recusados.
- Até o commit de ativação, a candidata fica em manutenção e não aceita mutação
  do usuário; falha descarta/quarentena somente a candidata e mantém o par
  anterior. Depois do commit, ainda em modo somente leitura, persistir e
  descarregar uma barreira `rollback-prohibited`; só então expor endpoints
  mutáveis. Queda antes da barreira pode voltar automaticamente ao par anterior;
  durante ou depois dela, usar correção à frente ou restauração explicitamente
  confirmada, nunca rollback automático que possa apagar dados novos. O launcher
  recupera journal interrompido escolhendo o último slot válido; testar queda
  antes, durante e depois da barreira e também durante o próprio rollback.
  Binário antigo nunca abre geração com schema novo.
- Reter versão e geração anteriores até o proprietário confirmar a nova
  abertura, com limpeza posterior explícita e limitada.
- Atualização nunca remove a geração ativa nem o último recovery point válido;
  limpeza posterior alcança apenas versões/gerações inativas e blobs sem
  referência, sob retenção explícita. Desinstalação não remove `data`,
  `recovery`, `state` ou documentos. Uma reinstalação deve reconhecer os dados
  existentes.
- Exclusão definitiva é fluxo separado, autenticado e explicitamente
  confirmado. A desinstalação informa o local preservado e o procedimento de
  remoção, mas não apaga silenciosamente dados pessoais.

## Alternativas consideradas

| Alternativa | Resultado | Motivo |
| --- | --- | --- |
| Tauri + FastAPI + SQLite/filesystem | Proposta | Atende janela/ícone, reaproveita React/FastAPI e elimina serviços administrativos no PC. |
| Tauri + PostgreSQL + MinIO | Rejeitada para o MVP | Mantém paridade atual, mas adiciona dois serviços, portas, credenciais, patches e snapshot distribuído para um único usuário. |
| Electron + FastAPI + SQLite/filesystem | Fallback | Viável, porém distribui Chromium e Node e amplia o ciclo de atualização e a superfície do shell. |
| PWA/navegador + agente local | Rejeitada | Não resolve instalação e lifecycle da API e contraria a experiência de aplicativo único. |
| Serviço Windows para a API | Rejeitada | Exige privilégio/instalação e execução contínua sem necessidade funcional. |
| MSIX + processo Python externo | Rejeitada no MVP | Loopback/container e ciclo de dados do pacote exigem complexidade e prova adicionais. |

Se o spike demonstrar que o pequeno núcleo Rust não é sustentável pelo time, o
fallback é Electron preservando os mesmos contratos de processo, persistência,
diretório, backup e segurança. Não usar PWA ou serviço como fallback implícito.

## Consequências

### Positivas

- instalação sem Docker, Python, PostgreSQL ou MinIO no cliente;
- menos processos, portas, credenciais e manutenção;
- backup e restauração mais simples de tornar consistentes;
- executáveis separados dos dados, permitindo atualização/desinstalação segura;
- interface existente é reaproveitada sem expor navegador.

### Custos e riscos

- adiciona Rust/Tauri, PyInstaller, SQLite assíncrono e build Windows;
- exige adaptar configuração, modelos e migrations PostgreSQL-específicos;
- enquanto PostgreSQL permanecer no desenvolvimento, CI deverá provar ambos os
  adaptadores para evitar divergência;
- exige certificado de assinatura, custódia de chaves e processo de release;
- depende da edição/configuração real do Windows e da criptografia do volume;
- segurança do loopback depende também de bootstrap, autenticação, CSP e
  lifecycle corretos.

Se aceita, esta ADR limita a ADR 0001 ao adaptador PostgreSQL de desenvolvimento
e ao padrão SQLAlchemy/Alembic; SQLite passa a ser a persistência de produção.
O próprio trabalho da #43 deverá, antes de ser encerrado, registrar status e
aprovadores, atualizar a ADR 0001, `AGENTS.md`, `ARCHITECTURE.md` e o plano de
instalação, sem reescrever o histórico. Código e dependências entram apenas nas
issues de implementação correspondentes.

## Gates para mudar o status para Aceita

1. Obter autorização do responsável pelo produto para o alvo proposto e para o
   spike isolado — concluída em 20 de agosto de 2026.
2. Ainda com status **Proposta**, executar as provas mínimas do spike.
3. Revisar as evidências do spike, o modelo de ameaça local, a separação entre
   binário e dados e o plano de rollback.
4. Obter aprovação explícita do time técnico no PR.
5. Registrar o aprovador técnico e atualizar esta ADR de **Proposta** para
   **Aceita**.

## Spike e gates de implementação

Enquanto a ADR ainda estiver como **Proposta**, depois que o time autorizar
explicitamente o spike e sempre antes de incorporar as novas dependências ao
produto, executar um protótipo isolado, não distribuível e com dados
exclusivamente sintéticos em VM Windows 11 x64 limpa. O spike prova as hipóteses
da decisão; não é uma versão do CRM e seus lockfiles não substituem os lockfiles
do produto.

Provas mínimas do spike arquitetural:

- instalar por usuário comum e offline, sem Docker, Python ou UAC no runtime;
- provar em VM sem ferramentas de desenvolvimento que a árvore `onedir` fica em
  caminho imutável, que o launcher rejeita manifesto/arquivo adulterado e que o
  entrypoint válido funciona. Usar chave sintética no spike, nunca chave real de
  release;
- provar instância única e encerramento de todos os filhos no fechamento
  gracioso, hard-kill do shell e reinício do Windows;
- provar que o sidecar reserva `127.0.0.1:0`, informa a porta pelo pipe privado e
  nenhuma porta escuta fora de loopback. Recusar Host/Origin inválido, bootstrap
  reutilizado/expirado e capability ausente/inválida; somente
  `POST /runtime/bootstrap` aceita o segredo one-shot sem capability;
- inspecionar DACL/handles com segundo usuário padrão, reparse point concorrente
  e provar negação de acesso. Em VMs/snapshots executadas como usuário padrão e
  sem UAC, estado de criptografia `Protected` permite e `Off`, `Suspended` e
  `Unknown` bloqueiam todos os volumes de dados antes da API;
- interromper criação, substituição, exclusão e retry/importação de blobs em
  cada janela; reiniciar, reconciliar e executar verificação de integridade do
  SQLite sem corrupção, duplicação ou recriação silenciosa;
- interromper instalação inativa, clone, migration, selagem do manifesto,
  gravação de journal, commit de ativação, barreira `rollback-prohibited`,
  rollback e substituição manual do launcher. Provar seleção do último par
  versão+geração válido, impedir rollback automático desde a barreira e
  reconhecer dados preservados após desinstalar/reinstalar;
- bloquear mutações, criar snapshot técnico consistente do SQLite e de cerca de
  500 documentos sintéticos totalizando provisoriamente 5 GiB pela Online Backup
  API + manifesto de blobs, restaurá-lo como geração candidata e comparar
  integridade/contagens/hashes. Esse volume é hipótese técnica, não limite do
  produto; repetir com o envelope aprovado na #14 antes do release;
- executar migrations e integração no SQLite e nos adaptadores que continuarem
  suportados;
- confirmar que logs, temporários e relatórios não contêm PII ou segredos.

Nenhum dado real pode ser usado no spike.

Os testes completos da criação/autenticação do proprietário pertencem à #15; o
filesystem privado e a reconciliação documental pertencem à #21; o backup
criptografado e sua escrita interrompida no HD pertencem à #44; assinatura do
release, atualização ponta a ponta e aceite em máquina limpa pertencem à #27.
Uma issue de implementação desktop/SQLite, a criar e vincular antes de encerrar
a #43, será dona do shell, instalador, sidecar, adapter SQLite e lifecycle.
Nenhuma dessas issues pode ignorar os contratos desta ADR.

Criptografia do artefato, chave portátil, escrita no HD, detecção de adulteração
e restauração em outro computador são critérios de aceite da #44, não gates
circulares da ADR. Mesmo após esta ADR ser aceita, **dados reais continuam
bloqueados** até #44 provar esse fluxo completo.

## Decisões externas e pendências

Aprovado pelo responsável pelo produto em 20 de agosto de 2026:

- Tauri/Rust, SQLite e filesystem privado como alvo proposto de produção;
- Windows 11 Pro x64 como perfil padrão do notebook definitivo;
- execução do spike isolado somente com dados sintéticos;
- a #44 deverá definir credencial/recovery code portátil e guardado fora do
  computador e do HD, sem reutilizar DPAPI como única chave.

Pendente:

- provas do spike e aprovação técnica antes de mudar o status da ADR;
- responsável, orçamento e custódia para Authenticode, assinatura do manifesto e
  futuras chaves de atualização — bloqueia distribuição, não o spike;
- inspeção do notebook definitivo e de seu BitLocker — bloqueia dados reais, não
  a decisão do perfil suportado.

Enquanto as provas e a aprovação técnica não forem concluídas, esta ADR
permanece **Proposta**. Depois de aceita, desenvolvimento e testes sintéticos da
#21 podem avançar quando a #14 permitir; uso de dados reais continua bloqueado
até os aceites da #21 e da #44, a inspeção do notebook definitivo e as demais
provas de implementação aplicáveis.

## Rollback da decisão

Antes de dados reais, remover o spike e escolher o fallback não exige migração
de cliente. Depois da primeira entrega, trocar shell, banco ou layout exige nova
ADR, conversor versionado, backup verificado e ensaio de rollback. Nunca
converter o único conjunto de dados do cliente in-place sem cópia recuperável.

## Referências primárias

- [Tauri — external binaries/sidecars](https://v2.tauri.app/develop/sidecar/)
- [Tauri — instalador Windows e WebView2](https://v2.tauri.app/distribute/windows-installer/)
- [Tauri — assinatura no Windows](https://v2.tauri.app/distribute/sign/windows/)
- [Tauri — assinatura de atualizações](https://v2.tauri.app/plugin/updater/)
- [Tauri — CSP](https://v2.tauri.app/security/csp/)
- [Tauri — capabilities](https://v2.tauri.app/security/capabilities/)
- [PyInstaller — manual](https://pyinstaller.org/en/stable/)
- [SQLite — usos apropriados](https://www.sqlite.org/whentouse.html)
- [SQLite — arquitetura sem servidor](https://www.sqlite.org/serverless.html)
- [SQLite — Online Backup API](https://www.sqlite.org/backup.html)
- [SQLite — como evitar corrupção](https://www.sqlite.org/howtocorrupt.html)
- [Microsoft — FOLDERID_LocalAppData](https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid)
- [Microsoft — DPAPI/CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)
- [Microsoft — visão geral do BitLocker](https://learn.microsoft.com/en-us/windows/security/operating-system-security/data-protection/bitlocker/)
- [Microsoft — Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
- [Microsoft — ReplaceFileW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew)
- [Microsoft — GetFinalPathNameByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew)
- [Microsoft — GetVolumeInformationByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getvolumeinformationbyhandlew)
- [Microsoft — fim do suporte do Windows 10](https://learn.microsoft.com/en-us/lifecycle/announcements/windows-10-end-of-support)

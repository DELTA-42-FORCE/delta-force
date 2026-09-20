# Decisões confirmadas com o cliente

**Atualizado em 19 de setembro de 2026.** Este registro complementa o levantamento
de requisitos. Em caso de divergência, uma decisão posterior confirmada pelo
cliente prevalece sobre uma hipótese anterior.

## Produto e acesso

- O CRM será usado somente pelo proprietário, em **um computador Windows**.
- O produto deve ser entregue como **aplicativo com ícone na área de trabalho**;
  não é um sistema acessado por outros computadores, celulares ou clientes.
- Não haverá portal, login ou envio de documentos pelos clientes no MVP.
- A conta inicial do proprietário continua obrigatória: a aplicação não pode
  depender de uma conta pré-criada em código, arquivo de ambiente ou terminal.
- A gestão de usuários internos e papéis foi retirada do MVP e permanece como
  possibilidade futura.

## Dados, documentos e acervo atual

- Informações e documentos devem ficar no computador do cliente; o banco guarda
  dados operacionais e metadados, nunca o conteúdo binário do documento.
- O CRM é uma **pasta digital flexível por cliente**. Criar um cliente exige
  somente um nome de identificação; todos os demais dados e documentos são
  opcionais e podem ser incluídos ao longo do tempo. Não há catálogo rígido de
  `gov.br`, regra de reservista ou documento obrigatório no MVP.
- Os documentos são pessoais, predominantemente PDF. O MVP aceita somente
  **PDF** e, para fotos, **JPEG** após validação de conteúdo.
- Não há limite comercial fixo por documento. O limite operacional é a
  capacidade livre do computador: anexos e importações devem ser gravados por
  streaming, verificar espaço disponível e abortar com limpeza segura se ele
  for insuficiente; nunca podem carregar o arquivo inteiro em memória.
- Os arquivos ficam em uma árvore privada gerenciada pelo aplicativo, fora do
  banco. O proprietário poderá abrir a pasta ou exportar uma cópia pelo CRM e,
  por serem arquivos locais, também consegue consultá-los pelo Windows. Alterar,
  renomear ou excluir diretamente arquivos já gerenciados não atualiza os
  metadados nem a auditoria; essas ações devem ser feitas pelo CRM.
- O cliente deseja importar o acervo existente: cerca de 500 documentos antigos
  e 30 a 40 novos. Existem arquivos possivelmente corrompidos; a importação
  precisa produzir relatório e preservar a origem.
- A ficha cadastral em PDF faz parte do MVP.
- O acompanhamento documental é opcional e manual. Anexar ou importar um
  arquivo não cria pendência automaticamente: o documento começa sem status.
  Quando decidir acompanhá-lo, o proprietário pode marcar **pendente** (ainda
  exige providência), **recebido/regular** (conferido manualmente e considerado
  adequado) ou **incorreto/incompleto** (conferido manualmente e com problema),
  e também pode remover o acompanhamento. Esses estados não bloqueiam cadastro,
  edição nem outros anexos e não criam catálogo de documentos obrigatórios.

## Backup, retenção e comunicação

- O backup será feito em **HD externo** e a restauração após perda/troca de
  computador deverá ocorrer a partir dele.
- A proteção do backup poderá usar uma **senha digitada pelo proprietário**. A
  aplicação não deve persistir essa senha no computador, no próprio backup, em
  logs ou no repositório.
- Dados e documentos devem ser guardados, sem prazo de descarte definido.
  Isso não elimina a necessidade de proteger backup, documentar restauração e
  atender eventual solicitação legítima do titular.
- O e-mail remetente da mala direta ainda será informado pelo cliente. Nenhuma
  credencial, conta de teste real ou segredo deve ser adicionado ao repositório.

## Contratos e parcelamento — etapa posterior ao MVP

- Todo contrato possui sinal fixo de **R$ 2.000,00**.
- O saldo restante será dividido em uma quantidade `N`, definida no contrato,
  de parcelas iguais, com vencimento no mesmo dia de cada período.
- Os estados persistidos do contrato serão **Ativo**, **Quitado** e
  **Cancelado**. A condição **Em atraso** será calculada automaticamente a partir
  das parcelas vencidas e não pagas de um contrato ativo; não será um estado
  preenchido manualmente.
- Valores em BRL exigem precisão exata e não podem ser calculados com ponto
  flutuante binário. Vencimentos são datas civis, sem horário ou variação de
  fuso.
### Homologado em 19/09/2026 (resposta do cliente via Aglison)

- **Evento que libera o parcelamento:** pagamento integral do sinal fixo de
  R$ 2.000,00. O proprietário registra a data; referência de comprovante não é
  exigida nem armazenada nesta entrega.
- **Primeiro vencimento:** no mês civil seguinte ao pagamento do sinal,
  preservando o mesmo dia como âncora das parcelas seguintes.
- **Dia inexistente no mês calculado:** o vencimento passa para o primeiro dia
  do mês posterior. Exemplo: a ocorrência ancorada em 31 de fevereiro vence em
  1º de março; a ocorrência seguinte continua ancorada no dia 31.
- **Sobra de centavos:** distribuída, um centavo por vez, nas primeiras
  parcelas, para manter diferença máxima de R$ 0,01 e soma exata.
- **Sinal parcelado:** não faz parte desta entrega. O parcelamento do saldo só é
  criado depois do pagamento integral dos R$ 2.000,00.

O responsável pelo produto autorizou a implementação da #29 com essas decisões.
PagBank, juros, multa, boleto, recibo, relatório financeiro e emissão fiscal
continuam fora desta entrega e exigem suas próprias issues.

## Decisões técnicas registradas

- SQLite em arquivo será usado no desenvolvimento e na entrega local; documentos
  serão guardados em filesystem privado. A decisão está na ADR 0003.

## Decisões técnicas ainda necessárias

A ADR 0002 e a issue #57 já definiram e implementaram o shell/empacotamento
Windows, o diretório privado, a primeira execução e a estratégia de atualização
manual. O formato criptográfico, a custódia/recuperação da senha do backup e o
provedor de e-mail seguem pendentes.

## Perguntas em aberto aguardando o cliente

Enviadas ao cliente em 15/09/2026; **aguardando resposta**. Enquanto não forem
respondidas, as issues abaixo permanecem bloqueadas. Nenhuma senha, credencial
ou segredo deve ser registrado aqui — apenas as decisões escolhidas.

### E-mail da mala direta (issue #46 — bloqueia #25)

1. Qual é o endereço e o nome de exibição do remetente? Informe apenas esses
   dados públicos, nunca senha, token ou código de recuperação.
2. Qual provedor/conta de e-mail já utiliza? A conta permite SMTP e senha de
   aplicativo, ou o provedor oferece outro mecanismo de envio autorizado?
3. Aproximadamente quantos destinatários espera alcançar por lote e com que
   frequência? O limite técnico será definido conforme as regras do provedor.
4. Confirma envio individual por destinatário, com registro das falhas e reenvio
   somente dos que falharam, sem duplicar mensagens já enviadas?

O time escolherá o adaptador SMTP ou API depois de conhecer o provedor. A
credencial deve ficar fora de arquivos, banco, backup, logs e repositório: para
o aplicativo Windows, avaliar Windows Credential Manager/DPAPI ou entrada a
cada sessão. Nenhum segredo deve ser pedido ou registrado nesta issue.

### Backup e restauração por HD externo (issue #44)

Já confirmado: o backup poderá usar uma senha digitada pelo proprietário.

1. Onde manterá uma cópia da senha de recuperação, separada do computador e do
   HD externo (por exemplo, cofre físico ou gerenciador de senhas)? Não informe
   a senha à equipe.
2. Quem deverá poder restaurar o backup em um computador substituto: apenas o
   proprietário ou também uma pessoa de confiança indicada por ele?
3. Se a senha do backup for perdida, haverá uma segunda cópia guardada em outro
   local seguro ou ele aceita que o backup se torne irrecuperável?
4. Com que frequência pretende conectar o HD e fazer backup? Deseja lembrete no
   aplicativo quando estiver há muito tempo sem uma cópia?
5. Quantas versões anteriores deseja manter no HD, ou por quanto tempo? Isso é
   diferente do prazo de guarda dos dados e documentos no CRM, que é indefinido.
6. A restauração será usada apenas em uma instalação vazia ou também poderá
   substituir dados já presentes? Na segunda hipótese, a operação exigirá
   confirmação explícita e proteção contra perda dos dados atuais.
7. O computador e o HD externo já usam senha do Windows e proteção de disco
   (por exemplo, BitLocker)? Essa resposta ajuda a orientar a operação, mas não
   substitui a criptografia do backup.
8. Após trocar o computador, como espera recuperar o acesso à conta do CRM caso
   também tenha esquecido a senha de login? A senha do backup não deve revelar
   nem reutilizar a senha de login.

O time definirá o formato criptográfico, o snapshot consistente de banco e
documentos e a restauração atômica com validação antes de substituir dados. A
senha do backup não será persistida pelo aplicativo nem incluída no backup.

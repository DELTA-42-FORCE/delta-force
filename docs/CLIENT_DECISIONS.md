# Decisões confirmadas com o cliente

**Atualizado em 4 de setembro de 2026.** Este registro complementa o levantamento
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
### Confirmado pelo cliente em 15/09/2026 (via Aglison)

- **Evento que libera o parcelamento:** o parcelamento do saldo passa a contar a
  partir do pagamento do sinal de R$ 2.000,00.
- **Primeiro vencimento:** 30 dias após o sinal.
- **Vencimento em dia sem expediente ou inexistente (ex.: 29, 30, 31):** ajustar
  para o **último dia útil do mês**.

### Ainda pendente antes de implementar

- **Conciliar a regra de vencimento:** "30 dias após o sinal" e "último dia útil
  do mês" precisam ser reconciliados — se o vencimento é *sinal + 30 dias, com as
  parcelas seguintes no mesmo dia recuando para o último dia útil quando cair em
  fim de semana/feriado ou dia inexistente*, ou se *toda parcela vence no último
  dia útil de cada mês*.
- **Calendário de dias úteis:** definir se "dia útil" considera apenas
  sábados/domingos e feriados nacionais, ou também feriados municipais/estaduais.
- **Sobra de centavos da divisão:** ainda não decidido (proposta: distribuir a
  diferença nas primeiras parcelas, para que fiquem quase iguais e a soma feche).
- **Sinal parcelado em 2x:** o cliente admitiu dividir o próprio sinal de
  R$ 2.000,00 em duas parcelas iguais; falta definir o vencimento dessas duas
  parcelas e se o parcelamento do saldo passa a contar após a quitação total do
  sinal ou já a partir da primeira parcela.

Essas decisões detalham a issue #29, mas não repriorizam o financeiro: contratos,
cobranças e relatórios continuam fora do MVP. A issue #28 permanece bloqueada
até a homologação do evento que libera o parcelamento.

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

1. Endereço e nome de exibição do remetente.
2. Forma de envio — proposta: usar o e-mail já contratado por SMTP; alternativa:
   contratar um serviço de envio por API.
3. Onde a credencial do e-mail fica guardada — proposta: arquivo protegido só na
   máquina, fora do sistema e do backup; alternativa: gerenciador de senhas do
   proprietário.
4. Limite de destinatários por lote — proposta: 50 por vez; alternativa: outro
   número informado pelo cliente.
5. Comportamento em falha parcial — proposta: registrar quem falhou e reenviar
   só para esses, sem duplicar; alternativa: reenviar a lista inteira.

### Backup e restauração por HD externo (issue #44)

Já confirmado: o backup poderá usar uma senha digitada pelo proprietário.

1. Onde guardar a senha/chave de recuperação, fora do computador e do HD de
   backup — proposta: local físico seguro (cofre/papel) sob responsabilidade do
   proprietário; alternativa: gerenciador de senhas do proprietário.
2. Quem pode restaurar o backup em um computador substituto — proposta: apenas o
   proprietário; alternativa: proprietário mais uma pessoa de confiança indicada.
3. Procedimento em caso de perda da senha/chave — proposta: aceitar o backup como
   irrecuperável e recomeçar; alternativa: manter uma segunda cópia da senha em
   outro local seguro.

O formato criptográfico do backup (ex.: AES-256) é decisão técnica do time e não
depende dessas respostas.

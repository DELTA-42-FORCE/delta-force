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
- O proprietário cadastrará no próprio aplicativo o nome, endereço e servidor
  SMTP do remetente. Nenhuma credencial, conta de teste real ou segredo deve ser
  adicionado ao repositório, banco, backup ou logs.
- O e-mail opcional de cada cliente será um campo próprio, validado, da pasta
  digital; não será inferido de campos livres. Modelos aceitam somente a
  variável `{{nome}}` no MVP. Outras variáveis exigem decisão e teste próprios.

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
manual. A validação final ainda precisa comprovar instalação limpa, assinatura
do instalador, envio com a conta real escolhida pelo proprietário e restauração
em outro computador. Esses são gates de aceite, não novas regras do cliente.

## Configurações operacionais feitas no próprio aplicativo

As informações públicas do remetente e as preferências operacionais serão
preenchidas pelo proprietário no aplicativo. Nenhuma senha, credencial ou
segredo deve ser registrado aqui, em issue ou em pull request.

### E-mail da mala direta (issues #25 e #46)

Por autorização do responsável pelo produto, as opções operacionais que não
alteram o escopo foram fechadas com padrões seguros:

- o MVP usa SMTP configurável, compatível com o provedor que o proprietário
  escolher; uma API específica de provedor fica fora do MVP;
- nome, endereço, servidor, porta, segurança, usuário e limite do lote são
  cadastrados no aplicativo; a senha ou senha de aplicativo é digitada somente
  no momento do envio e nunca é persistida;
- TLS direto ou STARTTLS validam certificado e nome do servidor. SMTP sem TLS é
  permitido exclusivamente para o Mailpit em endereço de loopback no ambiente
  de desenvolvimento e fica desabilitado por padrão na entrega final;
- cada destinatário recebe uma mensagem individual. O lote padrão comporta até
  50 destinatários e pode ser configurado entre 1 e 100;
- falhas comprovadamente rejeitadas podem ser tentadas de novo. Resultado
  desconhecido exige confirmação manual, pois o servidor pode já ter aceitado a
  mensagem; um novo envio após sucesso também exige confirmação explícita;
- o histórico guarda destinatário, conteúdo renderizado, identificador e
  resultado do envio. A consulta desse histórico e da configuração é auditada.

A conta real continua sendo necessária somente para o aceite operacional. Ela
não bloqueia a implementação nem deve ser registrada em issue ou pull request.

### Backup e restauração por HD externo (issue #44)

Já confirmado pelo cliente: o destino é um HD externo e a proteção usa senha
digitada pelo proprietário. Por autorização do responsável pelo produto, o MVP
adota ainda estas decisões conservadoras:

- cada backup é um arquivo versionado, criptografado e autenticado; não
  sobrescreve versões anteriores automaticamente;
- a senha é solicitada em cada backup/restauração e não é persistida. Não existe
  senha mestra, recuperação pela equipe ou chave presa ao computador perdido;
- somente o proprietário autenticado pode iniciar a operação. Se perder a senha
  e não mantiver uma cópia segura separada, o backup é irrecuperável;
- o aplicativo lembra o proprietário quando não houver backup bem-sucedido nos
  últimos sete dias, mas a conexão e a execução permanecem manuais;
- a restauração do MVP é aceita apenas em instalação vazia, valida todo o pacote
  antes da troca e não apaga o backup de origem. Substituir uma instalação que
  já contenha dados exige uma evolução posterior com confirmação reforçada;
- a senha de backup é independente da senha de login. O snapshot restaura a
  conta existente; recuperação de senha continua sendo outro fluxo;
- proteção do Windows e BitLocker são recomendadas, mas não substituem a
  criptografia do arquivo de backup.

A ADR da #44 deve registrar o formato, os limites, a consistência do snapshot e
o procedimento atômico antes da integração da implementação.

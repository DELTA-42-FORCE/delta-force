# Decisões confirmadas com o cliente

**Atualizado em 25 de agosto de 2026.** Este registro complementa o levantamento
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

## Backup, retenção e comunicação

- O backup será feito em **HD externo** e a restauração após perda/troca de
  computador deverá ocorrer a partir dele.
- Dados e documentos devem ser guardados, sem prazo de descarte definido.
  Isso não elimina a necessidade de proteger backup, documentar restauração e
  atender eventual solicitação legítima do titular.
- O e-mail remetente da mala direta ainda será informado pelo cliente. Nenhuma
  credencial, conta de teste real ou segredo deve ser adicionado ao repositório.

## Decisões técnicas registradas

- SQLite em arquivo será usado no desenvolvimento e na entrega local; documentos
  serão guardados em filesystem privado. A decisão está na ADR 0003.

## Decisões técnicas ainda necessárias

A ADR 0002 e a issue #57 já definiram e implementaram o shell/empacotamento
Windows, o diretório privado, a primeira execução e a estratégia de atualização
manual. A criptografia e a recuperação do backup, e o provedor de e-mail seguem
pendentes.

# Decisões confirmadas com o cliente

**Atualizado em 19 de agosto de 2026.** Este registro complementa o levantamento
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
- O cadastro deve partir dos dados solicitados para criação de conta em serviços
  `gov.br`. Antes de modelar a migration, o time deve registrar o catálogo
  explícito de campos e a fonte da regra em #14; não é permitido inferir campos
  adicionais sem homologação.
- Os documentos são pessoais, predominantemente PDF. O MVP aceita somente
  **PDF** e, para fotos, **JPEG** após validação de conteúdo.
- O limite de tamanho ainda não foi informado. Até a definição, uploads e
  importação não podem ser liberados com limite arbitrário.
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

## Decisões técnicas ainda necessárias

As decisões acima não autorizam escolher por hipótese a tecnologia de entrega.
A issue #43 definirá, por ADR aprovada, o empacotamento Windows, persistência de
produção, diretório privado de dados, primeira execução e estratégia de
atualização. PostgreSQL, MinIO, Mailpit e Docker Compose continuam sendo a
infraestrutura de desenvolvimento até essa decisão.

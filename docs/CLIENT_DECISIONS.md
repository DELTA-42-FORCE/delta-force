# Decisões confirmadas com o cliente

**Atualizado em 20 de agosto de 2026.** Este registro complementa o levantamento
de requisitos. Em caso de divergência, uma decisão posterior confirmada pelo
cliente prevalece sobre uma hipótese anterior.

## Produto e acesso

- O CRM será usado somente pelo proprietário, em **um computador Windows**.
- O notebook definitivo ainda não foi escolhido. O padrão de entrega aprovado é
  **Windows 11 Pro x64 com BitLocker ativo**, equivalente ao perfil do notebook
  de referência; a instalação deverá validar o equipamento final antes de abrir
  dados reais.
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
- A recuperação deverá usar uma credencial/recovery code portátil guardada fora
  do computador e do HD; a definição criptográfica e a experiência pertencem à
  #44 e não podem depender somente de DPAPI.
- Dados e documentos devem ser guardados, sem prazo de descarte definido.
  Isso não elimina a necessidade de proteger backup, documentar restauração e
  atender eventual solicitação legítima do titular.
- O e-mail remetente da mala direta ainda será informado pelo cliente. Nenhuma
  credencial, conta de teste real ou segredo deve ser adicionado ao repositório.

## Decisão técnica em avaliação

O responsável pelo produto autorizou em 20 de agosto de 2026 a proposta da ADR
0002 — Tauri/Rust, FastAPI empacotada, SQLite e filesystem privado — e um spike
isolado somente com dados sintéticos. A ADR permanece **Proposta** até as provas
do spike e a aprovação técnica no PR. PostgreSQL, MinIO, Mailpit e Docker Compose
continuam sendo a infraestrutura de desenvolvimento até a decisão ser aceita.

Responsável, orçamento e custódia da assinatura do aplicativo permanecem
pendentes e bloqueiam distribuição, mas não o spike sintético.

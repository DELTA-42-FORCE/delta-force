# ADR 0003 — SQLite como persistência local de desenvolvimento e entrega

**Status:** Aceita

**Data:** 25 de agosto de 2026

**Issue relacionada:** #54

## Contexto

O CRM será usado por um único proprietário, em um único computador Windows. Os
dados e os documentos precisam permanecer no dispositivo, sem que o proprietário
instale ou administre um servidor de banco. A fundação atual usa PostgreSQL e
MinIO somente porque foi criada antes da definição da entrega local; mantê-los
como ambiente obrigatório de desenvolvimento criaria uma diferença evitável em
relação ao aplicativo que será entregue.

## Decisão

- SQLite em arquivo será o banco de dados operacional tanto no desenvolvimento
  quanto na entrega Windows.
- SQLAlchemy 2 e Alembic permanecem; o adaptador passará a usar o driver
  assíncrono SQLite e migrations portáveis.
- Documentos continuarão fora do banco, em filesystem privado, tanto no
  desenvolvimento quanto na entrega. O banco conterá somente metadados.
- Docker, PostgreSQL e MinIO deixam de ser pré-requisitos do desenvolvimento.
  Enquanto o código de transição existir, eles podem ser usados apenas para
  manter os checks legados funcionando; não são arquitetura-alvo nem justificam
  novas funcionalidades específicas de PostgreSQL.

Esta ADR não escolhe o shell, instalador ou distribuição desktop. Essas decisões
continuam na issue #43 e na ADR 0002, que está aceita. Também não define
criptografia do backup, limite máximo de upload ou o remetente de e-mail.

## Requisitos implementados na #54

A issue #54 implementou, antes de iniciar funcionalidades persistentes de
clientes e documentos:

1. adicionar o driver SQLite e aceitar uma URL SQLite de arquivo configurada;
2. tornar modelos e migrations compatíveis com SQLite, inclusive UUID, índices,
   `foreign keys`, timestamps e a migration de token de sessão;
3. habilitar e testar `PRAGMA foreign_keys=ON`, `journal_mode=WAL`, timeout de
   lock e `synchronous=FULL` em cada conexão de produção;
4. substituir o advisory lock PostgreSQL da primeira conta por invariante de
   banco e transação compatíveis; duas tentativas concorrentes devem criar
   exatamente um proprietário;
5. executar migrations, autenticação e auditoria em SQLite de arquivo, inclusive
   fechamento/reabertura, `integrity_check` e `foreign_key_check`;
6. atualizar os comandos locais e o CI para que SQLite seja o teste de
   integração obrigatório. PostgreSQL permanece somente como check legado de
   compatibilidade até sua remoção em manutenção posterior.

Nenhuma migration de dados reais é necessária: a primeira instalação do cliente
nascerá com banco SQLite vazio. O acervo existente será tratado pela importação
assistida da issue #45, com cópia, confirmação e relatório.

## Consequências

- A instalação, o backup e a restauração lidam com um arquivo de banco e a árvore
  privada de documentos, sem serviço de banco separado.
- Desenvolvimento e produção exercitam o mesmo dialeto, reduzindo divergências
  de SQL e migrations.
- SQLite atende este MVP de um único usuário, mas não autoriza uso concorrente
  por rede, múltiplos usuários internos ou sincronização entre dispositivos.
  Qualquer evolução desse tipo requer nova ADR.
- A ADR 0001 é substituída como decisão vigente de persistência; ela permanece
  como registro histórico da fundação inicial.

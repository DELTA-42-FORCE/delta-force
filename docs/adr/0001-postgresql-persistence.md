# ADR 0001 — Persistência PostgreSQL assíncrona e migrations Alembic

**Status:** Aceita

## Contexto

O CRM precisa persistir usuários, clientes, auditoria e metadados documentais no PostgreSQL 16 já definido para o ambiente local. A API precisava de um caminho único para conexão, sessões e evolução do esquema antes das entidades de domínio.

## Decisão

Usar SQLAlchemy 2 com driver assíncrono `psycopg` como adaptador de persistência e Alembic para migrations versionadas. A URL usa o esquema `postgresql+psycopg://`, vem de `DATABASE_URL` no ambiente e é validada no início do uso do adaptador. Rotas HTTP não executam SQL diretamente.

## Consequências

- Toda mudança de esquema futura exige migration reversível, revisão e teste.
- O banco é acessado por sessões fornecidas pelo adaptador de infraestrutura.
- O endpoint `/health/ready` verifica conectividade sem expor detalhes de falha.
- Não há tabelas de negócio nesta fundação; elas serão introduzidas pelas issues responsáveis.

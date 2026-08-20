# Arquitetura inicial

O repositório é um monorepo: a API e a interface compartilham documentação, automações e infraestrutura, mas preservam dependências e testes isolados.

## Desenvolvimento

```text
apps/web ────────────────► apps/api ─────────────► PostgreSQL
  interface interna          autenticação e regras      dados operacionais
                              │
                              ├──────────────────────► MinIO
                              │                         documentos digitalizados
                              └──────────────────────► provedor de e-mail
                                                        (Mailpit local)
```

PostgreSQL, MinIO, Mailpit e Docker Compose são a infraestrutura de
**desenvolvimento**. Eles não significam que o cliente precisará instalar Docker
ou administrar esses serviços no computador Windows.

## Entrega ao cliente

O cenário aprovado é um aplicativo local Windows, usado somente pelo
proprietário e com dados/documentos no próprio dispositivo. A arquitetura de
produção — embalagem do aplicativo, banco, armazenamento privado de documentos,
primeira execução, atualização e backup — será definida pela ADR da issue #43.
Até essa aprovação, nenhuma dependência desktop ou troca de persistência deve
ser introduzida por conveniência.

Na API, a evolução deve manter as fronteiras abaixo:

- `domain`: entidades, regras e interfaces sem dependência de HTTP ou banco;
- `application`: casos de uso, DTOs e autorização;
- `infrastructure`: PostgreSQL, armazenamento de arquivos, e-mail e integrações;
- `presentation`: rotas HTTP, serialização e autenticação de requisição.

Essa separação reproduz o princípio adotado no Genesi, mas inicia pequena: não crie camadas vazias sem uma funcionalidade real. Toda decisão estrutural que mude este desenho deve ser registrada em `docs/adr/`.

## Persistência

O PostgreSQL é acessado somente pelo adaptador em `apps/api/src/crm_api/infrastructure/database.py`. A configuração é validada por `core/config.py`, usa o driver assíncrono `psycopg` e não deve ser lida diretamente por rotas HTTP. Migrations são controladas pelo Alembic em `apps/api/alembic/`; cada alteração de esquema futura requer migration reversível e teste correspondente.

Na instalação do cliente, documentos continuarão fora do banco e em área privada
da aplicação; somente metadados podem ser persistidos no banco. Backup e
restauração devem contemplar banco, documentos e metadados como uma unidade.

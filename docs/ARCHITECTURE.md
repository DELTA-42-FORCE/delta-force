# Arquitetura inicial

O repositório é um monorepo: a API e a interface compartilham documentação, automações e infraestrutura, mas preservam dependências e testes isolados.

## Desenvolvimento e dados locais

```text
apps/web ────────────────► apps/api ─────────────► SQLite em arquivo
  interface interna          autenticação e regras      dados operacionais
                              │
                              ├──────────────────────► filesystem privado
                              │                         documentos PDF/JPEG
                              └──────────────────────► provedor de e-mail
                                                        (Mailpit, quando aplicável)
```

SQLite e filesystem privado são o alvo para desenvolvimento e entrega, conforme
a [ADR 0003](adr/0003-sqlite-como-persistencia-local.md). Docker, PostgreSQL e
MinIO não são pré-requisitos. A fundação SQLite foi entregue pela #54; o suporte
PostgreSQL restante existe apenas no check legado de compatibilidade e não é
base para funcionalidades novas.

## Entrega ao cliente

O cenário aprovado é um aplicativo local Windows, usado somente pelo
proprietário e com dados/documentos no próprio dispositivo. A
[ADR 0002](adr/0002-aplicativo-local-windows.md), com status **Aceita**,
define a entrega: Tauri 2 como shell e supervisor mínimo, React na janela e
FastAPI empacotada com PyInstaller `onedir`. A persistência SQLite já está
decidida pela ADR 0003 e não faz parte do escopo da ADR 0002. A implementação
do shell será feita em uma nova issue de integração desktop; o spike da issue
#43 (PR #49) permanece experimento isolado e não deve ser integrado ao produto.

Versão/edição do Windows, proteção do disco, assinatura do instalador e método de
recuperação do backup ainda são decisões operacionais pendentes. Elas não devem
ser registradas como fatos confirmados pelo cliente.

Na API, a evolução deve manter as fronteiras abaixo:

- `domain`: entidades, regras e interfaces sem dependência de HTTP ou banco;
- `application`: casos de uso, DTOs e autorização;
- `infrastructure`: SQLite, armazenamento de arquivos, e-mail e integrações;
- `presentation`: rotas HTTP, serialização e autenticação de requisição.

Essa separação reproduz o princípio adotado no Genesi, mas inicia pequena: não crie camadas vazias sem uma funcionalidade real. Toda decisão estrutural que mude este desenho deve ser registrada em `docs/adr/`.

## Persistência

SQLite será acessado somente pelo adaptador em
`apps/api/src/crm_api/infrastructure/database.py`. A configuração não deve ser
lida diretamente por rotas HTTP. Migrations são controladas pelo Alembic em
`apps/api/alembic/`; cada alteração de esquema futura requer migration reversível
e teste correspondente. A fundação persistente SQLite já foi portada pela #54;
as próximas entidades devem usar esse adaptador, sem acoplamento ao PostgreSQL.

Na instalação do cliente, documentos continuarão fora do banco e em área privada
da aplicação; somente metadados podem ser persistidos no banco. Backup e
restauração devem contemplar banco, documentos e metadados como uma unidade.

## Auditoria

A trilha de auditoria é append-only na aplicação. Casos de uso registram ações
de negócio explicitamente; a dependência de autenticação centraliza apenas as
tentativas negadas por sessão ausente ou inválida. Não existe endpoint de
criação, edição ou exclusão manual de eventos.

Uma mutação relevante e seu evento usam a mesma sessão e o mesmo commit. Se o
evento não puder ser persistido, a mutação é revertida. Falhas técnicas que já
forçaram rollback não são gravadas nesta fundação; uma futura exigência desse
tipo deverá usar uma transação independente ou outbox sem comprometer a
atomicidade do fluxo principal.

O contexto é limitado a rota parametrizada pelo servidor, método HTTP e códigos
de motivo fechados. E-mail submetido, nome, senha, token, hash de token,
cabeçalho `Authorization`, corpo da requisição, IP e user-agent não pertencem ao
log. Cada issue futura de clientes, documentos, importação, PDF, e-mail e backup
deve acrescentar os próprios eventos no caso de uso correspondente.

Ações e tipos de recurso pertencem a catálogos fechados; identificadores de
recurso são UUIDs internos, nunca CPF, e-mail ou outro dado do cliente. O ator
autenticado referencia a conta preservada no banco, que não pode ser removida
enquanto houver histórico. A consulta usa cursor por `(occurred_at, id)`, não
offset, para que o próprio evento de visualização ou novos registros não
desloquem páginas já percorridas.

No SQLite, habilitar e testar `PRAGMA foreign_keys=ON` em toda conexão é
obrigatório antes de considerar uma FK efetiva. A transição também deve definir e
testar journal, timeout de lock, `synchronous=FULL`, timestamps UTC e a
integridade após reabrir o arquivo; compilar DDL isoladamente não prova essas
garantias.

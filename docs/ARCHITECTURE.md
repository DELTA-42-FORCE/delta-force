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
produção está proposta na [ADR 0002](adr/0002-aplicativo-local-windows.md), ainda
com status **Proposta**. Até sua aprovação, nenhuma dependência desktop ou troca
de persistência pode entrar no produto; apenas um spike isolado e sintético pode
ser autorizado explicitamente pelo time.

Se aceita, a topologia de produção será:

```text
Atalho ──► launcher mínimo assinado ──► Tauri 2 / React
                  │                         │ supervisiona
                  │ valida release          ▼
                  │ e ativação       FastAPI empacotada
                  │                         │
                  └───────────────► geração SQLite + blobs imutáveis

Tauri/API: capability por execução, somente 127.0.0.1 / porta dinâmica
```

O instalador proposto é NSIS por usuário, sem serviço Windows, Docker, Python,
banco administrado ou navegador exposto ao cliente. Binários versionados ficam
separados de dados; um launcher mínimo valida o manifesto assinado e o registro
durável que associa versão e geração de dados. Atualização/restauração constroem
uma candidata sem alterar a anterior e só a ativam após migration e health check.
A desinstalação preserva dados. Backup/restauração por HD externo será
implementado na #44 sob o contrato de consistência, criptografia portátil e
recuperação definido pela ADR.

O perfil padrão aprovado pelo produto é Windows 11 Pro x64 com BitLocker ativo.
O notebook definitivo não é o equipamento de desenvolvimento e deverá ser
inspecionado antes de receber qualquer dado real.

Na API, a evolução deve manter as fronteiras abaixo:

- `domain`: entidades, regras e interfaces sem dependência de HTTP ou banco;
- `application`: casos de uso, DTOs e autorização;
- `infrastructure`: PostgreSQL, armazenamento de arquivos, e-mail e integrações;
- `presentation`: rotas HTTP, serialização e autenticação de requisição.

Essa separação reproduz o princípio adotado no Genesi, mas inicia pequena: não crie camadas vazias sem uma funcionalidade real. Toda decisão estrutural que mude este desenho deve ser registrada em `docs/adr/`.

## Persistência

O PostgreSQL é acessado somente pelo adaptador em `apps/api/src/crm_api/infrastructure/database.py`. A configuração é validada por `core/config.py`, usa o driver assíncrono `psycopg` e não deve ser lida diretamente por rotas HTTP. Migrations são controladas pelo Alembic em `apps/api/alembic/`; cada alteração de esquema futura requer migration reversível e teste correspondente.

Enquanto a ADR 0002 não for aceita, PostgreSQL e MinIO continuam sendo somente o
caminho definido de desenvolvimento. Se aceita, SQLite será o banco de produção
em gerações e documentos serão blobs imutáveis no filesystem privado, ambos
atrás de adaptadores e cobertos por migrations/testes no caminho real do
aplicativo. Pontos específicos de PostgreSQL, inclusive o lock da primeira
conta, deverão ser substituídos por invariantes transacionais compatíveis, não
copiados para rotas ou componentes.

Na instalação do cliente, documentos continuarão fora do banco e em área privada
da aplicação; somente metadados podem ser persistidos no banco. Backup e
restauração devem contemplar banco, documentos e metadados como uma unidade.

# Delta Force CRM

Monorepo do CRM interno de gestão de clientes da Delta Force.

## Escopo do MVP

- Acesso de usuários internos autorizados;
- Cadastro e consulta de clientes;
- Gestão manual de documentos, checklist e status;
- Mala direta por e-mail e histórico de disparos;
- Auditoria de ações relevantes.

PagBank, financeiro, ficha em PDF e emissão fiscal estão fora do MVP inicial. Consulte [o guia do projeto](docs/PROJECT_GUIDE.md) e [o backlog](docs/BACKLOG.md).

## Estrutura

```text
apps/api/       API FastAPI (Python/uv)
apps/web/       Interface React + TypeScript
infra/          Serviços locais: PostgreSQL, MinIO e Mailpit
docs/           Requisitos, decisões e guias de trabalho
.github/        CI, templates de issues e de pull request
```

## Começo rápido

Pré-requisitos: Git, [just](https://github.com/casey/just), Docker Compose, Python 3.12+ com `uv`, Node.js 22+ e npm.

```bash
cp .env.example .env
just install
just infra-up
just api-migrate
just check
just audit # auditoria manual de segurança e de versões disponíveis
```

Use `just --list` para ver todos os comandos. Nenhuma credencial deve ser versionada.

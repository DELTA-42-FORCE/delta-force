# Delta Force CRM

Monorepo do CRM interno de gestão de clientes da Delta Force.

## Escopo do MVP

- Aplicativo local para um único proprietário, em computador Windows;
- Primeiro acesso, autenticação e auditoria de ações relevantes;
- Cadastro e consulta de clientes;
- Gestão manual de documentos PDF/JPEG, checklist e status;
- Importação assistida do acervo existente;
- Geração da ficha cadastral em PDF;
- Mala direta por e-mail e histórico de disparos;
- Backup e restauração por HD externo.

Gestão de múltiplos usuários, PagBank, financeiro e emissão fiscal estão fora
do MVP inicial. Consulte as [decisões do cliente](docs/CLIENT_DECISIONS.md),
[o plano do MVP](docs/MVP_PLAN.md), [o guia do projeto](docs/PROJECT_GUIDE.md)
e [o backlog](docs/BACKLOG.md).

## Estrutura

```text
apps/api/       API FastAPI (Python/uv)
apps/web/       Interface React + TypeScript
apps/desktop/   Shell Windows Tauri e supervisão do sidecar FastAPI
infra/          Serviços de desenvolvimento: PostgreSQL, MinIO e Mailpit
docs/           Requisitos, decisões e guias de trabalho
.github/        CI, templates de issues e de pull request
```

## Começo rápido

Pré-requisitos para desenvolvimento web/API: Git, [just](https://github.com/casey/just), Python 3.12+ com `uv`, Node.js 22+ e npm. Docker Compose é opcional e só atende os checks legados de PostgreSQL.

```bash
cp .env.example .env
just install
just infra-up
just api-migrate
just check
just audit # auditoria manual de segurança e de versões disponíveis
```

## Aplicativo Windows

O produto será entregue como aplicativo Tauri no Windows. O shell empacota a
API FastAPI como sidecar PyInstaller `onedir`, inicia-a em `127.0.0.1` com porta
dinâmica e preserva banco/documentos fora dos binários. Para gerar um build de
desenvolvimento no Windows, execute:

```powershell
just api-install
just web-install
just desktop-install
just desktop-build
```

O instalador NSIS gerado é apenas artefato de teste nesta etapa: assinatura,
distribuição, backup/restauração e validação em máquina Windows limpa pertencem
às issues #44 e #27. Consulte a ADR 0002 antes de alterar Rust, Tauri ou CI.

Use `just --list` para ver todos os comandos. Nenhuma credencial deve ser versionada.

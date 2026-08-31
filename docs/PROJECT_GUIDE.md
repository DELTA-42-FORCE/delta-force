# Guia de trabalho do Delta Force CRM

## Organização do monorepo

| Área | Responsabilidade |
| --- | --- |
| `apps/api` | API, regras de negócio, persistência, integrações e testes Python. |
| `apps/web` | Interface interna, experiência do operador e testes TypeScript. |
| `apps/desktop` | Shell Tauri Windows, sidecar FastAPI e build do instalador. |
| `infra` | Recursos locais que simulam dependências externas. |
| `docs` | Requisitos, decisões arquiteturais e material operacional. |
| `.github` | Proteções de qualidade que rodam em pull requests. |

## Fluxo de Git

`main` representa versões estáveis e `develop` é a integração do trabalho aprovado. Cada issue é implementada em uma branch curta, criada a partir de `develop`:

```text
feature/123-cadastro-clientes
fix/456-status-documento
chore/789-configurar-backup
```

Antes de começar e imediatamente antes de pedir revisão:

```bash
git fetch origin
git rebase origin/develop
just check
```

Se houver conflito, resolva-o na própria branch, execute `just check` de novo e faça `git push --force-with-lease` — nunca `--force` simples. Um pull request deve apontar para `develop`, referenciar a issue (`Closes #123`) e passar todos os checks. A integração em `develop` será por **squash merge** após uma aprovação. Releases usam PR de `develop` para `main`.

## Convenções de commits e PRs

Use Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`. Mantenha um único objetivo por PR. Não suba arquivos `.env`, dumps de banco, documentos reais de clientes, chaves ou tokens.

## Qualidade local

| Comando | Finalidade |
| --- | --- |
| `just check` | Validação completa exigida no PR. |
| `just audit` | Auditoria manual: Bandit, vulnerabilidades Python/JavaScript e relatório de versões novas. Não atualiza dependências. |
| `just api-check` | Black, Flake8 e testes unitários da API. |
| `just api-migrate` | Durante a transição, aplica migrations no banco atualmente configurado. O alvo final é SQLite em arquivo. |
| `just api-rollback` | Reverte a última migration; use `just api-rollback base` somente em banco local descartável. |
| `just api-makemigration "descricao"` | Gera uma migration a ser revisada antes de ser aplicada. |
| `just api-test-integration` | Durante a transição, executa a integração legada; a issue SQLite deve substituí-la por testes em arquivo SQLite. |
| `just web-check` | Prettier, ESLint, tipos e testes do web. |
| `just desktop-install` | Instala a CLI e dependências do shell Tauri. |
| `just desktop-build` | No Windows, gera o sidecar PyInstaller `onedir` e o instalador NSIS de teste. |
| `just desktop-format-check` | Verifica a formatação Rust do shell. |
| `just infra-up` | Sobe serviços auxiliares legados/opcionais; não é pré-requisito do CRM. |
| `just infra-down` | Para os serviços sem apagar dados. |
| `just infra-reset` | Apaga os volumes locais; use conscientemente. |

## Regras para dados pessoais

O CRM manipulará dados pessoais sensíveis. Em desenvolvimento, use apenas dados sintéticos. Os anexos não devem ser versionados. Toda nova funcionalidade que leia, altere ou baixe dados de clientes deve prever autorização e trilha de auditoria.

## Kanban e labels

Crie um GitHub Project com as colunas: **Backlog**, **Ready**, **In progress**, **In review**, **Blocked** e **Done**. Cada item deve ser uma issue. Labels recomendadas:

- Tipo: `type: feature`, `type: bug`, `type: chore`, `type: security`.
- Área: `area: api`, `area: web`, `area: infra`, `area: docs`.
- Prioridade: `priority: mvp`, `priority: next`, `priority: future`.
- Estado: `status: triage`, `status: ready`, `status: blocked`.

Configure automações do Project para mover issues abertas para **Backlog**, itens atribuídos para **In progress**, PR aberto para **In review** e issues fechadas para **Done**.

## Dependências e vulnerabilidades

Não usamos atualização automática de dependências por pull request. Em uma rotina de manutenção ou antes de atualizar uma biblioteca, execute `just audit`. Corrija vulnerabilidades prioritárias em uma issue/PR próprio; versões novas listadas pelo comando são informativas e só devem ser adotadas após o time avaliar compatibilidade, changelog e impacto.

## Shell Windows

O código em `apps/desktop` só pode ser alterado em branch baseada em `develop` e
precisa de aprovação de outro integrante antes do merge. O Rust inicia a API
empacotada como recurso `onedir`, envia um segredo por `stdin` uma única vez e
entrega a capability efêmera à janela somente por IPC. Não exponha segredo,
capability ou caminho privado em URL, argumentos, `.env`, logs, arquivos ou
`localStorage`. O build/instalador real roda no job Windows do GitHub Actions;
não versione o sidecar ou artefatos de `target/`.

## Banco de dados e migrations

Copie `.env.example` para `.env` antes de executar comandos de banco. A ADR 0003
define SQLite em arquivo como banco de desenvolvimento e entrega, implementado
na #54. Os alvos PostgreSQL existentes são apenas legados; não crie
funcionalidades persistentes novas sobre eles. Nunca edite a tabela
`alembic_version` manualmente, nunca aplique migration de produção por este
repositório sem autorização explícita e nunca gere migrations sem revisar o diff
produzido.

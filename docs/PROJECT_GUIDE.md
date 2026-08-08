# Guia de trabalho do Delta Force CRM

## Organização do monorepo

| Área | Responsabilidade |
| --- | --- |
| `apps/api` | API, regras de negócio, persistência, integrações e testes Python. |
| `apps/web` | Interface interna, experiência do operador e testes TypeScript. |
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
| `just web-check` | Prettier, ESLint, tipos e testes do web. |
| `just infra-up` | Sobe PostgreSQL, MinIO e Mailpit localmente. |
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

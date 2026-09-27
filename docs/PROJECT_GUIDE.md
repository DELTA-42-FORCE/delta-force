# Guia de trabalho do Delta Force CRM

## Organização do monorepo

| Área | Responsabilidade |
| --- | --- |
| `apps/api` | API, regras de negócio, persistência, integrações e testes Python. |
| `apps/web` | Interface interna, experiência do operador e testes TypeScript. |
| `apps/desktop` | Shell Tauri Windows, sidecar FastAPI e build do instalador. |
| `infra` | Recursos locais que simulam dependências externas. |
| `docs` | Requisitos, decisões arquiteturais e material operacional. |
| `.github` | Proteções de qualidade que rodam em pushes de desenvolvimento e pull requests para `main`. |

## Fluxo de Git e coordenação

`main` representa versões estáveis. `develop` integra trabalho concluído, sem PRs normais. Cada issue é reservada no GitHub Project antes da implementação: atribua ao responsável, mova para **In progress** e deixe um comentário com a branch. Isso sinaliza ao restante do time que a issue já está em andamento.

Crie uma branch curta a partir da ponta atual de `origin/develop`:

```text
feature/123-cadastro-clientes
fix/456-status-documento
chore/789-configurar-backup
```

Antes de começar, leia a issue e a documentação relacionada, confira se não há claim ativo e faça a varredura preflight definida em `skills/delta-force-development/SKILL.md`. Corrija falhas críticas, de segurança, perda de dados ou bugs reproduzíveis antes de uma nova tarefa; registre os achados não críticos fora do escopo como follow-up, sem incorporá-los automaticamente.

Implemente na branch e valide localmente:

```bash
git fetch origin
git switch -c feature/123-resumo origin/develop
just check
```

Envie a branch de trabalho para origin para disparar os checks de CI. Antes de integrar, atualize-a com `origin/develop` por rebase e rode `just check` novamente. Aguarde verdes todos os checks obrigatórios da ponta exata da branch — incluindo **Desktop Windows — sidecar and installer** para mudanças aplicáveis.

Integre sem PR apenas por fast-forward, apontando `develop` ao mesmo commit que passou pelos checks:

```bash
git fetch origin
git rebase origin/develop
just check
git push origin HEAD:develop
```

O push direto é protegido pelos status checks obrigatórios de `develop`; não use merge commit não testado, `--force`, bypass ou push se algum check estiver pendente/falho. Se `develop` avançar e o fast-forward for rejeitado, rebaseie, rode os checks novamente e só então tente de novo. Uma falha de push não autoriza contornar as proteções.

Mudanças em `apps/desktop` também precisam da aprovação de outro integrante antes da integração, registrada como comentário na issue; essa revisão curta não exige PR. Releases de `develop` para `main` continuam exigindo PR, aprovação independente e todos os checks.

## Convenções de commits e PRs

Use Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`. Mantenha branches e commits de um único objetivo. PRs são reservadas para releases/hotfixes destinados a `main`; não integre trabalho normal em `develop` por PR. Não suba arquivos `.env`, dumps de banco, documentos reais de clientes, chaves ou tokens.

## Qualidade local

| Comando | Finalidade |
| --- | --- |
| `just check` | Validação completa local antes de publicar a branch e integrar em `develop`. |
| `just audit` | Auditoria manual: Bandit, pip-audit, npm audit (web/desktop) e cargo-audit, com relatório informativo de versões novas. Requer `cargo-audit` instalado (`cargo install cargo-audit --locked`). Não atualiza dependências. |
| `just api-check` | Black, Flake8 e testes unitários da API. |
| `just api-migrate` | Durante a transição, aplica migrations no banco atualmente configurado. O alvo final é SQLite em arquivo. |
| `just api-rollback` | Reverte a última migration; use `just api-rollback base` somente em banco local descartável. |
| `just api-makemigration "descricao"` | Gera uma migration a ser revisada antes de ser aplicada. |
| `just api-test-integration` | Durante a transição, executa a integração legada; a issue SQLite deve substituí-la por testes em arquivo SQLite. |
| `just web-check` | Prettier, ESLint, tipos e testes do web. |
| `just desktop-install` | Instala a CLI e dependências do shell Tauri. |
| `just desktop-build` | No Windows, gera o sidecar PyInstaller `onedir` e o instalador NSIS de teste. |
| `just desktop-installer-smoke` | Instala o NSIS em área temporária, inicia e fecha o aplicativo, desinstala, reinstala usando o mesmo banco e comprova que os dados locais foram preservados. Requer um perfil Windows sem instalação ou dados existentes do CRM. |
| `just desktop-format-check` | Verifica a formatação Rust do shell. |
| `just desktop-test` | Executa no Windows os testes de ciclo de vida do supervisor e do Job Object. |
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

Configure automações do Project para mover issues abertas para **Backlog**, itens atribuídos para **In progress**, PR aberto para **In review** e issues fechadas para **Done**. Para trabalho sem PR, o responsável atualiza a issue para **Done** e a fecha somente depois da integração e do aceite.

## Dependências e vulnerabilidades

Não usamos atualização automática de dependências por pull request. Em uma rotina de manutenção ou antes de atualizar uma biblioteca, execute `just audit`. Corrija vulnerabilidades prioritárias em uma issue e branch próprias, integrando só após os checks; versões novas listadas pelo comando são informativas e só devem ser adotadas após o time avaliar compatibilidade, changelog e impacto.

## Shell Windows

O código em `apps/desktop` só pode ser alterado em branch baseada em `develop` e
precisa de aprovação de outro integrante antes do merge. O Rust inicia a API
empacotada como recurso `onedir`, envia um segredo por `stdin` uma única vez e
entrega a capability efêmera à janela somente por IPC. Não exponha segredo,
capability ou caminho privado em URL, argumentos, `.env`, logs, arquivos ou
`localStorage`. O build/instalador real roda no job Windows do GitHub Actions;
não versione o sidecar ou artefatos de `target/`.

### Pré-requisitos que não devem ser removidos

- O job **Desktop Windows — sidecar and installer** é a evidência obrigatória
  para mudanças no shell. Ambiente Linux não substitui seu build/teste completo.
- `beforeBuildCommand` e `beforeDevCommand` executam a partir de `apps/desktop`,
  mas `frontendDist` e `bundle.resources` em `src-tauri/tauri.conf.json` são
  resolvidos relativamente a `src-tauri/`. Portanto, o web deste monorepo usa
  `../../web/dist` como `frontendDist`.
- `src-tauri/resources/api-sidecar/.gitkeep` deve permanecer versionado. O
  diretório permite que `cargo test` valide o manifesto antes de o PyInstaller
  gerar o sidecar; apenas o binário gerado continua ignorado.
- `src-tauri/icons/icon.ico` e os formatos derivados devem permanecer
  versionados: Windows exige o ícone no `tauri-build`. Para trocar o desenho,
  altere o SVG-fonte e execute `npm --prefix apps/desktop exec tauri icon
  apps/desktop/src-tauri/icons/icon.svg`.

## Banco de dados e migrations

Copie `.env.example` para `.env` antes de executar comandos de banco. A ADR 0003
define SQLite em arquivo como banco de desenvolvimento e entrega, implementado
na #54. Os alvos PostgreSQL existentes são apenas legados; não crie
funcionalidades persistentes novas sobre eles. Nunca edite a tabela
`alembic_version` manualmente, nunca aplique migration de produção por este
repositório sem autorização explícita e nunca gere migrations sem revisar o diff
produzido.

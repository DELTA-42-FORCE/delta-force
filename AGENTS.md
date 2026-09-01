# Delta Force CRM — contexto e regras para agentes e desenvolvedores

Este arquivo é a fonte de orientação obrigatória para qualquer LLM, agente ou pessoa que atue neste repositório. Leia-o antes de propor, alterar, testar ou publicar código. Em caso de conflito, as decisões aprovadas pelo cliente e os documentos em `docs/` prevalecem.

## Produto e escopo

O produto é um CRM **interno** de gestão de clientes. Ele manipulará dados pessoais e documentos sensíveis; trate essa característica como requisito de arquitetura, não como detalhe posterior.

### MVP aprovado

- Aplicativo local Windows para um único proprietário, com primeira conta e
  autenticação segura.
- Cadastro, busca, consulta e edição de clientes.
- Anexo manual, consulta, checklist, status e importação assistida de documentos
  PDF/JPEG.
- Geração da ficha cadastral em PDF.
- Mala direta com modelos de e-mail, seleção de destinatários e histórico de disparos.
- Backup/restauração por HD externo, além de trilha de auditoria para ações
  relevantes.

### Fora do MVP

- Portal, login ou envio de documentos pelo cliente.
- Gestão de múltiplos usuários internos e papéis, salvo repriorização explícita.
- Integração PagBank, cobranças, boletos, recibos, relatório financeiro e nota fiscal.
- IA para validar documentos ou renegociação de dívida.

Não implemente item fora do MVP sem issue e decisão explícita. As decisões
confirmadas estão em `docs/CLIENT_DECISIONS.md` e o caminho de entrega em
`docs/MVP_PLAN.md`. Regras ainda pendentes — tamanho máximo de upload,
arquitetura de entrega local, criptografia do backup e provedor de e-mail —
estão no backlog. Não as invente: registre a dependência e peça definição.

## Fontes de verdade

1. `docs/levantamento_requisitos_crm.pdf`: levantamento consolidado do cliente.
2. `docs/BACKLOG.md`: backlog derivado do levantamento, dependências e aceite.
3. `docs/PROJECT_GUIDE.md`: fluxo de Git, PR, qualidade e Kanban.
4. `docs/ARCHITECTURE.md`: fronteiras arquiteturais.
5. `docs/CLIENT_DECISIONS.md`: respostas confirmadas posteriormente pelo cliente.
6. `docs/MVP_PLAN.md`: sequência de entrega e dependências do MVP local.
7. A issue vinculada e as decisões aprovadas no pull request.

## Stack definida

| Camada | Tecnologia |
| --- | --- |
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2, driver SQLite assíncrono, Alembic, `uv`, Black, Flake8 e pytest. |
| Frontend | React 19, TypeScript, Vite, ESLint, Prettier e Vitest. |
| Dados | SQLite em arquivo, no desenvolvimento e no aplicativo Windows. |
| Documentos | Filesystem privado; o banco guarda somente metadados. |
| E-mail local | Mailpit, somente quando a issue de e-mail o exigir. |
| Infra local | Não requer Docker, PostgreSQL ou MinIO. |
| Automação | `just` e GitHub Actions; auditoria manual de dependências. |

A decisão de SQLite foi implementada na issue #54, com SQLite em arquivo como
alvo de desenvolvimento e entrega. A cobertura PostgreSQL restante é legada e
opcional; não crie funcionalidade persistente nova sobre detalhes de PostgreSQL.
O shell e o empacotamento Windows estão definidos na ADR 0002 da issue #43.
Não troque bibliotecas-base, gerenciadores de dependência ou banco de dados sem
ADR em `docs/adr/` e aprovação do time. Dependências devem ser adicionadas apenas
quando uma issue justificar seu uso e os lockfiles correspondentes devem ser atualizados.

### Guardrails do shell Windows

- Em mudanças de `apps/desktop`, considere o job **Desktop Windows — sidecar and
  installer** obrigatório; não declare a entrega pronta antes de ele concluir com
  sucesso. O ambiente Linux não substitui essa prova.
- Em `apps/desktop/src-tauri/tauri.conf.json`, `frontendDist` e os recursos do
  bundle são resolvidos a partir de `src-tauri/`, enquanto os comandos
  `beforeBuildCommand`/`beforeDevCommand` partem de `apps/desktop`. Para o web
  deste monorepo, use `frontendDist: "../../web/dist"`; não mude esse caminho sem
  validar o bundle Windows.
- Preserve `src-tauri/resources/api-sidecar/.gitkeep`. O sidecar PyInstaller é
  gerado e ignorado pelo Git, mas o diretório precisa existir para `cargo test`
  validar o manifesto Tauri antes do build.
- Preserve o conjunto versionado em `src-tauri/icons/`, especialmente
  `icons/icon.ico`: o `tauri-build` no Windows exige esse ícone. Se ele for
  alterado, regenere os formatos pelo comando oficial `tauri icon`; não use
  imagens ou dados reais.

Não há atualização automática de dependências por pull request. Execute `just audit` periodicamente ou antes de uma atualização: ele falha em vulnerabilidades de código/dependências e lista versões novas apenas para decisão explícita do time.

## Organização do repositório

```text
apps/api/       API FastAPI e testes Python
apps/web/       Interface React/TypeScript e testes
infra/          recursos locais transitórios e serviços auxiliares opcionais
docs/           Requisitos, backlog, arquitetura e decisões
.github/        CI e templates de colaboração
```

Na API, evolua para as fronteiras `domain`, `application`, `infrastructure` e `presentation` conforme os casos de uso reais forem implementados. Regras de negócio não pertencem às rotas HTTP, componentes React, ORM ou SDKs externos. Não crie uma camada vazia apenas para simular arquitetura.

## Regras não negociáveis de segurança e LGPD

- Nunca use, versiona, anexe a issue ou exponha dados reais de clientes, documentos, tokens, senhas, chaves, dumps ou arquivos `.env`.
- Use dados sintéticos em testes, seeds, screenshots e exemplos.
- Todo recurso de cliente, documento ou histórico deve exigir autenticação e autorização no servidor; esconder uma ação no frontend não é controle de acesso.
- Toda consulta, criação, alteração e download relevante precisa ser considerada para auditoria.
- Documentos devem ficar fora do banco, em armazenamento privado; não devem ser servidos por URL pública permanente.
- Valide tipo, tamanho, nome e conteúdo aceito no upload. Não confie em extensão enviada pelo navegador.
- Não execute comandos destrutivos, migrações de produção, deploys, alterações de permissões externas ou envios de e-mail sem pedido explícito e confirmação do alvo.

## Forma de trabalhar

1. Leia a issue, este arquivo e os documentos relacionados antes de mudar código.
2. Confirme o escopo, as dependências e os critérios de aceite. Se faltar uma regra de negócio, pare e peça a decisão; não adivinhe.
3. Trabalhe em branch curta, originada de `develop`: `feature/<issue>-<resumo>`, `fix/<issue>-<resumo>` ou `chore/<issue>-<resumo>`.
4. Antes de codificar e antes de solicitar revisão, sincronize com `origin/develop` usando rebase.
5. Execute a verificação aplicável e não marque uma tarefa como pronta sem evidência.

```bash
git fetch origin
git rebase origin/develop
just check
```

O projeto configura `pull.rebase=true`, `rebase.autoStash=true` e `fetch.prune=true`. Em caso de rebase já publicado, use somente `git push --force-with-lease`, nunca `--force` simples.

## Qualidade e definição de pronto

- `just api-check`: Black, Flake8 e testes unitários da API.
- `just web-check`: Prettier, ESLint, TypeScript e Vitest.
- `just workspace-check`: whitespace do Git e configuração do Docker Compose.
- `just check`: todas as verificações acima.

Cada entrega deve ter testes proporcionais ao risco: unidade para regra de negócio, integração para persistência/autorização/armazenamento e teste de interface para fluxos críticos. Corrija a causa do problema; não desative testes, lint ou checks para fazê-los passar. Atualize documentação, migrations, contratos de API e `.env.example` quando a alteração exigir.

## Git, PRs e Kanban

- `main` contém versões estáveis; `develop` integra trabalho aprovado.
- Pull requests normais apontam para `develop`, referenciam a issue (`Closes #123`) e usam squash merge após aprovação.
- Use Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:` ou `chore:`.
- Mantenha PRs pequenos, coesos e revisáveis; não misture refatoração ampla com mudança funcional sem motivo.
- Atualize o item no GitHub Project: Backlog → Ready → In progress → In review → Done. Use **Blocked** quando uma decisão externa impedir avanço.

## Convenções por camada

### API

- Tipagem explícita, validação na borda e respostas/erros consistentes.
- Rotas ficam finas; casos de uso concentram fluxo de negócio; adaptadores de banco, e-mail e objetos ficam isolados.
- Toda mudança de esquema persistente deve ter migration reversível, testes e estratégia de compatibilidade.
- Não acople regras a SQLite, filesystem, PagBank ou provedor de e-mail; use interfaces/adaptadores quando a integração entrar no escopo.

### Web

- TypeScript estrito; não introduza `any` para contornar erro de tipo.
- Estados de carregamento, vazio, erro, permissão negada e sucesso fazem parte da entrega.
- A interface não é a fonte de verdade para validação, autorização nem regra de negócio.
- Não introduza uma biblioteca visual, gerenciamento de estado global ou roteador sem necessidade demonstrada pela issue.

### Infraestrutura

- Serviços locais devem funcionar com variáveis documentadas em `.env.example`.
- Imagens e dependências precisam de versões controladas pelos lockfiles/configurações.
- Segredos ficam no provedor de deploy/CI, nunca no repositório ou logs.

## Regras de revisão de código

Sinalize e corrija antes do merge, em especial:

- acesso a cliente/documento sem autorização no backend;
- exposição de dados pessoais, logs sensíveis ou links públicos de documentos;
- regra de negócio duplicada ou implementada somente no frontend;
- ausência de auditoria em ação relevante;
- alteração incompatível de API, esquema ou contrato sem migration/documentação;
- teste ausente para fluxo novo, regressão ou regra sensível;
- mudança fora do escopo da issue ou que antecipe recurso fora do MVP.

## Para agentes de IA

- Faça mudanças mínimas e verificáveis; preserve alterações de outros desenvolvedores.
- Não faça `git reset --hard`, `git checkout --`, `push --force`, exclusões amplas, commits, pushes, criação de PR/issues ou chamadas externas sem autorização explícita do solicitante.
- Não use credenciais fornecidas em conversa. Oriente o uso de integrações autorizadas ou tokens com menor privilégio, sem exibi-los.
- Ao concluir, informe arquivos alterados, verificações executadas, limitações e decisões que ainda exigem o time.

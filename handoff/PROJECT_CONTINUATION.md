# Delta Force CRM — continuidade do projeto

Atualizado em **22 de agosto de 2026**. Esta branch transfere contexto entre
Thiago, Caio, Vergueiro e outros agentes. Ela não é uma feature e não deve ser
mesclada automaticamente em `develop`.

## Regras obrigatórias

1. Ler `AGENTS.md`, a issue e os documentos relacionados antes de editar.
2. Usar somente dados sintéticos; nunca versionar PII, documento real, segredo,
   token, senha, `.env` ou dump.
3. Não implementar campo, tamanho, tipo documental, criptografia, provedor ou
   arquitetura ainda pendente por hipótese.
4. Não fazer merge automático. Thiago autorizou commits, pushes, abertura de PR
   e pedidos de revisão, mas não autorizou merge.
5. Preservar alterações alheias. O `package-lock.json` não rastreado na raiz do
   checkout Windows pertence ao ambiente de Thiago e não deve ser tocado.

## Estado remoto confirmado

Repositório: <https://github.com/DELTA-42-FORCE/delta-force>

| Linha | Branch/PR | Head | Estado |
| --- | --- | --- | --- |
| Base integrada | `develop` | `c111f0c` | #41, #50, #51, #52 e #53 já mescladas pelo time |
| Arquitetura #43 | `chore/43-arquitetura-windows`, PR #48 | `7f7d6a9` | mergeável; 5 checks verdes; nova revisão de Caio pendente |
| Spike #43 | `chore/43-windows-spike`, PR #49 | `5539583` | conflicting, changes requested, sem CI; manter isolada |
| Backup #44 | `chore/44-backup-design` | `98f29bb` antigo | proposta empilhada na ADR antiga; não integrar/rebasear ainda |
| Remetente #46 | `feature/46-remetente-homologacao` | `deedc02` | sem PR; aguarda e-mail/provedor do cliente |
| Preview local | `chore/integration-preview-20260822` | descartável | obsoleta após os merges; não publicar |

Só existem duas PRs abertas: #48 e #49.

## Produto já desenvolvido em `develop`

### Autenticação do proprietário

- primeira conta criada por fluxo de setup;
- login, sessão por bearer, logout e revogação;
- somente hash do token persistido;
- token mantido em memória na interface, nunca em `localStorage`;
- tela responsiva de primeiro acesso, login e área do proprietário.

### Auditoria

- migration e trilha append-only;
- eventos de setup, login, perfil, logout, negações e consultas;
- contexto allowlisted sem senha, token/hash ou PII submetida;
- `GET /audit/events` autenticado com cursor keyset;
- painel “Atividade recente” e histórico completo;
- paginação, carregar mais e filtros server-side por ação/resultado;
- estados de loading, vazio, erro/retry e sucesso.

### Catálogo em homologação

A PR #53 integrou a proposta e `docs/QUESTIONARIO_CATALOGO_CLIENTE.md`, mas não
homologou os campos. A issue #14 continua `status: blocked`. Não criar schema de
cliente a partir da expressão “dados pedidos pelo gov.br”.

## Trabalho executado na PR #48

Caio pediu quatro correções: separar fatos/hipóteses, comparar uma solução menor,
fechar a transição PostgreSQL → SQLite e devolver assinatura/update/backup a
gates futuros. O commit `7f7d6a9` atende esses pontos:

- `docs/CLIENT_DECISIONS.md` foi restaurado aos fatos confirmados em `develop`;
- `docs/ARCHITECTURE.md` não publica mais a proposta como arquitetura vigente;
- `docs/MVP_PLAN.md` contém gates, não uma cadeia customizada já decidida;
- a ADR 0002 caiu de 530 para cerca de 357 linhas;
- a proposta é Tauri direto + React + FastAPI/PyInstaller `onedir` +
  SQLite/filesystem, condicionada ao aceite técnico;
- launcher separado, updater, manifesto assinado e protocolo A/B/gerações foram
  removidos do MVP;
- shell Python/WebView, Electron, navegador/PWA e PostgreSQL/MinIO locais foram
  comparados com custo recorrente de build, CI e suporte;
- o time precisa nomear responsável por Rust/Tauri e CI Windows antes do aceite;
- computador/Windows final, proteção do disco, assinatura/custódia, WebView2 e
  proteção/recuperação do backup permanecem pendentes;
- a ADR 0001 deverá ser limitada ao desenvolvimento/transição no mesmo commit que
  aceitar a ADR 0002.

Pedido de nova revisão:
<https://github.com/DELTA-42-FORCE/delta-force/pull/48#issuecomment-5382896982>

### Compatibilidade SQLite comprovadamente pendente

A investigação executou a cadeia Alembic real contra SQLite:

- `0001` e `0002` passam;
- `20260819_0003_hash_session_tokens.py` falha com
  `NotImplementedError` ao alterar/remover/criar constraints sem batch mode.

Outros gaps atuais:

- `core/config.py` aceita apenas `postgresql+psycopg://`;
- não existe driver SQLite assíncrono no produto;
- modelos/migrations usam UUID específico do PostgreSQL;
- setup concorrente usa `pg_advisory_xact_lock`;
- o engine não habilita `PRAGMA foreign_keys=ON`;
- CI e integração são PostgreSQL-only;
- o smoke da #49 usa tabelas artificiais e não prova migrations/modelos do CRM.

Não existe banco PostgreSQL do cliente. A primeira instalação deverá criar um
SQLite vazio e portar toda a cadeia. Se surgir banco real antes da entrega, será
necessária issue separada de exportação/importação, integridade e rollback.

Gates registrados na ADR:

- `upgrade base → head` e preservação de dados em PostgreSQL e SQLite de arquivo;
- UUID, UTC, índices, checks, FKs/cascatas, paginação e auditoria em ambos;
- setup concorrente com exatamente um `201`, um `409` e um proprietário;
- `integrity_check=ok`, `foreign_key_check` vazio e `alembic_version=head`;
- reinício idempotente após interrupção;
- fluxo empacotado em Windows limpo.

### Validação do head `7f7d6a9`

Local:

- `git diff --check`: PASS;
- Docker Compose config: PASS;
- Black (71 arquivos) e Flake8: PASS;
- pytest: 98 passed, 12 integration deselected;
- ESLint e TypeScript: PASS;
- Vitest: 23 passed;
- Prettier local acusa CRLF em arquivos web não alterados;
- integração PostgreSQL local não rodou porque o daemon Docker está desligado.

GitHub Actions: cinco checks verdes, incluindo integração PostgreSQL e gate web
com Prettier. A PR está mergeável, mas ainda aguarda nova revisão humana.

## PR #49: não mexer agora

A #49 ficou `CONFLICTING` depois do rebase correto da #48. Isso é esperado e não
deve ser “consertado”: Caio pediu que o protótipo permaneça fora do produto. Não
rebasear, retargetar, resolver conflitos ou incorporar seus lockfiles.

Após a ADR ser aceita, o time deve escolher uma destas opções:

1. manter apenas relatório sanitizado/digest e referência ao commit na issue #43;
2. mover o experimento integral para repositório separado;
3. criar uma nova PR mínima, baseada em `develop`, com CI e issue própria.

## Bloqueios atuais

| Dependência | Bloqueia | Ação para liberar |
| --- | --- | --- |
| revisão/aceite da #48 | implementação desktop/SQLite e #44 | Caio revisar; Thiago autorizar eventual merge |
| catálogo #14 | #18–#23, #34 e #45 | cliente responder todo o questionário e time homologar |
| tamanho máximo PDF/JPEG | upload/importação | cliente/time definir limite explícito |
| remetente/provedor #46 | #24/#25 | cliente informar conta e produto, sem enviar senha/token |
| proteção/recuperação do backup | #44 e dados reais | decisão própria da #44 + revisão criptográfica |
| equipamento final | release/dados reais | inspeção e decisão de Windows/proteção em #27 |

Todos os módulos funcionais restantes do MVP estão marcados `blocked`, exceto a
#27, que é aceite de ponta a ponta e deve ocorrer no final. Portanto, não existe
agora uma feature de cliente/documento segura para codar sem uma resposta externa.

## Ordem recomendada

1. Monitorar a nova revisão da #48 e tratar somente achados objetivos.
2. Se Caio aprovar, avisar Thiago; não fazer merge sem autorização explícita.
3. Após merge autorizado, criar issue de implementação desktop/SQLite baseada em
   `develop`; não partir da PR #49.
4. Enviar ao cliente o questionário #14 e obter o remetente/provedor #46.
5. Homologar #14; implementar #18, depois #19 e #20.
6. Implementar armazenamento/documentos (#21/#22/#23), importação #45 e ficha PDF
   #34 somente após campos/tipos/tamanho estarem fechados.
7. Repropor #44 sem assumir recovery code/algoritmo; obter revisão criptográfica.
8. Implementar modelos/envio de e-mail (#24/#25) após homologar #46.
9. Finalizar operação/LGPD #26 e aceite Windows #27 por último.

## Comandos de retomada

```powershell
git fetch origin --prune
git status --short --branch
git worktree list
git log --oneline --decorate -8 origin/develop
gh pr view 48 --repo DELTA-42-FORCE/delta-force
gh pr checks 48 --repo DELTA-42-FORCE/delta-force
gh pr view 49 --repo DELTA-42-FORCE/delta-force
gh issue list --repo DELTA-42-FORCE/delta-force --state open --limit 100
```

Para continuar a #48 se houver novo review:

```powershell
git fetch origin --prune
git switch chore/43-arquitetura-windows
git rebase origin/develop
# corrigir somente os achados e executar os gates
git push --force-with-lease
```

Antes de qualquer push reescrito, conferir `git status`, `git log --graph` e a
ponta remota. Nunca usar `--force` simples.

## Arquivos auxiliares desta branch

- `handoff/VERGUEIRO_START_HERE.md`
- `handoff/issue-drafts/24.md`
- `handoff/issue-drafts/25.md`
- `handoff/issue-drafts/27.md`
- `handoff/pr-bodies/14-catalog.md`
- `handoff/pr-bodies/15-auth-web.md`
- `handoff/pr-bodies/17-audit.md`
- `handoff/pr-bodies/43-spike.md`
- `handoff/pr-bodies/46-sender.md`
- `handoff/review-notes/41-rereview.md`
- `handoff/review-notes/48-and-spike.md`

Os rascunhos antigos são histórico; leia o estado remoto antes de reutilizá-los.

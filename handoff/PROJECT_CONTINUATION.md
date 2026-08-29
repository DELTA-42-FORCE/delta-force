# Delta Force CRM — continuidade do projeto

Atualizado em **29 de agosto de 2026**. Esta branch transfere contexto entre
Thiago, Caio, Vergueiro e outros agentes. Ela não é uma feature e não deve ser
mesclada automaticamente em `develop`.

## Regras obrigatórias

1. Ler `AGENTS.md`, a issue e os documentos relacionados antes de editar.
2. Usar somente dados sintéticos; nunca versionar PII, documento real, segredo,
   token, senha, `.env` ou dump.
3. Não inventar limite de arquivo, criptografia/proteção do backup ou provedor de
   e-mail.
4. Não fazer merge automático. Thiago autorizou commits, pushes, PRs e pedidos
   de revisão, mas não autorizou merge.
5. Preservar alterações alheias. O `package-lock.json` não rastreado na raiz do
   checkout Windows não deve ser tocado.

## Estado remoto confirmado

Repositório: <https://github.com/DELTA-42-FORCE/delta-force>

| Linha | Branch/PR | Head | Estado |
| --- | --- | --- | --- |
| Base integrada | `develop` | `2384618` | autenticação, web, auditoria, ADR 0003 e pasta flexível |
| Arquitetura #43 | `chore/43-arquitetura-windows`, PR #48 | `437c352` | conflicting/changes requested; sincronização final pedida por Caio |
| Spike #43 | `chore/43-windows-spike`, PR #49 | `5539583` | isolada; não integrar |
| SQLite #54 | issue aberta | branch remota homônima ainda aponta ao merge documental | pronta para implementação baseada no `develop` atual |
| Backup #44 | `chore/44-backup-design` | `98f29bb` antigo | proposta desatualizada; não integrar/rebasear ainda |
| Remetente #46 | `feature/46-remetente-homologacao` | `deedc02` | aguarda conta/provedor |

As únicas PRs abertas em 29/08 são #48 e #49.

## Produto já desenvolvido em `develop`

### Autenticação do proprietário

- primeira conta criada por fluxo de setup;
- login, sessão bearer, logout e revogação;
- somente hash do token persistido;
- token mantido em memória na interface;
- telas de primeiro acesso, login e área do proprietário.

### Auditoria

- trilha append-only;
- eventos de setup, login, perfil, logout, negações e consultas;
- contexto allowlisted sem senha, token/hash ou PII submetida;
- consulta autenticada com cursor;
- painel de atividade recente e histórico com filtros/paginação.

### Decisões de produto e persistência

- SQLite em arquivo é o banco no desenvolvimento e na entrega;
- documentos ficam em filesystem privado, com metadados no banco;
- Docker, PostgreSQL e MinIO deixam de ser pré-requisitos após a transição #54;
- o CRM é uma pasta digital flexível: nome é o único campo obrigatório para criar
  cliente; demais dados e documentos são opcionais;
- somente PDF e JPEG serão aceitos, mas o limite máximo continua pendente;
- importação assistida deve considerar aproximadamente 500 documentos antigos,
  30 a 40 novos e possíveis arquivos corrompidos;
- ficha cadastral em PDF faz parte do MVP;
- backup será em HD externo; remetente de e-mail ainda não foi informado.

## Última decisão do Caio na PR #48

Caio confirmou:

- **Tauri 2 direto + React + FastAPI empacotada como sidecar + SQLite**;
- Tauri cuida apenas da janela, supervisor do sidecar e integrações nativas
  indispensáveis;
- regras de negócio, autenticação, auditoria e acesso a dados ficam no FastAPI;
- instalação manual simples, sem launcher, atualizador próprio ou protocolo de
  gerações;
- toda PR que alterar Tauri/CI Windows deve ter autor responsável e revisão de
  outro integrante;
- a PR #49 é somente experimento e deve ser fechada sem merge após o aceite.

Antes da aprovação final da ADR 0002, Caio pediu:

1. rebase da PR #48 após a PR #55;
2. referência à ADR 0003 e à issue #54;
3. PostgreSQL descrito apenas como fundação legada a remover;
4. #54 responsável por driver, migrations, autenticação, auditoria, comandos e
   CI SQLite;
5. #43 responsável somente por shell, sidecar, diretórios, primeira execução,
   instalador e lifecycle Windows;
6. substituição do especialista Rust fixo pela regra de colaboração acima;
7. proibição explícita de merge/reuso de lockfiles da #49.

## Próximo recorte de código: issue #54

A ADR 0003 está aceita e a issue #54 está `status: ready`. Ela antecede novas
entidades persistentes de cliente/documento e exige:

- driver SQLite assíncrono e URL segura para arquivo local;
- UUIDs, índices, FKs, timestamps e migrations portáveis;
- correção da migration de hash de sessão para SQLite;
- substituição do advisory lock PostgreSQL por garantia transacional compatível;
- exatamente um proprietário em duas tentativas concorrentes de setup;
- `foreign_keys=ON`, WAL, timeout de lock e `synchronous=FULL`;
- upgrade `base → head`, preservação dos dados sintéticos, reopen,
  `integrity_check` e `foreign_key_check`;
- autenticação e auditoria funcionando em SQLite;
- comandos e CI sem exigir Docker, PostgreSQL ou MinIO.

Não usar código, dependências ou lockfiles da spike #49 na #54.

## Ordem de implementação do MVP

1. Corrigir/rebasear a PR #48 e pedir nova revisão, sem merge automático.
2. Implementar #54 em branch curta nascida do `origin/develop`.
3. Implementar #18 e #19: modelo, API e telas da pasta flexível de clientes.
4. Implementar #21/#22/#23: filesystem privado, PDF/JPEG e checklist, somente
   após definir o limite máximo.
5. Implementar importação #45 e ficha PDF #34.
6. Implementar #24/#25 após definir remetente/provedor #46.
7. Reespecificar e implementar backup/restauração #44 após decisão de proteção.
8. Finalizar operação/LGPD #26 e aceite Windows ponta a ponta #27.

## Bloqueios restantes

| Dependência | Bloqueia | Ação |
| --- | --- | --- |
| limite máximo PDF/JPEG | liberação de upload/importação | cliente/time definir bytes ou MiB |
| remetente/provedor #46 | #24/#25 | cliente informar conta/provedor, sem senha no Git |
| proteção/recuperação do backup | #44 | decisão e revisão de segurança |
| aprovação final da PR #48 | integração definitiva do shell | aplicar ajustes e Caio revisar |
| equipamento Windows final | release/aceite #27 | validar instalação limpa e diretórios |

Cadastro básico pode avançar depois da #54 porque a pasta flexível já foi
aprovada. Não é necessário voltar ao catálogo rígido de campos do gov.br.

## Comandos de retomada

```powershell
git fetch origin --prune
git status --short --branch
git worktree list
git log --oneline --decorate -8 origin/develop
gh pr view 48 --repo DELTA-42-FORCE/delta-force
gh pr view 49 --repo DELTA-42-FORCE/delta-force
gh issue view 54 --repo DELTA-42-FORCE/delta-force
gh issue list --repo DELTA-42-FORCE/delta-force --state open --limit 100
```

Para tratar a PR #48:

```powershell
git fetch origin --prune
git switch chore/43-arquitetura-windows
git rebase origin/develop
# aplicar somente os ajustes do último comentário do Caio
just check
git push --force-with-lease
```

Antes do push reescrito, conferir o head remoto e o lease. Nunca usar
`--force`. O merge continua dependendo de autorização explícita de Thiago.

Para a #54, partir de `origin/develop` em branch própria, implementar por etapas
reversíveis e executar testes proporcionais de migration, concorrência,
persistência e reinício. Ao parar, registrar branch, commit, testes, limitações e
o próximo comando neste handoff.

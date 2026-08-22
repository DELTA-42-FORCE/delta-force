# Delta Force CRM — continuidade do projeto

Atualizado em **22 de agosto de 2026**. Esta branch existe para transferir
contexto entre pessoas ou agentes. Ela não é uma feature e **não deve ser
mesclada automaticamente em `develop`**.

## Regras antes de continuar

1. Ler `AGENTS.md`, `docs/CLIENT_DECISIONS.md`, `docs/MVP_PLAN.md`,
   `docs/BACKLOG.md` e a issue trabalhada.
2. Usar somente dados sintéticos. Nunca colocar cliente real, documento,
   endereço de e-mail, senha, token, chave, `.env` ou dump no GitHub.
3. Preservar alterações alheias e executar os gates proporcionais ao risco.
4. Não implementar regra pendente por hipótese.
5. O `package-lock.json` não rastreado que existe em um checkout Windows é
   alheio ao projeto e nunca deve ser adicionado.

## Estado remoto confirmado

| Linha            | Branch/PR                                 | Commit    | Estado em 22/08/2026                                                 |
| ---------------- | ----------------------------------------- | --------- | -------------------------------------------------------------------- |
| Base             | `develop`                                 | `6cb9ac5` | base atual das linhas documentais                                    |
| Autenticação #15 | `feature/15-autenticacao-backend`, PR #41 | `d2d2a86` | 5 checks verdes; revisão antiga ainda aparece como changes requested |
| Auditoria #17    | `feature/17-auditoria`                    | `2671d11` | publicada e empilhada sobre #15; sem PR                              |
| Arquitetura #43  | `chore/43-arquitetura-windows`, PR #48    | `101981c` | 5 checks verdes; sem aprovação técnica                               |
| Spike #43        | `chore/43-windows-spike`                  | `5539583` | publicado e empilhado sobre a arquitetura; sem PR                    |
| Catálogo #14     | `feature/14-catalogo-homologacao`         | `3c9efd1` | questionário/registro publicados; aguarda cliente                    |
| Remetente #46    | `feature/46-remetente-homologacao`        | `deedc02` | questionário/registro publicados; aguarda provedor                   |

Repositório: <https://github.com/DELTA-42-FORCE/delta-force>

## Evidência já obtida

### Autenticação #15

A ponta atual da branch resolve os três bloqueios da revisão antiga:

- primeira conta do proprietário por setup seguro;
- somente hash do token de sessão no banco;
- fluxo web de setup/login/logout utilizável sem `localStorage`.

A PR #41 continua precisando de nova revisão humana. Não reescrever a branch
enquanto a #17 estiver empilhada nela sem planejar ambos os rebases.

### Auditoria #17

- migration reversível `20260820_0004`;
- trilha append-only com contexto allowlisted;
- eventos de setup, login, perfil, logout, negações e consulta da trilha;
- commit atômico entre mutação de autenticação e evento;
- `GET /audit/events` autenticado, com cursor keyset estável;
- sem senha, token/hash, e-mail submetido ou outra PII no contexto técnico.

Gate executado no commit `2671d11`:

- Black e Flake8: PASS;
- 93 testes unitários: PASS;
- 12 testes PostgreSQL/migrations: PASS.

Depois do merge da PR #41, rebasear #17 em `origin/develop`, repetir os gates e
abrir PR. A issue #17 deve continuar recebendo eventos das features futuras; não
usar `Closes #17` prematuramente.

### Windows #43

A ADR 0002 ainda está **Proposta**. O spike sintético já provou:

- React em janela Tauri e API PyInstaller `onedir`;
- loopback com porta efêmera, bootstrap one-shot e capability por execução;
- Host/Origin estritos, instância única e Job Object sem sidecar órfão;
- SQLite com invariantes de durabilidade e integridade;
- recusa de manifesto/árvore adulterados;
- relatório sanitizado ligado a digest de 38 fontes
  `b280db5793c6eecd182469b39602ccd4675b871a28ce392fdb4936cdff2dcac3`.

Faltam somente os gates formais para aceitar a ADR:

1. abrir/revisar o PR empilhado do spike;
2. obter aprovação técnica explícita;
3. registrar o aprovador e alterar a ADR para **Aceita** em mudança revisável.

Assinatura real/VM limpa (#27), DACL/TOCTOU (#21), backup (#44) e inspeção do
notebook definitivo são gates posteriores. Eles bloqueiam distribuição ou dados
reais, não a decisão arquitetural.

### Catálogo #14

Enviar ao cliente o arquivo
`docs/QUESTIONARIO_CATALOGO_CLIENTE.md` da branch publicada. A implementação de
schema/API/UI de clientes, documentos, importação e ficha PDF permanece
bloqueada até todas as respostas serem homologadas no registro técnico.

### Remetente #46

Enviar ao cliente `docs/QUESTIONARIO_REMETENTE_CLIENTE.md`. Não pedir senha,
token, MFA, endereço real ou lista de clientes no GitHub/chat. Depois de saber o
provedor/produto, preencher o registro usando somente documentação oficial. O
envio real permanece bloqueado; Mailpit continua exclusivo do desenvolvimento.

## Ordem recomendada

1. Solicitar nova revisão da PR #41 e responder aos três pontos antigos com
   evidência da ponta atual.
2. Abrir PR empilhado do spike #43 contra `chore/43-arquitetura-windows` e pedir
   revisão técnica conjunta com a PR #48.
3. Enviar os questionários #14 e #46 ao cliente.
4. Reconciliar no GitHub as issues #24, #25 e #27 usando os rascunhos desta
   branch, após nova leitura do estado remoto.
5. Quando #15 for integrada, rebasear/publicar #17.
6. Quando a ADR #43 for aceita, criar/vincular a issue de implementação
   desktop/SQLite e então definir a ADR criptográfica da #44.
7. Depois da homologação #14: #18/#19/#20, depois #21/#22/#23/#45/#34.
8. Depois da homologação #46 e da #24: implementar #25; fechar #26 e #27 por
   último.

## Arquivos auxiliares desta branch

- `handoff/issue-drafts/24.md`
- `handoff/issue-drafts/25.md`
- `handoff/issue-drafts/27.md`
- `handoff/pr-bodies/14-catalog.md`
- `handoff/pr-bodies/17-audit.md`
- `handoff/pr-bodies/46-sender.md`
- `handoff/pr-bodies/43-spike.md`
- `handoff/review-notes/41-rereview.md`
- `handoff/review-notes/48-and-spike.md`

Antes de usar um rascunho, ler novamente a issue remota e preservar qualquer
mudança feita depois desta data.

## Comandos iniciais

```powershell
git fetch origin --prune
git status --short --branch
git worktree list
gh pr view 41 --repo DELTA-42-FORCE/delta-force
gh pr view 48 --repo DELTA-42-FORCE/delta-force
```

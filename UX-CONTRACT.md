# UX Contract

## Product context

- Audience: proprietário único do CRM.
- Primary jobs: organizar clientes/documentos e executar comunicações com
  rastreabilidade.
- Target market and active locale: Brasil, `pt-BR`.
- Timezone/calendar: datas civis quando o domínio não exige instante; exibição
  local em `pt-BR`.
- Accessibility target: WCAG 2.2 AA.

## Business-context sources

| Domínio | Fonte autoritativa | Tipo | Revisão |
|---|---|---|---|
| Produto e dados | `docs/CLIENT_DECISIONS.md` | Decisões do cliente | 2026-09-20 |
| Escopo e aceite | `docs/MVP_PLAN.md` e issue vinculada | Plano/backlog | 2026-09-20 |
| Segurança e permissão | `AGENTS.md` e `docs/ARCHITECTURE.md` | Política/arquitetura | 2026-09-20 |
| E-mail | `docs/adr/0005-adaptador-e-credencial-de-email.md` | ADR | 2026-09-20 |

## Visual contract

- Project `DESIGN.md`: `DESIGN.md`.
- Token ownership: `apps/web/src/App.css` é o runtime canônico; `DESIGN.md`
  documenta intenção e valores estáveis.
- Theme: claro; nenhum tema escuro está prometido no MVP.

## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Select/Listbox | elemento HTML `select` | este contrato | nativo Windows/WebView | teclado + testes de fluxo |
| Date | elemento HTML de data | este contrato e regra de domínio | nativo | locale + testes de regra |
| Form | componente de tela + validação API | este contrato | criar/editar | testes de componente/API |
| Scrollbar | stylesheet global | `DESIGN.md` e `App.css` | geometria global | inspeção estática |
| CRUD | casos de uso/API e página da feature | issue/contrato HTTP | voltar ou permanecer conforme fluxo | integração + componente |

## Component behavior

| Componente | Padrão | Foco | Desabilitado/ocupado | Erro |
|---|---|---|---|---|
| Button | rótulo textual | anel visível | bloqueia novo submit e preserva geometria | feedback próximo |
| Input | label persistente | anel azul-petróleo | valor legível | mensagem associada |
| Secret input | mascarado, reveal explícito | igual a input | não persistir | nunca repetir segredo |
| Textarea | altura suficiente e sem redimensionamento livre | igual a input | preserva texto | mensagem associada |
| Table/list | ordem estável | ações alcançáveis | estado local | retry no mesmo lugar |

## Dataset navigation

Listas operacionais usam paginação/cursor da API, ordem estável e estados
explícitos de carregamento, vazio e erro. Seleção é da página carregada,
mostra a contagem e é limpa quando o filtro muda.

## Flow ledger

| Operação | Pending | Sucesso | Falha/recuperação |
|---|---|---|---|
| Criar/editar | botão ocupado | retorna à lista com status | preserva formulário e erro seguro |
| Excluir | confirmação contextual | remove da lista | mantém item e permite repetir |
| Buscar/listar | indicador na região | lista ou vazio | retry no mesmo bloco |
| Envio externo | revisão explícita e botão ocupado | resumo por resultado + histórico | não confundir falha de refresh com falha de envio |

## Navigation and responsive behavior

O shell preserva navegação por botões nomeados. Grades viram coluna em
larguras menores; nenhuma ação depende de hover. Truncamento deve conservar uma
forma de acessar o valor completo quando isso afetar a decisão do usuário.

## Overlays and feedback

Confirmações contextuais são preferidas a dialogs genéricos. Ações externas ou
destrutivas explicam a consequência antes do commit. Feedback usa `role=status`
ou `role=alert` e não inclui segredo nem detalhe interno.

## Async and resilience

- Mutações são pessimistas e bloqueiam submit duplicado.
- Envio de e-mail é individual e serializado no processo local; `pending`,
  sucesso e resultado desconhecido exigem confirmação antes de repetir.
- Falha ao recarregar histórico depois do envio nunca é apresentada como falha
  do transporte externo.
- Requisições obsoletas de paginação são descartadas pela tela.

## Validation

API e casos de uso são a fonte de verdade. Formulários novos/tocados usam
`noValidate`, validação inline, primeiro erro acionável e mensagens sem detalhes
privados. Fluxos legados entram em migração quando forem alterados.

## Permission and clipboard

Todos os dados funcionais exigem sessão no backend; esconder controles não é
autorização. Segredos não oferecem cópia, toast ou persistência pelo aplicativo.

## Migration status

Forms legados ainda sem `noValidate` e textareas redimensionáveis são dívida
conhecida; nenhum fluxo novo deve ampliar esse padrão. A migração ocorre por
feature, acompanhada de teste.

## Verification

- Estático: `just web-check` e auditoria premium em modo estrito.
- Runtime: Vitest/Testing Library para estados e fluxos; job Windows para shell
  e instalador.
- Evidência desta fatia: `apps/web/src/communications/CommunicationsPage.test.tsx`.

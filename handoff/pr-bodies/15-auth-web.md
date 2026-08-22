## Resumo

- transforma o fluxo existente de primeira conta, login e logout em uma
  interface responsiva e utilizável;
- adiciona estados visuais de carregamento, indisponibilidade, erro e sessão
  ativa;
- apresenta a primeira área autenticada do CRM sem simular ações ainda não
  implementadas;
- reutiliza o contrato da API da PR #41 sem adicionar dependência frontend.

## Base empilhada

Este PR usa `feature/15-autenticacao-backend` como base enquanto a PR #41 estiver
aberta. Depois que #41 for integrada, rebasear em `origin/develop`, repetir
`just web-check` e retargetar o PR.

## Segurança e comportamento

- token de sessão permanece somente em memória, sem `localStorage`;
- logout oculta a área autenticada antes de aguardar a resposta da API;
- sessão expirada e logout já revogado removem o estado local;
- nenhuma senha, token, conta real ou dado de cliente entra no código ou nos
  testes;
- Clientes, Documentos e E-mails aparecem somente como próximos módulos, sem
  botões ou chamadas falsas.

## Verificação

- Prettier nos arquivos alterados: PASS;
- ESLint: PASS;
- TypeScript: PASS;
- Vitest: 11 testes aprovados;
- build Vite de produção: PASS;
- primeiro acesso e painel inspecionados em viewport de notebook e responsivo,
  com dados sintéticos e sem erro no console.

## Limites deliberados

Cadastro de clientes, documentos, e-mail e empacotamento Windows pertencem às
issues correspondentes e não são antecipados neste PR.

Refs #15

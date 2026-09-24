---
version: alpha
name: "Delta Force CRM"
description: "Aplicativo operacional local, sóbrio e legível para organizar clientes e documentos sensíveis."
colors:
  primary: "#08758f"
  primary-soft: "#edf8fa"
  ink: "#18243a"
  muted: "#657286"
  border: "#e0e5ec"
  surface: "#ffffff"
  inset: "#f7f9fc"
  background: "#f2f5f9"
  warning: "#8a6218"
  danger: "#8d2630"
typography:
  sans:
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
rounded:
  DEFAULT: "0.65rem"
  sm: "0.5rem"
  md: "0.8rem"
  lg: "1rem"
  pill: "999px"
spacing:
  control-gap: "0.65rem"
  card-padding: "1.4rem"
  section-gap: "1.5rem"
  page-max: "76rem"
components:
  button:
    backgroundColor: "#08758f"
    textColor: "#ffffff"
    rounded: "0.65rem"
    height: "2.7rem"
  card:
    backgroundColor: "#ffffff"
    textColor: "#18243a"
    rounded: "1rem"
    padding: "1.4rem"
  input:
    backgroundColor: "#f7f9fc"
    textColor: "#18243a"
    rounded: "0.65rem"
    height: "2.7rem"
  status:
    backgroundColor: "#edf8fa"
    textColor: "#08758f"
    rounded: "999px"
---

# Delta Force CRM Design System

## Overview

### Creative North Star

O produto deve lembrar um fichário administrativo bem organizado em uma mesa de
trabalho: navegação previsível, rótulos diretos, superfícies claras e sinais de
estado discretos. O azul-petróleo identifica ações e progresso sem transformar
documentos pessoais em uma experiência promocional.

### Product context and register

- **Público e tarefa:** um único proprietário organiza clientes, documentos,
  lembretes e comunicações no próprio computador Windows.
- **Mercado e evidência:** Brasil, conforme `docs/CLIENT_DECISIONS.md`; moeda,
  datas e texto da interface usam `pt-BR`.
- **Cena de uso:** desktop Windows, uso recorrente e dados sensíveis. Clareza,
  recuperação de falhas e leitura confortável vencem densidade extrema.
- **Registro:** produto operacional. Expressão de marca fica no painel de acesso
  e no símbolo; formulários e históricos permanecem familiares.
- **Assinatura memorável:** azul-petróleo com pequenos sinais geométricos e
  indicadores de prontidão.
- **Restrição:** envios, restaurações, exclusões e dados pessoais nunca usam
  linguagem ambígua ou ornamentação que esconda consequências.
- **Anti-referências:** landing pages com gradientes decorativos em toda parte,
  dashboards genéricos cheios de cards e interfaces que dependem apenas de cor.
- **Tokens:** este arquivo documenta os tokens canônicos implementados em
  `apps/web/src/App.css`; mudanças de sistema devem atualizar ambos.

## Colors

`primary` indica foco, ação e seleção. `ink` e `muted` estabelecem hierarquia
textual; `surface`, `inset` e `background` separam camadas com borda antes de
sombra. `warning` e `danger` são semânticos e sempre acompanham texto ou ícone.
O MVP possui somente tema claro; um tema futuro deve preservar esses papéis e
contraste WCAG 2.2 AA.

## Typography

A pilha sans usa Inter quando disponível e fontes nativas do sistema como
fallback. Títulos são compactos, texto de apoio usa altura de linha confortável e
contagens/datas preservam algarismos alinhados. A interface usa português do
Brasil e evita caixa alta fora de pequenos `eyebrow` de navegação.

## Layout

Telas usam largura máxima de `76rem`, espaçamento responsivo e grades que viram
uma coluna quando a largura não comporta leitura confortável. Ações relacionadas
ficam próximas; estados de carregamento, vazio, erro e sucesso ocupam a mesma
região para evitar saltos. Formulários não dependem de hover.

## Elevation & Depth

Bordas e variações tonais são o recurso principal. Sombras sutis são reservadas
ao painel de marca, foco e superfícies que realmente se elevam. Cards estáticos
não recebem sombras pesadas nem efeito de vidro.

## Shapes

Campos e botões usam raios entre `0.5rem` e `0.8rem`; cards podem chegar a
`1rem`. Pílulas ficam restritas a status e contagens curtas. Contornos de foco
permanecem visíveis e não alteram a geometria.

## Components

### Foundational visual states

Todo fluxo deve representar carregamento, vazio, erro recuperável, sucesso,
desabilitado e ocupado. Foco usa anel azul-petróleo; erro usa texto associado e
`role="alert"`; progresso usa o indicador compartilhado e texto.

### Buttons and actions

Botão primário confirma a ação principal; secundário navega ou cancela; ação
destrutiva fica separada e exige confirmação. Durante mutação, o rótulo muda
sem alterar a largura de forma brusca e novos submits ficam desabilitados.

### Navigation and data display

Listas mantêm nome, resumo e ações em ordem consistente. Status internos são
traduzidos para linguagem humana. Valores truncados precisam de contexto ou
acesso ao valor completo quando forem relevantes para a tarefa.

### Forms and overlays

A aplicação é dona da validação (`noValidate`), associa erros ao campo e move
o foco quando necessário. Selects e datas nativos são intencionais no Windows;
o navegador controla o popup e o calendário. Segredos iniciam mascarados, podem
ser revelados e nunca aparecem em feedback, histórico ou logs.

### Iconography

O sistema atual usa símbolos geométricos simples e SVGs locais. Ícones não
substituem rótulos em ações importantes.

### Motion

Movimento comunica carregamento, foco ou transição curta; não decora operações
rotineiras. Respeite `prefers-reduced-motion` ao adicionar animação.

### Content and data visualization

O tom é direto e acolhedor, com verbos concretos. Datas usam `pt-BR`; valores
financeiros usam BRL exato. Contagens e estados sempre possuem alternativa
textual acessível.

## Do's and Don'ts

- **Faça:** mantenha consequências e recuperação visíveis antes de ações externas.
- **Faça:** reutilize tokens, estados e vocabulário existentes entre telas.
- **Não faça:** exponha nomes internos de enum, detalhes técnicos ou segredos.
- **Não faça:** use cor, animação ou cards decorativos sem função operacional.

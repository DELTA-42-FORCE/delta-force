## Resumo

- adiciona questionário seguro para fechar campos cadastrais, documentos,
  limites de upload e ficha PDF com o cliente;
- adiciona registro técnico que só pode ser homologado após respostas completas;
- mantém schema, migration, API e interface bloqueados até a decisão final.

## Segurança e privacidade

- não contém dado, documento ou identidade real;
- orienta o cliente a não enviar CPF, endereço, arquivo ou outro dado pessoal;
- não inventa limite de PDF/JPEG nem transforma a referência ao gov.br em
  schema antes da homologação.

## Verificação

- Prettier: PASS;
- `git diff --check`: PASS;
- revisões independentes de fidelidade, clareza/privacidade e
  implementabilidade: PASS.

## Estado da issue

Este PR **não fecha #14**. Depois da revisão documental, o questionário ainda
precisa ser respondido pelo cliente e transcrito no catálogo aprovado. Somente
essa homologação libera #18/#21/#34.

Refs #14

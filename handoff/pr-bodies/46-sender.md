## Resumo

- adiciona questionário seguro para identificar provedor/produto, identidade
  visível, finalidade documental, volume e comportamento de falha/reenvio;
- adiciona registro técnico para transporte TLS, autenticação/OAuth, limites,
  idempotência, logs, restauração e testes;
- mantém credenciais, endereço real e configuração do adaptador fora do Git.

## Segurança e privacidade

- proíbe senha, token, chave de API, MFA, acesso DNS, endereço/lista real e
  screenshots sensíveis no questionário ou repositório;
- exige TLS sem downgrade, validação de cadeia/hostname e OAuth desktop com
  PKCE/`state` quando aplicável;
- separa histórico funcional protegido de logs técnicos allowlisted;
- restauração não carrega credencial e mantém lotes pendentes/incertos pausados;
- rejeita CR/LF e controles em headers.

## Verificação

- Prettier: PASS;
- `git diff --check`: PASS;
- revisões independentes de segurança, clareza e fidelidade ao escopo: PASS.

## Estado da issue

Este PR **não fecha #46**. O cliente ainda precisa informar o provedor/produto;
depois disso, o registro deve ser preenchido somente com documentação oficial e
homologado novamente. Mailpit permanece exclusivo do desenvolvimento.

Refs #46

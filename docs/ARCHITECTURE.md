# Arquitetura inicial

O repositório é um monorepo: a API e a interface compartilham documentação, automações e infraestrutura, mas preservam dependências e testes isolados.

```text
apps/web ────────────────► apps/api ─────────────► PostgreSQL
  interface interna          autenticação e regras      dados operacionais
                              │
                              ├──────────────────────► MinIO
                              │                         documentos digitalizados
                              └──────────────────────► provedor de e-mail
                                                        (Mailpit local)
```

Na API, a evolução deve manter as fronteiras abaixo:

- `domain`: entidades, regras e interfaces sem dependência de HTTP ou banco;
- `application`: casos de uso, DTOs e autorização;
- `infrastructure`: PostgreSQL, armazenamento de arquivos, e-mail e integrações;
- `presentation`: rotas HTTP, serialização e autenticação de requisição.

Essa separação reproduz o princípio adotado no Genesi, mas inicia pequena: não crie camadas vazias sem uma funcionalidade real. Toda decisão estrutural que mude este desenho deve ser registrada em `docs/adr/`.

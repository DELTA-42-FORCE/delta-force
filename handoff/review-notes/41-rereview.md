## Resposta aos bloqueios da revisão anterior

@CaioSTAM, por favor, faça uma nova revisão da ponta atual deste PR.

A ponta atual `d2d2a86` resolve os três pontos registrados na revisão do commit
`5d6b320`:

1. **Primeira conta:** `POST /auth/setup` cria uma única conta proprietária sem
   segredo em ambiente/terminal; concorrência no PostgreSQL permite exatamente
   um sucesso e um conflito.
2. **Token em repouso:** migration `0003` substitui o token bruto por SHA-256;
   o token original é devolvido uma vez e nunca persistido. O frontend mantém a
   sessão somente em memória, sem `localStorage`.
3. **Fluxo utilizável:** a interface cobre setup inicial, login, perfil e logout,
   com estados de carregamento/erro e comportamento seguro para sessão inválida.

Correções adicionais de segurança na mesma ponta:

- senha limitada a 72 bytes UTF-8 para evitar truncamento silencioso do bcrypt;
- hash dummy pré-calculado evita custo/timing diferente para e-mail inexistente;
- runner de integração recusa `DATABASE_URL` não loopback;
- migration de hash do token suporta ciclo downgrade/upgrade;
- logout local preserva/limpa estado conforme o contrato testado.

Evidência atual: cinco checks do GitHub verdes. Solicita-se nova revisão sobre a
ponta atual, pois a decisão `CHANGES_REQUESTED` ainda aponta para o commit
antigo.

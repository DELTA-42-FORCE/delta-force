## Pedido de revisão técnica — ADR Windows e spike

@CaioSTAM, por favor, revise em conjunto esta ADR e o spike empilhado da PR #49.

A PR #48 contém a ADR 0002 como **Proposta**. O spike isolado está publicado em
`chore/43-windows-spike`, na PR #49 contra `chore/43-arquitetura-windows`, para
que o diff mostre somente as evidências.

O gate reproduzível do spike aprovou:

- 23 testes Python e 17 testes Rust;
- build React/Tauri `release` e renderização visível da UI;
- PyInstaller `onedir`, listener apenas em loopback e porta efêmera;
- bootstrap one-shot, capability por execução e Host/Origin estritos;
- instância única, fechamento gracioso e hard-kill sem órfão;
- SQLite `FULL`, foreign keys, rollback, reopen e `integrity_check`;
- rejeição de manifesto/arquivo adulterado;
- digest determinístico de 38 fontes:
  `b280db5793c6eecd182469b39602ccd4675b871a28ce392fdb4936cdff2dcac3`.

Foco solicitado:

1. suficiência das oito provas mínimas da ADR;
2. modelo de ameaça e separação entre binários/dados;
3. protocolo de lifecycle/rollback;
4. fronteira correta dos gates posteriores #21/#27/#44.

O aceite da ADR não autoriza dados reais nem distribuição. Assinatura real,
VM limpa, DACL/TOCTOU, backup e notebook definitivo permanecem posteriores.

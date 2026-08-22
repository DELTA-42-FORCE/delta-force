## Resumo

- adiciona um spike isolado e descartável para validar a arquitetura Windows da
  ADR 0002;
- prova React em janela Tauri, API sintética PyInstaller `onedir`, loopback
  dinâmico e lifecycle por Job Object;
- prova bootstrap one-shot/capability, recusa de Host/Origin inválidos,
  invariantes SQLite e rejeição de árvore adulterada;
- mantém dependências e lockfiles somente sob `spikes/issue-43-windows/`.

## Evidência reproduzível

```powershell
npm --prefix .\apps\web ci --ignore-scripts --no-audit --no-fund
.\spikes\issue-43-windows\scripts\build_desktop_poc.ps1
```

Execução de referência em Windows:

- 23 testes Python e 17 testes Rust aprovados;
- build React/Tauri `release` aprovado;
- janela React visível, instância única e somente loopback;
- fechamento gracioso e hard-kill sem sidecar órfão;
- bootstrap/capability/Host/Origin e isolamento entre execuções aprovados;
- SQLite `FULL`, foreign keys, rollback, reopen e `integrity_check` aprovados;
- adulteração de manifesto/arquivo recusada;
- digest de 38 fontes:
  `b280db5793c6eecd182469b39602ccd4675b871a28ce392fdb4936cdff2dcac3`.

O relatório sanitizado está em
`spikes/issue-43-windows/evidence/first-spike-report.md`.

## Limites deliberados

- somente dados e chaves sintéticos;
- não implementa cadastro, documentos, backup, instalador final, atualização
  completa ou assinatura real;
- DACL/TOCTOU, backup #44 e release/VM limpa #27 permanecem gates posteriores;
- não altera dependências ou lockfiles de `apps/` nem o `package-lock.json` da
  raiz.

## Relação com a ADR

PR empilhado sobre `chore/43-arquitetura-windows` para revisar apenas o spike.
Esta mudança fornece evidência aos gates 2 e 3 da ADR; não fecha #43 nem muda a
ADR para **Aceita** sem aprovação técnica explícita.

Refs #43

## Foco da revisão

- suficiência das oito provas mínimas da ADR;
- modelo de ameaça, separação binário/dados e rollback;
- fronteira entre este spike e os gates posteriores #21/#27/#44;
- ausência de segredo, dado real ou dependência do produto no diff.

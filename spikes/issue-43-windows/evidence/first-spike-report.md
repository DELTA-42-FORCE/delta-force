# Evidência sanitizada — primeiro spike Windows da issue #43

Data da execução: 20/08/2026 (America/Manaus).

## Resultado

**PASS** para o recorte do primeiro spike definido na ADR 0002. O resultado
permite revisão técnica da arquitetura proposta; não transforma a ADR em
Aceita, não aprova uso de dados reais e não constitui artefato distribuível.

O comando versionado abaixo executou do começo ao fim com código de saída zero:

```powershell
.\spikes\issue-43-windows\scripts\build_desktop_poc.ps1
```

## Ambiente de referência

| Item | Versão observada |
| --- | --- |
| Windows | 11 x64, kernel `10.0.26200.0` |
| Node.js / npm | `22.22.3` / `10.9.8` |
| uv / Python | `0.12.3` / `3.12.13` |
| FastAPI / Uvicorn | `0.141.1` / `0.52.4` |
| PyInstaller | `6.22.2` |
| Rust / Cargo | `1.97.1` / `1.97.1` |
| Tauri CLI / crate | `2.11.4` / `2.11.5` |
| Visual Studio Build Tools | `17.14.39` |
| MSVC / Windows SDK | `14.44.35207` / `10.0.26100.0` |

Este notebook é somente a máquina de referência. Não houve aceite de BitLocker,
NTFS ou hardware definitivo; essas provas devem ocorrer no computador final.

## Provas executadas

- Black deixou os 15 arquivos Python inalterados; Flake8 passou com o mesmo
  limite de 88 colunas definido para Black.
- Pytest: `23 passed`, com um aviso de depreciação vindo de
  Starlette/httpx e sem falha funcional.
- O PyInstaller gerou um layout `onedir` de 41 arquivos de payload.
- O executável empacotado foi iniciado de verdade e passou bootstrap one-shot,
  capability obrigatória e isolada por execução, Host/Origin exatos, shutdown
  gracioso, saída sanitizada e SQLite externo íntegro.
- A enumeração de sockets do Windows confirmou um único listener IPv4 em
  `127.0.0.1` e porta efêmera escolhida pelo próprio sidecar.
- O build React existente compilou 28 módulos; a automação de acessibilidade do
  Windows encontrou um elemento de texto `Delta Force CRM` renderizado e
  visível dentro da janela Tauri. Esse `<h1>` não existe no HTML estático, e a
  prova não concedeu IPC nem shell à WebView.
- Cargo executou `17 passed`: integridade Ed25519, alteração/ausência/excesso de
  arquivos, manifesto alterado ou malformado, arquivo de controle excessivo,
  readiness estrita, capability, mutex de instância única e Job Object.
- O executável Tauri `release` abriu com a árvore
  `tauri-shell -> crm-api-poc`; a segunda instância saiu sem criar outro
  sidecar.
- O fechamento nativo da janela encerrou o sidecar; o hard-kill do shell também
  encerrou o filho pelo Job Object `KILL_ON_JOB_CLOSE`.
- Depois do gate, não havia processo do shell nem `crm-api-poc` em execução.

## Artefatos locais ignorados

Os binários abaixo ficam em `build/`/`target/` ignorados pelo Git. Os hashes são
evidência desta execução e podem mudar em uma reconstrução PyInstaller.

| Artefato | Tamanho | SHA-256 |
| --- | ---: | --- |
| `crm-api-poc.exe` | 6.014.474 bytes | `4df923442a5ab9a4d1c34bb910e4130f4ce627eb358579ef0cab4320fe326de8` |
| `manifest.json` (41 entradas) | 5.475 bytes | `9ac8f5196a8f9fd940474d2c4ebc6ea295f1ac9621e6e3ff6ddea553a5468069` |
| `delta-force-windows-architecture-spike.exe` | 8.988.672 bytes | `dd1cbcfde88f324cd3ba74c5e1997baafc51fb3814e19bc66bed67dc9a148c05` |

`manifest.sig` tem exatamente 64 bytes e usa uma chave Ed25519 sintética,
exclusiva do spike. Nenhuma chave de produção foi criada ou usada.

## Vínculo com os fontes testados

O gate terminou calculando SHA-256 de cada arquivo versionável do spike,
ordenando linhas no formato `sha256  caminho` por bytes UTF-8 e calculando o
SHA-256 desse manifesto lógico. O relatório é excluído do conjunto para evitar
autorreferência, e o `.gitattributes` local fixa LF para que checkouts Windows
não alterem o digest por conversão de final de linha.

| Entradas | Algoritmo | Digest dos fontes |
| ---: | --- | --- |
| 38 | `sha256-of-sorted-sha256-path-lines-v1` | `b280db5793c6eecd182469b39602ccd4675b871a28ce392fdb4936cdff2dcac3` |

Depois de o gate preparar o ambiente `.venv`, o valor pode ser reproduzido com:

```powershell
.\spikes\issue-43-windows\api-poc\.venv\Scripts\python.exe `
  .\spikes\issue-43-windows\scripts\hash_spike_sources.py
```

## Revisão independente

A revisão final apontou três lacunas de evidência: janela nativa sem prova do
React renderizado, cleanup vulnerável a reutilização de PID e ausência de
vínculo entre resultados e fontes. O verificador agora exige o elemento de texto
criado pelo React, abre e retém os handles dos processos que criou e o gate
publica o digest acima. O comando completo foi reexecutado depois das correções
e terminou com código de saída zero.

## Avisos não bloqueadores

- O PyInstaller informa que o import opcional `tzdata` não foi encontrado; o
  runtime UTC-only empacotado foi executado e passou todos os probes.
- Cargo alerta para o mesmo nome de PDB entre os alvos binário e biblioteca e
  para um accessor reservado e ainda não usado no protótipo; ambos são avisos
  de build, sem falha de execução.

## Limites preservados

- DACL e eliminação do TOCTOU por handles pertencem à issue #21.
- NSIS, VM limpa, WebView2 offline, reinstalação, atualização e assinatura real
  pertencem à issue #27.
- Backup criptografado/restauração em HD externo pertence à issue #44.
- Não foram implementados cadastro, documentos, e-mail ou qualquer outro fluxo
  de produto.
- Nenhum dado, documento, credencial ou segredo real foi usado.

Portanto, este relatório encerra somente o primeiro spike. O próximo passo é a
revisão técnica do PR documental e, com autorização explícita, a publicação
desta branch de evidências para revisão.

# ADR 0004 — Formato de backup cifrado e restauração atômica por HD externo

**Status:** Proposta

**Data:** 18 de setembro de 2026

**Issue relacionada:** #44 (bloqueia #26 e #27)

## Contexto

O CRM roda para um único proprietário, em um único computador Windows, com SQLite
em arquivo e documentos numa árvore privada fora do banco (ADR 0003). A ADR 0002
fixou a **fronteira do backup** — snapshot consistente de banco, metadados e
documentos, gravado em HD externo e comprovado por restauração em outro
computador — mas adiou explicitamente para a #44 as decisões de **criptografia,
formato, KDF, credencial e custódia**.

O cliente já confirmou (`docs/CLIENT_DECISIONS.md`):

- backup em HD externo, restauração a partir dele após perda/troca de máquina;
- a proteção poderá usar uma **senha digitada pelo proprietário**;
- a senha **não** pode ser persistida no computador, no backup, em logs ou no
  repositório;
- gravação em streaming, verificando espaço e abortando com limpeza segura, sem
  carregar o arquivo inteiro em memória.

A revisão da PR #91/#93 reforçou a separação de responsabilidades: **formato
criptográfico, snapshot consistente e restauração atômica são decisões técnicas
do time**; custódia, quem restaura, perda de senha, frequência e retenção são
decisões operacionais que dependem do cliente. Esta ADR decide apenas a parte
técnica e mantém a operacional como pendência declarada.

## Decisão

### 1. Contêiner de arquivo único

O backup é um arquivo único `*.dfcrmbak` com:

1. **Cabeçalho em claro** (JSON de tamanho fixo prefixado por comprimento):
   `magic`, `versao_formato`, identificação do KDF e seus parâmetros, `salt`,
   `nonce_base`, tamanho de quadro, versão do schema Alembic e versão da
   aplicação. O cabeçalho é autenticado como dado associado (AAD), não cifrado,
   para permitir diagnóstico e escolha de rota de restauração sem a senha.
2. **Corpo cifrado em quadros (frames)**: um arquivo tar determinístico contendo
   `manifest.json`, o snapshot `db.sqlite3` e a subárvore `documents/`, cifrado
   em blocos de tamanho fixo (por ex. 1 MiB). Cada quadro é selado
   individualmente com AEAD, permitindo **gravação e leitura em streaming** sem
   materializar o arquivo inteiro em memória.

Nenhum nome de cliente, caminho identificável ou metadado sensível aparece no
cabeçalho em claro.

### 2. Criptografia

- **Cifra:** AES-256-GCM, aplicada por quadro. O `nonce` de cada quadro é
  derivado de `nonce_base` + contador monotônico do quadro; a tag GCM de cada
  quadro garante integridade e detecção de truncamento/reordenação. O cabeçalho
  entra como AAD do primeiro quadro para vinculá-lo ao corpo.
- **Derivação de chave (KDF):** `scrypt` (memória-dura, disponível no stdlib via
  `hashlib.scrypt`) com `salt` aleatório de 16 bytes e parâmetros registrados no
  cabeçalho (`n`, `r`, `p`). A chave de 32 bytes é derivada da senha do
  proprietário apenas em memória, usada e descartada; nunca é gravada.
- **Senha:** informada pelo proprietário a cada backup/restauração. Não é
  persistida em arquivo, banco, log, repositório nem no próprio backup. Não há
  chave vinculada à máquina de origem — o backup precisa abrir num computador
  substituto apenas com a senha.

### 3. Snapshot consistente

Sendo um único usuário e uma única máquina, a operação toma um **lock de
manutenção da aplicação** (bloqueia escrita durante o snapshot) e então:

1. copia o banco por **SQLite Online Backup API** (ou `VACUUM INTO`) para um
   arquivo temporário, produzindo cópia consistente mesmo com WAL ativo
   (coerente com `journal_mode=WAL`/`synchronous=FULL` da ADR 0003);
2. copia a subárvore privada de documentos;
3. escreve `manifest.json` com: versão do schema (revisão Alembic `head`),
   contagem de arquivos, tamanho total e **SHA-256 por arquivo**.

### 4. Restauração atômica

1. Ler o cabeçalho, derivar a chave, decifrar e **verificar as tags GCM** e os
   checksums do manifesto em uma área de staging temporária.
2. Rodar `integrity_check` e `foreign_key_check` no banco restaurado e conferir
   a revisão Alembic contra a aplicação.
3. Só após todas as verificações, **trocar atomicamente** banco e documentos
   para o lugar ativo. Falha em qualquer etapa preserva os dados atuais intactos
   e remove o staging; nunca há sobrescrita parcial.

### 5. Falha segura na gravação

Antes de gravar no HD externo, verificar espaço livre estimado. A gravação é em
streaming direto para o arquivo de destino; em erro (espaço, I/O, cancelamento),
o arquivo parcial é excluído — nunca fica conteúdo parcial. Restauração recusa
alvo errado (cabeçalho/`magic` inválido), arquivo corrompido (tag GCM ou
checksum divergente) e destino sem espaço.

### 6. Dependência

A API não possui hoje biblioteca de cifra simétrica (só `bcrypt`) e o stdlib do
Python não oferece AES. Esta ADR adota **`cryptography` (PyCA)** como única nova
dependência de runtime para AES-256-GCM: biblioteca auditada, com wheels para
Windows e sem exigir toolchain de build. `scrypt` permanece no stdlib. A adição
deve passar por `pip-audit` como as demais.

## Fora do escopo desta ADR (pendências operacionais do cliente/#26)

Permanecem decisões operacionais, não técnicas, e **não** são resolvidas aqui:

- onde a senha/chave de recuperação é guardada fora do computador e do HD;
- quem pode executar a restauração num computador substituto;
- procedimento em caso de perda da senha/chave;
- frequência, lembrete, versões/retenção de backups e proteção do disco
  (BitLocker) da máquina.

Essas respostas do cliente destravam a #26 e o aceite #27, mas não alteram o
formato aqui decidido.

## Consequências

- A #44 pode implementar o motor de backup/restauração com base técnica fechada,
  sem esperar as respostas operacionais do cliente.
- O backup é portátil: abre em outra máquina só com a senha, sem segredo preso
  ao equipamento perdido — atende à recuperação por HD externo.
- Uma nova dependência (`cryptography`) entra no runtime da API e no
  empacotamento PyInstaller; o job Windows e o `pip-audit` devem cobri-la.
- Nenhum dado real pode ser usado antes de backup e restauração serem aprovados
  e testados (ADR 0002); o aceite ponta a ponta ocorre na #27.
- Alterar cifra, KDF ou layout do contêiner depois exige nova ADR e conversor de
  formato versionado.

## Alternativas consideradas

| Alternativa | Resultado |
| --- | --- |
| **AES-256-GCM em quadros + scrypt (stdlib) + `cryptography`** | **Proposta.** AEAD auditada, streaming, integridade por quadro, sem toolchain de build. |
| Argon2id como KDF | Mais resistente a GPU, mas exige dependência adicional (`argon2-cffi`) além do cipher; `scrypt` do stdlib já é memória-dura e suficiente para este MVP de um usuário. Pode ser revisto em ADR futura. |
| ZIP com senha (ZipCrypto/AES-ZIP) | Rejeitada: ZipCrypto é inseguro; o AES-ZIP não é padronizado entre bibliotecas e dá menos controle sobre KDF, streaming e verificação atômica. |
| Cifra artesanal só com stdlib (`hmac`+XOR/CTR manual) | Rejeitada: implementar AEAD à mão é risco desnecessário; não há AES no stdlib. |
| Backup sem cifra, protegido só por BitLocker | Rejeitada: contraria a decisão do cliente de senha própria e deixa o HD externo desprotegido fora de uma máquina com BitLocker. |

## Referências

- [ADR 0002 — Aplicativo local Windows](0002-aplicativo-local-windows.md) (fronteira do backup)
- [ADR 0003 — SQLite como persistência local](0003-sqlite-como-persistencia-local.md)
- `docs/CLIENT_DECISIONS.md` (decisões e pendências da #44/#46)
- [SQLite — Online Backup API](https://www.sqlite.org/backup.html)

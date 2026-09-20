# ADR 0004 — Backup cifrado e restauração por HD externo

**Status:** Aceita

**Data:** 20 de setembro de 2026

**Issue relacionada:** #44 (bloqueia #26 e #27)

## Contexto

O CRM mantém o SQLite e os documentos privados no computador do proprietário. O
cliente confirmou backup/restauração por HD externo e senha digitada. Essa senha
não pode ser persistida. A ADR 0002 definiu a fronteira do backup, mas deixou
formato, criptografia, KDF e recuperação para esta decisão.

Esta ADR fecha a parte técnica sem inventar recuperação de senha. A restauração
em instalação vazia é o caminho padrão. Por decisão posterior registrada em
`docs/CLIENT_DECISIONS.md`, também será possível substituir dados existentes,
sempre com confirmação explícita, nova geração completa e rollback durável. Esse
mecanismo é uma exceção estrita à proibição de um sistema geral de gerações na
ADR 0002: ele existe somente durante restauração, não é atualizador nem histórico
de versões do aplicativo.

## Decisão

### Formato binário versão 1

O arquivo tem extensão `.dfcrmbak` e a sequência canônica abaixo:

1. magic ASCII de 8 bytes `DFCRMBK1`;
2. tamanho do cabeçalho em `uint32` big-endian, entre 1 e 4096 bytes;
3. cabeçalho JSON UTF-8 canônico (`sort_keys=True`, separadores `,` e `:`, sem
   chaves desconhecidas nem números de ponto flutuante);
4. para cada quadro: tamanho do texto claro em `uint32` big-endian, seguido do
   ciphertext de mesmo tamanho e da tag GCM de 16 bytes.

O cabeçalho contém somente `format_version`, `app_version`, `schema_revision`,
`created_at`, `payload_bytes`, `frame_count`, `frame_size`, `cipher`, `kdf`,
`salt` e `nonce_prefix`. `format_version` é o inteiro `1`; `cipher` é a string
`AES-256-GCM`; `kdf` é exatamente o objeto
`{"name":"scrypt","n":32768,"r":8,"p":1,"dklen":32,"maxmem":67108864}`.
`created_at` usa UTC no formato RFC 3339 com sufixo `Z`; tamanhos e contagens são
inteiros JSON não negativos. `salt` e `nonce_prefix` usam Base64 canônico com
padding e decodificação estrita. Os campos de versão são strings UTF-8 limitadas
a 128 bytes. O cabeçalho não contém nome de cliente, caminho, senha ou outro
dado pessoal.

Antes de executar o KDF, o leitor valida o tamanho físico e exige exatamente:

- versão 1, `AES-256-GCM` e `scrypt`;
- `scrypt` com `N=32768`, `r=8`, `p=1`, saída de 32 bytes e `maxmem` de
  64 MiB;
- salt aleatório de 16 bytes e prefixo de nonce aleatório de 8 bytes;
- quadros de 1 MiB, payload entre 1 byte e 2 TiB e de 1 a 2.097.152 quadros;
- `frame_count = ceil(payload_bytes / frame_size)`, todos os quadros não finais
  com 1 MiB e o quadro final com o restante declarado;
- tamanho físico exatamente igual ao derivado do cabeçalho e dos quadros.

Parâmetro divergente exige outra versão do formato. Parâmetros controlados por
arquivo não confiável jamais são repassados livremente ao KDF, evitando consumo
arbitrário de CPU ou memória.

O nonce de 96 bits é `nonce_prefix` (64 bits) concatenado ao índice `uint32`
big-endian do quadro. Os limites acima impedem overflow e reutilização. O AAD de
**todo** quadro é:

```text
SHA-256(cabeçalho canônico) || índice_u32 || ultimo_u8 || tamanho_claro_u32
```

O leitor conhece previamente contagem e tamanho total e rejeita repetição,
lacuna, reordenação, remoção de sufixo, truncamento, quadro extra e bytes depois
do último quadro.

### Payload e manifesto

O payload é um TAR determinístico composto somente por arquivos regulares:

- `manifest.json` canônico;
- `db.sqlite3`, snapshot do banco;
- `documents/<storage_key>`, apenas documentos referenciados pelo snapshot.

O manifesto registra revisão do schema, contagens, tamanhos e SHA-256 do banco e
de cada documento. A extração não usa `extractall`: rejeita links, dispositivos,
entradas extras ou duplicadas, nomes absolutos, `..`, barras alternativas,
arquivos fora do catálogo, mais de 100 mil documentos e manifesto acima de
16 MiB. Metadados TAR variáveis são normalizados para que o mesmo conjunto gere
estrutura determinística, sem publicar caminhos ou nomes originais.

### Snapshot consistente

1. A SQLite Online Backup API cria um snapshot coerente mesmo com WAL ativo.
2. As referências de documento são lidas desse snapshot, nunca do banco vivo.
3. Somente essas `storage_key` são copiadas para um staging local privado. Cada
   origem deve ser arquivo regular dentro da raiz gerenciada, sem symlink,
   junction ou reparse point, e seu tamanho e SHA-256 devem coincidir com os
   metadados persistidos. Ausência ou divergência aborta o backup.
4. O TAR nasce do staging imutável, é cifrado em streaming e todo plaintext
   temporário é removido ao final ou na falha.

Um documento publicado depois do snapshot fica para o próximo backup. Um que
aparece no snapshot já foi publicado de forma atômica pelo armazenamento. Assim,
o backup não confia em alterações diretas feitas pelo Windows.

### Destino e publicação no HD

Na entrega Windows, a pasta é escolhida pelo diálogo nativo. A aplicação abre e
valida o destino por handle, resolve o caminho final e:

- rejeita UNC/rede/nuvem, reparse point, FAT/FAT32 e o mesmo volume que contém
  os dados;
- consulta a identidade do volume e seu tipo por handle; aceita mídia removível
  ou volume conectado por USB, inclusive HD USB apresentado como `FIXED`;
- verifica espaço livre com margem mínima de 64 MiB;
- cria um nome aleatório exclusivo terminado em `.partial`, sem sobrescrever;
- grava em streaming, executa flush no arquivo, revalida a identidade do volume
  e publica com rename no mesmo volume somente após validar tamanho e digest;
- reabre o nome final, confirma identidade, tamanho e digest e remove somente o
  parcial conhecido caso qualquer etapa falhe.

Ao selecionar um backup depois de reconectar o HD, a aplicação revalida a
identidade do volume e o digest do arquivo antes de iniciar a restauração. O
bypass de mídia local existe apenas em configuração explícita de teste e fica
desabilitado no aplicativo distribuído.

### Restauração e ativação recuperável

O arquivo do HD é somente leitura durante toda a operação. Antes do KDF, a
aplicação valida cabeçalho, tamanho e espaço local disponível para duas cópias do
payload mais margem. Depois:

1. decifra quadros em streaming num staging local privado e valida TAR,
   manifesto, hashes e referências;
2. executa `integrity_check`, `foreign_key_check` e valida a revisão Alembic sem
   abrir o banco para uso normal;
3. materializa banco e documentos numa **nova geração completa**, ainda inativa;
4. grava e sincroniza um journal de ativação com geração anterior, candidata e
   fase atual;
5. fecha conexões, confirma novamente a autorização quando já há dados e troca
   um único ponteiro durável para a candidata;
6. reabre a geração ativa e repete os checks antes de concluir; a anterior fica
   preservada até a confirmação final e só então pode ser removida.

O resolvedor dos caminhos do banco e dos documentos sempre parte desse ponteiro,
de modo que ambos pertencem à mesma geração. Se houver interrupção, o bootstrap
consulta o journal e conclui ou desfaz a ativação sem combinar banco de uma
geração com documentos de outra. Falha preserva a geração anterior recuperável,
remove apenas o staging conhecido e nunca altera o backup no HD.

Em instalação vazia, o mesmo protocolo é usado com uma geração inicial vazia. A
substituição de dados exige autenticação do proprietário, resumo do impacto e
confirmação explícita reforçada; não é acionada automaticamente por atualização.

A ativação registra `backup.restore_applied` sem senha, caminho pessoal ou nome
de arquivo. O uso normal continua exigindo login com a conta trazida no backup.

### Senha e custódia

A senha é normalizada em NFC, deve ter de 12 a 1024 bytes em UTF-8, entra apenas
no request local e na memória do KDF e nunca é persistida, auditada ou incluída
no backup. Buffers controlados pela aplicação são sobrescritos assim que
possível, sem prometer eliminação absoluta de cópias internas do runtime. Não há
chave mestra, recuperação pela equipe nem vínculo com a máquina de origem.
Perder a senha sem cópia segura separada torna o backup irrecuperável.

### Dependência

Adota-se `cryptography` (PyCA) 50.x para AES-GCM; `hashlib.scrypt` permanece no
stdlib. A versão exata fica presa no lockfile. `pip-audit`, PyInstaller e o job
Windows obrigatório devem cobrir a biblioteca antes do merge da implementação.

## Pendências operacionais do cliente

As respostas sobre custódia da senha, pessoa autorizada a restaurar, perda de
senha, frequência, retenção, proteção do disco e recuperação da conta calibram
o manual, os lembretes e o aceite das issues #26/#27. Elas não alteram o formato
criptográfico nem autorizam guardar segredos no projeto.

## Consequências

- O backup é portátil e confidencial mesmo fora do computador.
- Corrupção e senha errada produzem a mesma resposta pública, reduzindo oráculo.
- Backup e restauração exigem espaço temporário local; a interface deve explicar
  a margem antes de iniciar.
- O primeiro aceite real usa dados sintéticos e HD de teste, nunca a única cópia
  do cliente.
- A restauração introduz somente gerações transitórias para ativação/rollback;
  não cria versionamento geral ou mecanismo de atualização.
- Alterar magic, layout, cifra, KDF, nonce ou manifesto exige nova versão e
  conversor explícito; a versão 1 nunca é reinterpretada silenciosamente.

## Alternativas rejeitadas

- ZIP/ZipCrypto: proteção inadequada e interoperabilidade AES-ZIP inconsistente.
- Backup sem cifra/BitLocker apenas: não protege o arquivo fora daquele volume.
- Cifra artesanal: risco criptográfico desnecessário.
- Chave presa ao computador: impediria recuperação após perda da máquina.
- Trocar banco e documentos separadamente: pode ativar um conjunto inconsistente.
- Sobrescrever dados ativos: falha ou queda de energia poderia destruir a única
  cópia local válida.

## Referências

- [ADR 0002](0002-aplicativo-local-windows.md)
- [ADR 0003](0003-sqlite-como-persistencia-local.md)
- `docs/CLIENT_DECISIONS.md`
- issue #44

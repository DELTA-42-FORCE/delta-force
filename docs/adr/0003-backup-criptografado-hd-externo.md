# ADR 0003 — Backup criptografado em HD externo

**Status:** Proposta

**Issue:** #44

**Data:** 22 de agosto de 2026

**Aprovadores:** responsável pelo produto e responsável técnico — pendentes

Esta proposta pode ser revisada enquanto a ADR 0002 ainda aguarda aprovação,
mas **não autoriza dependência, código, envio real de dados ou mudança nos
lockfiles**. A implementação começa somente depois do aceite das duas ADRs, das
respostas de `QUESTIONARIO_BACKUP_CLIENTE.md` e de uma issue de implementação
com critérios de teste.

## Contexto e dependências

O cliente confirmou backup em HD externo, restauração após perda/troca do
computador e guarda sem prazo de descarte definido. A ADR 0002 propõe produção
em SQLite e blobs imutáveis e exige um artefato único, versionado, criptografado,
autenticado e restaurável em outro Windows sem depender somente de DPAPI.

Dependências de decisão:

- ADR 0002 aceita e implementação desktop/SQLite vinculada;
- perfil documental/tamanho da #14 homologado para dimensionar ensaios;
- respostas do questionário de backup homologadas;
- biblioteca criptográfica e componente proprietário definidos por spike curto;
- nenhum dado real antes dos gates #21/#27/#44 e da inspeção do notebook final.

## Escopo e não objetivos

Esta ADR propõe:

- credencial de recuperação e sua custódia;
- formato v1 do artefato e compatibilidade futura;
- derivação/separação de chaves e criptografia autenticada;
- protocolos de criação, verificação e restauração transacionais;
- falhas, rollback, auditoria e provas necessárias.

Não fazem parte desta decisão:

- implementar o backup ou adicionar bibliotecas agora;
- escolher automaticamente HD, apagar histórico ou formatar dispositivo;
- sincronizar com nuvem/rede ou executar backup escondido;
- proteger dados já abertos contra malware, administrador ou conta Windows
  comprometida — limites já declarados na ADR 0002;
- definir descarte de dados sem decisão posterior do responsável pelo produto.

## Leitores, escritores e propriedade

O formato terá **uma única implementação criptográfica do produto**, reutilizada
nos dois sentidos. O spike de implementação deverá decidir se ela fica em módulo
Python empacotado ou crate Rust; duplicar cifra/parser em duas linguagens é
rejeitado porque cria leitores divergentes.

- **Escritor:** caso de uso de backup iniciado pelo proprietário autenticado,
  com API em modo manutenção e adaptador de snapshot/artefato isolado.
- **Leitor:** modo de recuperação fechado, iniciado pelo launcher antes de abrir
  a geração ativa. Em instalação vazia, posse do artefato e do código autoriza a
  decriptação; em instalação com dados, também exige proprietário autenticado e
  confirmação explícita.
- **Fonte dos dados:** snapshot SQLite consistente, conjunto congelado de IDs de
  blobs da geração ativa e allowlist versionada de configurações portáteis não
  secretas. Caminhos locais, sessões e credenciais nunca entram nessa allowlist.
- **Destino:** arquivo novo em HD externo confirmado, nunca o conjunto ativo.

O frontend apenas conduz confirmação e progresso. Ele não recebe chave derivada,
chave de dados nem conteúdo decriptado.

## Modelo de ameaça específico

O desenho deve proteger confidencialidade e integridade diante de:

- perda, roubo ou leitura direta do HD;
- alteração, truncamento, reordenação ou mistura de partes do artefato;
- tentativa offline de adivinhar o código;
- arquivo hostil tentando consumir memória/disco, escapar de staging ou explorar
  parser de versão;
- HD errado, mesmo volume da origem, reparse point, falta de espaço, desconexão
  ou queda em qualquer etapa;
- restauração de versão incompatível ou tentativa de sobrescrever geração ativa;
- sessão/credencial ligada à máquina migrando indevidamente.

O tamanho total do artefato e a versão pública do formato não são ocultados. A
segurança não depende de nome de arquivo secreto nem de hash sem chave.

## Credencial de recuperação

- Gerar por CSPRNG um código portátil com **pelo menos 128 bits aleatórios de
  payload**, além do checksum de transcrição; o checksum não conta como entropia
  e não se aceita código escolhido pelo usuário.
- Mostrar/permitir impressão somente em fluxo local autenticado e confirmado.
  Não copiar automaticamente para clipboard, log, screenshot, diagnóstico,
  banco, GitHub ou HD de backup.
- Exigir confirmação de grupos escolhidos aleatoriamente antes de considerar a
  guarda concluída.
- Guardar a cópia portátil separadamente do computador e do HD. A forma exata
  depende da homologação do questionário.
- Se aprovado pelo cliente, uma cópia operacional pode ser protegida por DPAPI
  `CurrentUser` para criar backups sem redigitação. Ela fica em `state/secrets`,
  nunca no artefato, e é descartada/recriada no fluxo explícito de rotação.
- Em outro computador, o código é informado novamente. Sessões, tokens e
  credenciais SMTP/API não são restaurados.
- Suspeita de comprometimento gera outro código e **outro backup completo**.
  Backup antigo não é reescrito e continua exigindo o código antigo até existir
  decisão explícita de descarte físico.

Se o código e toda cópia operacional forem perdidos, não existe recuperação
oculta ou chave-mestra do fornecedor. Essa consequência deve aparecer antes da
ativação.

## Suíte criptográfica proposta para o formato v1

| Finalidade             | Decisão v1                                              |
| ---------------------- | ------------------------------------------------------- |
| Código para chave-base | Argon2id v1.3, saída de 256 bits                        |
| Parâmetros iniciais    | `m=65536 KiB`, `t=3`, `p=4`, salt aleatório de 128 bits |
| Chave de dados         | 256 bits gerados por CSPRNG para cada backup            |
| Separação de chaves    | HKDF-SHA-256 com `info` versionado e distinto           |
| Proteção               | AES-256-GCM, nonce de 96 bits e tag de 128 bits         |
| Hashes internos/recibo | SHA-256                                                 |

Os parâmetros Argon2id correspondem à segunda recomendação uniforme do RFC
9106 para ambientes com menos memória. Antes do aceite final, o spike deve medir
o notebook de referência e a VM da #27 sem enfraquecer esses valores. Parâmetro
carregado de arquivo não é livre: o leitor v1 aceita somente a suíte/limites
aprovados, impedindo artefato hostil de solicitar custo arbitrário.

Fluxo de chaves e cabeçalho, sem dependência circular:

1. decodificar, normalizar e validar o código sem reduzir seus 128 bits de
   payload;
2. construir bytes canônicos e limitados de `header_prefix`, contendo magic,
   versão, suíte, `backup_id`, parâmetros/salt Argon2id e nonce de
   envelopamento;
3. derivar `root_key = Argon2id(codigo, salt)`;
4. derivar a chave de envelopamento com HKDF-SHA-256, usando `root_key`,
   `salt=backup_id` e
   `info="delta-force-crm-backup/v1/wrap"`;
5. gerar a chave de dados aleatória e envelopá-la com AES-GCM, usando os bytes
   exatos de `header_prefix` como associated data;
6. formar o cabeçalho completo com `header_prefix`, chave envelopada e tag, e
   calcular `header_hash = SHA-256(header_completo)`;
7. derivar da chave de dados, via HKDF-SHA-256 e `info` distintos e versionados,
   a chave dos registros e a chave do manifesto;
8. apagar da memória código normalizado, `root_key`, `wrap_key` e demais chaves
   assim que cada fase terminar, usando primitivas de zeroização da biblioteca
   escolhida.

Cada chave de dados, salt e nonce de envelopamento é aleatório e exclusivo do
backup. Registros usam contador monotônico como nonce no domínio de sua chave;
o manifesto usa chave distinta e domínio de nonce separado. Contador repetido,
overflow, limite excedido ou ordem divergente faz a operação falhar fechada.
Nunca reutilizar nonce/chave entre artefatos.

O formato v1 terá constantes internas `MAX_RECORDS`, `MAX_TOTAL_PLAINTEXT` e
`MAX_RECORD_PLAINTEXT`; elas não vêm do cabeçalho. Os valores finais e sua prova
contra os limites de segurança do AES-GCM serão aprovados na revisão
criptográfica antes do aceite desta ADR. Até lá, não existe formato v1 liberado
para implementação.

O NIST iniciou revisão da SP 800-38D. Antes de implementar, conferir a publicação
final vigente e registrar qualquer mudança necessária em nova revisão desta ADR;
não trocar algoritmo silenciosamente mantendo o mesmo identificador de suíte.

## Formato do artefato v1

Extensão proposta: `.dfcrm-backup`. Nome externo contém somente parte suficiente
do ID aleatório do backup, sem data, nome de cliente, usuário ou computador. O
instante de criação fica apenas no manifesto criptografado.

```text
header_prefix público, canônico e limitado
  magic + versão do formato + suíte
  backup_id aleatório
  parâmetros/salt Argon2id
  nonce de envelopamento
chave de dados envelopada + tag
registros autenticados e criptografados
  snapshot SQLite
  blobs em ordem estável por ID opaco
manifesto final autenticado e criptografado
  versão do aplicativo/schema
  geração de origem
  configurações portáteis não secretas
  contagem/tamanho/hash do banco e de cada blob
  contagem final dos registros
```

- O cabeçalho não contém PII, caminho, nome de máquina nem data.
- Antes de executar Argon2id, o leitor limita o cabeçalho e aceita exatamente os
  parâmetros v1 aprovados; nenhum tamanho ou custo controlado pelo arquivo pode
  provocar alocação arbitrária.
- O `header_prefix` exato autentica o envelopamento. O `header_hash` do cabeçalho
  completo autentica todos os registros e o manifesto.
- Cada registro inclui em associated data `header_hash`, índice, tipo e tamanho
  cifrado; duplicação, remoção, troca de ordem ou truncamento invalida o
  artefato.
- O manifesto é obrigatório e somente aparece depois de todos os registros. O
  leitor não ativa nada antes de autenticá-lo e cruzar contagens/hashes.
- O parser usa comprimentos fixos/limitados, operações aritméticas verificadas e
  limites compatíveis com o perfil homologado da #14. Campo duplicado,
  desconhecido ou fora do limite falha antes de alocar/escrever conteúdo.
- O pacote não aceita caminho arbitrário. Só existem os tipos `database` e
  `blob`; ID de blob segue o formato opaco validado pela #21.
- Um recibo local guarda volume, ID do backup, tamanho e SHA-256 final para a
  verificação após reconexão. O recibo é sanitizado e não é necessário para
  restaurar em outra máquina; segurança portátil vem de AEAD e do manifesto.

Testes terão vetores sintéticos versionados para leitura v1. Vetores nunca usam
o código operacional nem dados do cliente.

## Protocolo de criação

1. Exigir proprietário autenticado, confirmação, HD conectado e código/cópia
   operacional disponível.
2. Resolver origem/destino por handles; confirmar caminho final, filesystem,
   reparse points, identidade do volume e identidade do dispositivo físico.
   Aceitar somente NTFS ou exFAT e rejeitar rede, nuvem, FAT32, mesmo volume e
   mesmo disco físico. Número serial do volume isolado não prova que dois
   volumes estejam em discos diferentes. Nunca formatar.
3. Pré-validar espaço com margem para snapshot, framing, tags e `.partial`.
4. Entrar em modo manutenção e bloquear toda mutação.
5. Criar em staging local protegido o snapshot pela SQLite Online Backup API;
   executar `integrity_check` e congelar transacionalmente as referências de
   blobs.
6. Verificar existência, tamanho e SHA-256 de cada blob referenciado. Divergência
   aborta antes de publicar qualquer backup.
7. Criar no HD um nome exclusivo `.partial` com operação create-new; nunca abrir
   backup anterior para escrita.
8. Escrever/encriptar em fluxo, verificar cada resultado, descarregar o arquivo
   com primitiva Windows e publicar nome definitivo único somente após sucesso.
9. Reabrir o arquivo definitivo por handle, calcular tamanho/SHA-256 e persistir
   recibo sanitizado. Sair do modo manutenção e remover somente staging criado
   por esta execução após revalidar seus handles.
10. Orientar ejeção segura. Depois de reconectar, revalidar volume, arquivo,
    tamanho e SHA-256; somente então mostrar **backup verificado**.

Queda/desconexão nunca remove backup anterior nem produz sucesso. `.partial`
restante é ignorado para restauração e só pode ser limpo por ação explícita após
revalidar volume e nome exato.

## Protocolo de restauração

1. Em instalação vazia, abrir modo de recuperação sem criar proprietário/banco;
   em instalação com dados, exigir sessão do proprietário e confirmação.
2. Abrir artefato por handle, validar volume/caminho e copiar ou ler somente para
   staging local protegido, com espaço pré-validado.
3. Fazer parsing limitado do cabeçalho, derivar chave, autenticar chave
   envelopada e decriptar registros em arquivos novos de staging. Código errado
   ou adulteração retorna erro genérico, sem distinguir oráculo criptográfico.
4. Autenticar o manifesto final e cruzar versão, schema, contagens, tamanhos,
   hashes, IDs, allowlist de configurações e `integrity_check` do SQLite.
   Configuração desconhecida, secreta ou ligada a caminho/máquina é recusada.
5. Aceitar somente formato suportado. Se migration for necessária, construir uma
   única geração candidata não selada, migrar e executar health check antes de
   gerar/validar manifesto de geração e selar.
6. Importar blobs por ID opaco sem sobrescrever. ID existente com hash diferente
   aborta; conteúdo idêntico pode ser reutilizado somente após verificação.
7. Ativar a candidata pelo journal e slots duráveis da ADR 0002, preservando a
   geração anterior inativa. Falha antes do commit deixa a ativa intacta.
8. Apagar staging/chaves com escopo exato. Exigir novo login e nova configuração
   de credenciais ligadas à máquina. Redefinir a senha do proprietário usando
   somente artefato+código só será permitido se essa regra for explicitamente
   homologada no questionário; a escolha e o resultado serão auditados.
9. Registrar evento funcional sanitizado de tentativa/resultado da restauração,
   sem caminho, volume, código, hash de chave ou conteúdo.

Restauração nunca decripta diretamente sobre a geração ativa e nunca executa
arquivo vindo do backup.

## Compatibilidade, migração e rollback

- O v1 é imutável depois do primeiro release. Alterar estrutura, KDF, AEAD ou
  semântica cria nova versão/suíte, novos vetores e nova ADR/revisão.
- Escritor sempre produz a versão corrente. Leitor mantém suporte a todas as
  versões já distribuídas enquanto houver backup retido; remover leitor exige
  política explícita e conversão para **novo artefato**, nunca in-place.
- Versão mais nova desconhecida retorna “aplicativo precisa ser atualizado” sem
  tentar interpretar payload.
- Reexecução após queda é idempotente por `backup_id`/`operation_id`; não
  sobrescreve artefato, staging ou geração já existente.
- Falha de backup não altera dados ativos. Falha de restauração não ativa
  candidata. Rollback alcança somente staging/candidata desta operação e nunca
  apaga backup, geração ativa ou último recovery point.
- Rotação do código gera novo backup completo. Não re-encriptar o único artefato
  nem substituir histórico no próprio HD.

## Auditoria, logs e mensagens

Auditar início, sucesso, falha normalizada, verificação e restauração com IDs
internos, horário, ator/`system`, resultado e código fechado. Não registrar:

- caminho, label/serial do volume, nome de arquivo fornecido pelo usuário;
- código, salt, nonce, chave, tag ou chave envelopada;
- CPF, nome, e-mail, documento, conteúdo ou hash correlacionável de blob;
- stack trace, header ou manifesto bruto.

Mensagens ao proprietário podem mostrar espaço necessário/disponível e uma
identificação local confirmável do HD, mas logs/relatórios usam somente ID opaco.

## Provas antes do aceite e implementação

### Gate da ADR

- [ ] Questionário respondido sem segredo e homologado.
- [ ] ADR 0002 aceita e issue desktop/SQLite vinculada.
- [ ] Revisão criptográfica independente da suíte, framing e nonces.
- [ ] Limites internos de registros, tamanho total e uso por chave aprovados
      contra os limites do AES-GCM; nenhuma dessas constantes vem do artefato.
- [ ] Spike sintético prova biblioteca única, vetores v1 e zeroização.
- [ ] Benchmark Argon2id passa no notebook de referência e na VM alvo sem
      reduzir os parâmetros v1.
- [ ] Aprovadores técnico/produto e data registrados; status muda para Aceita.

### Gate automatizado da implementação

- [ ] Vetores conhecidos para Argon2id, HKDF e AES-GCM e vetor completo do
      container v1 em pelo menos duas execuções/linguagens de ferramenta
      independentes para conferência, sem duplicar implementação no produto.
- [ ] Round trip de banco+blobs, backup vazio e perfil máximo da #14.
- [ ] Bit flip, truncamento, reordenação, duplicação, contador/nonce inválido,
      tag/chave errada, header hostil e versão/suíte desconhecida falham fechado.
- [ ] Queda/desconexão em cada janela de snapshot, `.partial`, flush, rename,
      recibo, decriptação, migration, selagem, journal e ativação.
- [ ] HD errado, mesmo volume, FAT32, rede/nuvem, reparse point, readonly e
      espaço insuficiente preservam dados e backups anteriores.
- [ ] Volumes distintos no mesmo disco físico são reconhecidos como o mesmo
      dispositivo e recusados; HD externo NTFS e exFAT são aceitos.
- [ ] Restore em instalação vazia e não vazia; sessão/DPAPI/SMTP não migram.
- [ ] Concorrência/retry são idempotentes e nunca publicam dois artefatos com o
      mesmo ID nem ativam duas candidatas.
- [ ] Scanner de logs/relatórios não encontra segredo, PII, caminho ou manifesto.

### Gate manual da #27

- [ ] Backup em HD externo na VM limpa, ejeção, reconexão e verificação.
- [ ] Restauração em outro Windows vazio usando somente artefato e código.
- [ ] Instruções executadas por pessoa diferente de quem as escreveu.
- [ ] Perda do computador, código incorreto e rotação são demonstrados com dados
      sintéticos.

## Decisão recomendada e pendências

A recomendação técnica é aprovar o container v1 e a suíte acima, condicionada ao
spike e à revisão criptográfica. Permanecem escolhas do responsável pelo produto:

- frequência/lembretes e período de manutenção;
- quantidade/rotação de HDs;
- custódia e reexibição do código;
- uso ou não da cópia local DPAPI;
- senha após restauração e frequência do teste periódico;
- regra futura de descarte quando o HD ficar sem espaço.

Enquanto qualquer uma estiver aberta, esta ADR permanece **Proposta** e nenhum
código/dependência de backup entra no produto.

## Referências primárias

- [RFC 9106 — Argon2](https://www.rfc-editor.org/rfc/rfc9106.html)
- [RFC 5869 — HKDF](https://www.rfc-editor.org/rfc/rfc5869.html)
- [NIST SP 800-38D — GCM/GMAC](https://csrc.nist.gov/pubs/sp/800/38/d/final)
- [NIST SP 800-57 Parte 1 Rev. 5 — gestão e recuperação de chaves](https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final)
- [SQLite — Online Backup API](https://www.sqlite.org/backup.html)
- [Microsoft — FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)
- [Microsoft — GetFinalPathNameByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew)
- [Microsoft — GetVolumeInformationByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getvolumeinformationbyhandlew)
- [Microsoft — IOCTL_STORAGE_GET_DEVICE_NUMBER](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-ioctl_storage_get_device_number)

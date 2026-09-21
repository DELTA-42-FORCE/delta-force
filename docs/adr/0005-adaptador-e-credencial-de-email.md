# ADR 0005 — Porta de envio, adaptadores e guarda de credencial de e-mail

**Status:** Aceita

**Data:** 20 de setembro de 2026

**Issue relacionada:** #46 (bloqueia a configuração real da #25)

## Contexto

A mala direta do CRM precisa de um remetente e de uma forma segura de guardar a
credencial. O cliente confirmou apenas que **informará depois** o e-mail/conta;
endereço, provedor, mecanismos autorizados, volume por lote e limites ainda não
vieram. A escolha entre SMTP e API cabe ao time depois dessas respostas.

O módulo `communications` já existe em arquitetura hexagonal (domínio,
aplicação, infraestrutura, apresentação) com portas como `Protocol`, mas
**sem porta de envio** — os arquivos declaram explicitamente "sem transporte
externo" / "ainda sem envio". Modelos de mensagem, seleção de destinatários,
triagem e o CRUD já foram entregues (#70/#79/#84).

A revisão da PR #93 fixou a separação: **o time escolhe o adaptador (SMTP/API) e
o mecanismo de guarda segura**; o cliente informa remetente, provedor/conta,
mecanismos de autenticação autorizados e volume por lote. O envio individual e
o tratamento de falhas já são decisões técnicas do time. Esta ADR decide essa
parte e deixa a configuração concreta como pendência declarada.

## Decisão

### 1. Porta de envio no domínio

Adicionar em `domain/communications` uma porta `EmailSender` (`Protocol`),
coerente com as portas de repositório já existentes. A porta envia **por
destinatário** e devolve um resultado por tentativa: `confirmed`,
`definitive_failure` ou `unknown`, além do identificador estável da tentativa e
do `Message-ID`. Nunca usa uma lista compartilhada — não há vazamento de
endereços entre destinatários (`To`/`CC` coletivo). A aplicação depende só da
porta; nenhum detalhe de SMTP/API sobe para o caso de uso.

### 2. Adaptadores na infraestrutura

Três implementações plugáveis, selecionadas por configuração:

1. **`SmtpEmailSender`** — envio real por SMTP usando `smtplib` e `email` do
   stdlib. Na configuração de produção, exige TLS com certificado e hostname
   validados pelo contexto seguro padrão e falha fechada **antes** de enviar
   credencial ou mensagem. Não há opção de ignorar certificado, hostname ou
   downgrade para texto claro no pacote distribuído.
2. **`InMemoryEmailSender`** (test double) — registra mensagens em memória, sem
   transporte. Existe somente nos testes da #25 e nunca representa envio real
   nem resolve as variáveis/campos pendentes da #24.
3. **Adaptador de API HTTP** — previsto como ponto de extensão caso o provedor
   informado pelo cliente ofereça apenas API. Não é implementado agora; a porta
   já o comporta sem mudar a aplicação.

O Mailpit usa uma configuração separada de desenvolvimento, aceita sem TLS e
sem autenticação somente quando o destino, após resolução, é loopback. Esse modo
não é compilado/empacotado nem selecionável na configuração final; qualquer
destino não loopback exige a política de produção.

### 3. Guarda de credencial

Adicionar uma porta `EmailCredentialProvider` (`Protocol`) com duas formas
suportadas de obtenção:

1. **Credencial Generic do Windows Credential Manager**, acessada pelas APIs
   `CredWriteW`, `CredReadW`, `CredFree` e `CredDeleteW` via `ctypes`. O target
   estável é `DeltaForceCRM/email-sender/v1` e não inclui endereço sensível em claro. Criação,
   atualização e remoção são explícitas; a leitura copia somente o necessário,
   libera a estrutura com `CredFree` e sobrescreve buffers controlados pela
   aplicação em best effort. A credencial fica no cofre do usuário Windows,
   fora de arquivos do aplicativo, banco, repositório, logs, issues e backups.
   DPAPI é uma proteção interna do Windows Credential Manager, não um segundo
   caminho em que o CRM armazena blobs cifrados.
2. **Entrada por sessão** — o proprietário digita a credencial ao iniciar o
   envio; ela permanece apenas em memória durante a operação e é descartada
   depois, com limpeza best effort dos buffers controlados.

A credencial de e-mail **pode** ficar atrelada ao perfil Windows da máquina: ao
contrário da senha de backup (ADR 0004), ela é reinserível pelo proprietário e
não precisa sobreviver à perda do computador. Nenhuma credencial é persistida
pela aplicação em disco próprio.

### 4. Envio individual, lote e reenvio

- Envio **individual** por destinatário; falha de um não interrompe os demais.
- Cada tentativa recebe `Message-ID` e identificador estável antes do transporte.
  Aceite confirmado pelo provedor vira `confirmed`; rejeição explícita antes do
  aceite vira `definitive_failure`. Timeout, desconexão ou resposta perdida
  depois de `DATA`/aceite possível vira `unknown`, nunca falha comprovada.
- **Reenvio automático** reprocessa somente `definitive_failure`. Destinatários
  `confirmed` nunca são repetidos. Estado `unknown` exige que o proprietário
  veja o risco de duplicidade e confirme uma nova tentativa; ela mantém vínculo
  com a tentativa e o `Message-ID` anteriores.
- Limite por lote e limites do provedor são **parametrizáveis**; o adaptador
  respeita a taxa configurada. Os valores concretos dependem do provedor e do
  volume informado pelo cliente.

### 5. Segredos e auditoria

Credencial e senha nunca entram em log, banco, repositório, issue ou backup. A
auditoria registra o evento de envio (quem, quando, contagens e resultado),
mas **não** grava credencial, corpo da mensagem ou endereços em claro nos logs,
conforme a regra de dados sensíveis da `ARCHITECTURE.md`. O histórico funcional
autorizado pode relacionar destinatário, tentativa, `Message-ID` e resultado
para permitir consulta e reenvio seguro.

### 6. Dependência

Nenhuma dependência nova de runtime: SMTP e montagem da mensagem usam `smtplib`
e `email` (stdlib); o Credential Manager usa `ctypes` (stdlib).
Se o provedor do cliente exigir SDK de API HTTP, a dependência correspondente
será avaliada na PR de implementação do adaptador de API, não aqui.

## Fora do escopo desta ADR (pendências do cliente/#25)

- endereço e nome de exibição do remetente;
- provedor/conta e mecanismos de autenticação que ele autoriza;
- volume esperado por lote e limites do provedor;
- forma de autenticação autorizada pelo provedor.

Essas respostas permitem ao time escolher e configurar SMTP ou API e destravam
o aceite real da **#25**, mas não alteram a arquitetura aqui decidida. O cliente
não precisa escolher a tecnologia do adaptador.

## Consequências

- `InMemoryEmailSender` permanece test double da #25; não substitui os campos e
  as variáveis homologadas que a #24 exige.
- A #25 implementa porta, transporte, cofre, histórico e tratamento dos três
  resultados. A configuração e o teste real aguardam os dados públicos do
  remetente e os mecanismos autorizados pelo provedor.
- Sem dependência nova de runtime; o job Windows exercita os caminhos `ctypes`
  específicos do SO, que precisam de teste no ambiente empacotado.
- Trocar de SMTP para API, ou de guarda de credencial, fica isolado atrás das
  portas, sem afetar os casos de uso.
- Nenhum envio real ocorre antes de o cliente informar o remetente e de a
  configuração segura ser aprovada.

## Alternativas consideradas

| Alternativa | Resultado |
| --- | --- |
| **Porta `EmailSender` + SMTP(stdlib)/InMemory + Credential Manager(ctypes)/sessão** | **Aceita.** Sem dependência nova, plugável, envio individual, segredo fora do app. |
| `keyring` para a credencial | Rejeitada agora: adiciona dependência para o que a API nativa do Credential Manager já resolve no alvo Windows único. |
| Guardar credencial em arquivo cifrado do app (como o backup, ADR 0004) | Rejeitada: o SO já oferece cofre por usuário; recriar KDF/custódia para uma credencial reinserível é complexidade desnecessária. |
| Credencial em `.env`/config do app | Rejeitada: contraria o critério de aceite (fora de arquivos, banco, repo, logs, backup). |
| Envio em lote com `To`/`CC` coletivo | Rejeitada: vazaria endereços entre destinatários; o envio é individual. |

## Referências

- [ADR 0002 — Aplicativo local Windows](0002-aplicativo-local-windows.md)
- [ADR 0004 — Formato de backup cifrado](0004-formato-de-backup-cifrado.md) (contraste de custódia de segredo)
- `docs/CLIENT_DECISIONS.md` (pendências da #46/#25)
- Issues #46 (esta), #24 e #25

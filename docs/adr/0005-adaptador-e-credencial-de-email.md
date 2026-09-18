# ADR 0005 — Porta de envio, adaptadores e guarda de credencial de e-mail

**Status:** Proposta

**Data:** 18 de setembro de 2026

**Issue relacionada:** #46 (bloqueia #25; permite a #24 avançar com adaptador falso)

## Contexto

A mala direta do CRM precisa de um remetente e de uma forma segura de guardar a
credencial. O cliente confirmou apenas que **informará depois** o e-mail/conta;
endereço, provedor, SMTP-ou-API, volume por lote e limites ainda não vieram.

O módulo `communications` já existe em arquitetura hexagonal (domínio,
aplicação, infraestrutura, apresentação) com portas como `Protocol`, mas
**sem porta de envio** — os arquivos declaram explicitamente "sem transporte
externo" / "ainda sem envio". Modelos de mensagem, seleção de destinatários,
triagem e o CRUD já foram entregues (#70/#79/#84).

A revisão da PR #93 fixou a separação: **o time escolhe o adaptador (SMTP/API) e
o mecanismo de guarda segura (Windows Credential Manager/DPAPI ou entrada por
sessão)**; o cliente informa remetente, provedor/conta, volume por lote e
confirma o envio individual com reenvio apenas das falhas. Esta ADR decide a
parte do time e deixa a operacional como pendência declarada.

## Decisão

### 1. Porta de envio no domínio

Adicionar em `domain/communications` uma porta `EmailSender` (`Protocol`),
coerente com as portas de repositório já existentes. A porta envia **por
destinatário** e devolve um resultado por destinatário (sucesso/falha com
motivo), nunca uma lista compartilhada — não há vazamento de endereços entre
destinatários (sem `To`/`CC` coletivo). A aplicação depende só da porta; nenhum
detalhe de SMTP/API sobe para o caso de uso.

### 2. Adaptadores na infraestrutura

Três implementações plugáveis, selecionadas por configuração:

1. **`SmtpEmailSender`** — envio real por SMTP com STARTTLS/TLS obrigatório,
   usando `smtplib` e `email` do stdlib. Autenticação obtida do provedor de
   credencial (item 3). É também o adaptador usado contra **Mailpit**, que
   permanece **exclusivo de desenvolvimento**.
2. **`InMemoryEmailSender`** (falso) — registra as mensagens em memória, sem
   transporte. Habilita os testes e permite a **#24** avançar (renderização e
   seleção) sem provedor real, conforme a própria issue.
3. **Adaptador de API HTTP** — previsto como ponto de extensão caso o provedor
   informado pelo cliente ofereça apenas API. Não é implementado agora; a porta
   já o comporta sem mudar a aplicação.

### 3. Guarda de credencial

Adicionar uma porta `EmailCredentialProvider` (`Protocol`) com duas
implementações suportadas, escolhidas por configuração:

1. **Windows Credential Manager / DPAPI**, acessado via `ctypes` (stdlib,
   `advapi32`/`crypt32`). A credencial fica no cofre do usuário Windows,
   protegida pelo SO, **fora** de arquivos do aplicativo, banco, repositório,
   logs, issues e backups.
2. **Entrada por sessão** — o proprietário digita a senha ao iniciar o envio; a
   credencial fica **apenas em memória** durante a sessão e é descartada depois.

A credencial de e-mail **pode** ficar atrelada ao perfil Windows da máquina: ao
contrário da senha de backup (ADR 0004), ela é reinserível pelo proprietário e
não precisa sobreviver à perda do computador. Nenhuma credencial é persistida
pela aplicação em disco próprio.

### 4. Envio individual, lote e reenvio

- Envio **individual** por destinatário; falha de um não interrompe os demais.
- **Reenvio** reprocessa **apenas os destinatários que falharam**, sem duplicar
  os que já receberam. O histórico da #25 registra o resultado por destinatário.
- Limite por lote e limites do provedor são **parametrizáveis**; o adaptador
  respeita a taxa configurada. Os valores concretos vêm do cliente.

### 5. Segredos e auditoria

Credencial e senha nunca entram em log, banco, repositório, issue ou backup. A
auditoria registra o evento de envio (quem, quando, contagens, resultado), mas
**não** grava endereços em claro nos logs, conforme a regra de dados sensíveis
da `ARCHITECTURE.md`.

### 6. Dependência

Nenhuma dependência nova de runtime: SMTP e montagem da mensagem usam `smtplib`
e `email` (stdlib); a guarda por Credential Manager/DPAPI usa `ctypes` (stdlib).
Se o provedor do cliente exigir SDK de API HTTP, a dependência correspondente
será avaliada na PR de implementação do adaptador de API, não aqui.

## Fora do escopo desta ADR (pendências do cliente/#25)

- endereço e nome de exibição do remetente;
- provedor/conta e escolha concreta entre SMTP e API;
- volume esperado por lote e limites do provedor;
- forma de autenticação autorizada pelo provedor.

Essas respostas configuram o adaptador real e destravam a **#25**, mas não
alteram a arquitetura aqui decidida.

## Consequências

- A #24 pode avançar já com o `InMemoryEmailSender`, sem provedor e sem expor
  endereços.
- A #25 passa a ser, principalmente, configurar o adaptador SMTP real e a guarda
  de credencial escolhida, mais histórico e tratamento de falhas.
- Sem dependência nova de runtime; o job Windows exercita os caminhos `ctypes`
  específicos do SO, que precisam de teste no ambiente empacotado.
- Trocar de SMTP para API, ou de guarda de credencial, fica isolado atrás das
  portas, sem afetar os casos de uso.
- Nenhum envio real ocorre antes de o cliente informar o remetente e de a
  configuração segura ser aprovada.

## Alternativas consideradas

| Alternativa | Resultado |
| --- | --- |
| **Porta `EmailSender` + SMTP(stdlib)/InMemory + Credential Manager(ctypes)/sessão** | **Proposta.** Sem dependência nova, plugável, envio individual, segredo fora do app. |
| `keyring` para a credencial | Rejeitada agora: adiciona dependência para o que `ctypes`/DPAPI já resolve no alvo Windows único. |
| Guardar credencial em arquivo cifrado do app (como o backup, ADR 0004) | Rejeitada: o SO já oferece cofre por usuário; recriar KDF/custódia para uma credencial reinserível é complexidade desnecessária. |
| Credencial em `.env`/config do app | Rejeitada: contraria o critério de aceite (fora de arquivos, banco, repo, logs, backup). |
| Envio em lote com `To`/`CC` coletivo | Rejeitada: vazaria endereços entre destinatários; o envio é individual. |

## Referências

- [ADR 0002 — Aplicativo local Windows](0002-aplicativo-local-windows.md)
- [ADR 0004 — Formato de backup cifrado](0004-formato-de-backup-cifrado.md) (contraste de custódia de segredo)
- `docs/CLIENT_DECISIONS.md` (pendências da #46/#25)
- Issues #46 (esta), #24 e #25

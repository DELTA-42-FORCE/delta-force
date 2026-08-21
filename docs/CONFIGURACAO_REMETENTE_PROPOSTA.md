# Configuração segura do remetente — registro técnico

- **Status:** aguardando respostas do cliente e documentação oficial — não
  implementar nem enviar mensagens reais
- **Versão do rascunho:** 0.1
- **Data:** 21 de agosto de 2026
- **Issue relacionada:** #46

Este registro será preenchido depois de
`QUESTIONARIO_REMETENTE_CLIENTE.md`. Ele documentará a configuração sem conter
endereço pessoal, senha, token, chave de API, código de MFA ou outro segredo.
Questionário preenchido, identidade do aprovador e credenciais permanecem fora
do repositório.

Todo campo deve ser preenchido. Use **não se aplica** em alternativas
legitimamente inaplicáveis e **não sei** somente enquanto a decisão continuar
bloqueada.

## Escopo desta decisão

- identificar provedor, produto e transporte suportado oficialmente;
- registrar autenticação, limites e requisitos de domínio sem guardar segredo;
- formalizar falha, reenvio, teste e ativação;
- definir como o aplicativo solicitará novamente a credencial após restauração.

## Não objetivos

- escolher provedor ou plano por hipótese;
- criar adaptador SMTP/API antes da decisão;
- enviar e-mail real ou usar endereço de cliente em teste;
- implementar modelos, seleção ou histórico das issues #24/#25;
- aconselhar juridicamente sobre consentimento ou retenção.

Antes de implementar #24/#25, seus corpos e dependências ainda precisam ser
reconciliados no GitHub: #24 depende de #14, #19 e #23 e usa o proprietário como
ator; #25 depende de #17 e #24, enquanto #46 bloqueia apenas a configuração
real. Cobranças permanecem fora do MVP. Esta correção externa exige autorização
do responsável pelo repositório e não faz parte da homologação documental #46.

## 1. Identificação reproduzível do provedor

| Item                                 | Decisão aprovada          |
| ------------------------------------ | ------------------------- |
| ID da configuração                   | REMETENTE-__________      |
| Provedor                             | __________                |
| Produto/plano                        | __________                |
| Transporte oficial: SMTP ou API      | __________                |
| Data da consulta                     | __________                |
| Documentação oficial de envio        | __________                |
| Documentação oficial de autenticação | __________                |
| Documentação oficial de limites      | __________                |
| Documentação oficial de erros/retry  | __________                |
| Domínio próprio                      | sim / não / não se aplica |
| Papel responsável pelo provedor/DNS  | __________                |
| Conta já existente e funcional       | sim / não                 |
| Conta empresarial ou pessoal         | __________                |

O endereço real, o nome da pessoa e a credencial não entram nesta tabela. A
configuração em produção os recebe por fluxo local protegido e referencia
somente um identificador técnico sem conteúdo sensível.

### 1.1 Endpoint e transporte protegido

Cada valor vem da documentação oficial do produto/plano escolhido:

| Item                                        | Decisão aprovada                         |
| ------------------------------------------- | ---------------------------------------- |
| SMTP hostname                               | __________ / não se aplica               |
| SMTP porta                                  | __________ / não se aplica               |
| SMTP modo: SMTPS ou STARTTLS obrigatório    | __________ / não se aplica               |
| API base URL                                | __________ / não se aplica               |
| API região, quando aplicável                | __________ / não se aplica               |
| Versão mínima de TLS suportada oficialmente | __________                               |
| Política oficial de redirects da API        | __________                               |
| Autoridade/cadeia de certificado esperada   | confiança padrão do Windows / __________ |

Regras obrigatórias:

- nunca enviar autenticação antes de concluir TLS nem fazer fallback para texto
  puro quando SMTPS/STARTTLS falhar;
- validar cadeia e hostname do certificado;
- não desabilitar verificação TLS;
- em API HTTPS, seguir redirect somente conforme allowlist oficial e nunca
  encaminhar autorização para host diferente não aprovado.

## 2. Identidade visível da mensagem

| Item                                                    | Decisão aprovada          |
| ------------------------------------------------------- | ------------------------- |
| Identificador externo do remetente                      | __________                |
| Nome empresarial/marca visível ou identificador externo | __________                |
| Reply-To usa a mesma caixa                              | sim / não                 |
| Identificador externo do Reply-To, se diferente         | __________                |
| Caixa acompanhada por                                   | papel: __________         |
| Finalidades documentais aprovadas no MVP                | __________                |
| Endereço/domínio verificado pelo provedor               | sim / não / não se aplica |

| Mecanismo | Exigido?   | Estado da verificação | Referência oficial |
| --------- | ---------- | --------------------- | ------------------ |
| SPF       | __________ | __________            | __________         |
| DKIM      | __________ | __________            | __________         |
| DMARC     | __________ | __________            | __________         |

SPF, DKIM e DMARC serão registrados conforme as instruções oficiais do
provedor; o repositório não guarda acesso ao DNS, registros completos nem
valores sensíveis.

## 3. Autenticação e ciclo da credencial

| Item                                                | Decisão aprovada    |
| --------------------------------------------------- | ------------------- |
| Mecanismo oficial: OAuth/app password/API key/outro | __________          |
| Escopo mínimo concedido                             | __________          |
| Como o proprietário insere a credencial             | __________          |
| Como testa sem exibir o segredo                     | __________          |
| Como revoga/rotaciona                               | __________          |
| Comportamento após troca de computador/restauração  | solicitar novamente |

Se o mecanismo aprovado for OAuth, preencher também:

| Item OAuth                                | Decisão aprovada                                   |
| ----------------------------------------- | -------------------------------------------------- |
| Tipo de aplicativo registrado no provedor | desktop/public client                              |
| Fluxo oficial                             | Authorization Code com PKCE e `state` / __________ |
| Authorization endpoint                    | __________                                         |
| Token endpoint                            | __________                                         |
| Redirect URI oficial                      | __________                                         |
| Escopos mínimos                           | __________                                         |
| Expiração/refresh                         | __________                                         |
| Revogação/desconexão                      | __________                                         |

Aplicativo desktop não embute `client_secret` confidencial como se pudesse
mantê-lo secreto. Fluxo OAuth usa a recomendação oficial do provedor, valida
`state`, PKCE, issuer/audience quando aplicáveis e trata refresh, expiração e
revogação sem registrar tokens.

Regras obrigatórias:

- nunca aceitar senha, token de acesso ou de refresh, chave de API ou outra
  credencial permanente por argumento, URL, log, issue, repositório ou arquivo
  de exemplo;
- no OAuth, a única exceção de URL é a resposta temporária recebida exatamente
  pela `redirect URI` registrada: validar `state` e PKCE, trocar o código uma só
  vez e nunca registrar a URL, a query nem o código;
- nunca reutilizar a senha principal da caixa quando o provedor exigir OAuth,
  senha de aplicativo ou chave própria para integração;
- nunca incluir credencial no backup ou relatório;
- não registrar corpo de resposta que possa conter token;
- não desativar validação TLS nem aceitar downgrade silencioso;
- ao desconectar, revogar ou trocar conta, apagar a credencial local protegida
  e exigir autenticação nova;
- usar o armazenamento local protegido definido pela ADR #43 somente depois de
  ela ser aceita e implementada; DPAPI `CurrentUser` não torna a credencial
  portátil, portanto a restauração exige nova configuração.

## 4. Limites oficiais

Não preencher por estimativa. Cada valor precisa de URL oficial e data de
consulta.

| Limite                     | Valor/unidade                 | Fonte oficial | Comportamento do CRM         |
| -------------------------- | ----------------------------- | ------------- | ---------------------------- |
| Destinatários por mensagem | __________                    | __________    | um destinatário por mensagem |
| Mensagens por minuto/hora  | __________                    | __________    | __________                   |
| Mensagens por dia          | __________                    | __________    | __________                   |
| Concorrência permitida     | __________                    | __________    | __________                   |
| Tamanho máximo da mensagem | __________                    | __________    | __________                   |
| Tamanho máximo de anexo    | não usado no MVP / __________ | __________    | __________                   |
| Outro limite               | __________                    | __________    | __________                   |

Expectativa operacional aprovada pelo cliente:

| Item                                        | Decisão aprovada |
| ------------------------------------------- | ---------------- |
| Máximo de destinatários por lote            | __________       |
| Máximo de lotes por dia                     | __________       |
| Repetição para o mesmo cliente no mesmo dia | __________       |
| Dias/horários permitidos                    | __________       |

O limite operacional do CRM deve ser igual ou menor que o limite oficial. Uma
mudança de plano/provedor exige rever esta tabela antes de enviar.

Registrar também os sinais oficiais de limitação (`Retry-After`, horário de
reset, código ou equivalente), a pausa do lote, o backoff e o máximo de
tentativas. Ausência dessa informação mantém o envio real bloqueado; não criar
temporização por hipótese.

## 5. Falha, resultado incerto e reenvio

| Situação                              | Classificação e comportamento aprovado          |
| ------------------------------------- | ----------------------------------------------- |
| Aceite confirmado pelo provedor       | registrar sucesso técnico                       |
| Destinatário recusado permanentemente | __________                                      |
| Limite temporário/rate limit          | __________                                      |
| Timeout antes de resposta             | resultado incerto; não reenviar automaticamente |
| Queda após resposta não persistida    | resultado incerto; não reenviar automaticamente |
| Credencial revogada/expirada          | bloquear lote e solicitar reconfiguração        |
| Erro desconhecido                     | falhar fechado e mostrar código sanitizado      |

Antes de chamar o provedor, persistir uma intenção e um `attempt_id` aleatório
sem PII. Quando houver idempotência oficial, registrar escopo, validade e regra
de reutilização da chave, também sem PII. Persistir o identificador de mensagem
retornado pelo provedor, quando houver, para reconciliar o resultado. Queda sem
confirmação continua como resultado incerto; idempotência local não prova que o
provedor deixou de enviar.

Política de reenvio aprovada:

- [ ] registrar resultado por destinatário;
- [ ] não reenviar automaticamente falha ou resultado incerto;
- [ ] exigir seleção e confirmação explícita do proprietário;
- [ ] usar chave idempotente quando o provedor oferecer suporte oficial;
- [ ] respeitar `Retry-After`/reset oficial, pausar o lote e aplicar somente o
      backoff aprovado;
- [ ] impedir novo lote equivalente sem confirmação quando houver resultado
      pendente/incerto;
- [ ] máximo de tentativas manuais: __________.

Depois de restauração, qualquer lote que estava pendente, em andamento ou com
resultado incerto permanece **pausado**. Ele só pode continuar após nova
autenticação da conta e confirmação explícita do proprietário.

O histórico funcional e a auditoria serão implementados nas issues #25/#17 sem
senha, token ou resposta sensível do provedor.

### 5.1 Logs e diagnósticos

Logs aceitam somente IDs internos opacos, `attempt_id`, código de erro
normalizado, data/hora, duração e resultado técnico. É proibido registrar:

- endereço do remetente, Reply-To ou destinatário;
- assunto, corpo, parâmetros/valores de modelo ou anexos;
- headers/envelope da mensagem;
- credencial, token, chave idempotente ou identificador que contenha PII;
- request/response bruto do provedor.

Histórico operacional protegido pode cumprir a #25, mas não deve ser copiado
para log ou diagnóstico. Mensagens de erro visíveis são sanitizadas.

Remetente, Reply-To, assunto e qualquer outro header rejeitam CR/LF e caracteres
de controle antes de chegar ao adaptador, evitando injeção de cabeçalho.

## 6. Plano de teste e ativação

| Autorização                      | Papel aprovado |
| -------------------------------- | -------------- |
| Autorizar primeiro teste externo | __________     |
| Ativar envio real em lote        | __________     |

1. Testar modelos, personalização e separação de destinatários no Mailpit.
2. Testar adaptador com respostas sintéticas de sucesso, falha permanente,
   limite temporário, timeout e resultado incerto.
3. Configurar a credencial pelo fluxo local, sem log ou captura.
4. Enviar uma única mensagem sintética para endereço autorizado externamente.
5. Confirmar remetente, Reply-To, autenticação de domínio, histórico sanitizado
   e ausência de segredo em logs/backup.
6. Simular queda antes/durante/depois da chamada e provar intenção persistida,
   resultado incerto e ausência de reenvio automático.
7. Restaurar estado com lote pendente/em andamento e provar que volta pausado,
   sem credencial e sem retomada automática.
8. Exigir confirmação do proprietário antes de habilitar lote.

## 7. Gates para homologação

- [ ] questionário do cliente respondido sem segredo ou dado pessoal versionado;
- [ ] provedor/produto/transporte identificados;
- [ ] fontes oficiais e datas registradas;
- [ ] endereço remetente e Reply-To aprovados em registro externo;
- [ ] autenticação de menor privilégio e ciclo da credencial aprovados;
- [ ] limites oficiais e comportamento local aprovados;
- [ ] política de falha, resultado incerto e reenvio aprovada;
- [ ] transporte TLS, endpoint e autenticação condicional aprovados;
- [ ] allowlist de logs e validação de headers aprovadas;
- [ ] restauração pausa lotes e exige nova autenticação/confirmação;
- [ ] plano de teste aprovado;
- [ ] nenhum campo vazio, “não sei” ou ressalva sem solução.

A homologação documental da #46 não depende do aceite da ADR #43. Somente a
implementação do armazenamento de segredo em produção permanece bloqueada até
o aceite da ADR.

## 8. Homologação

- **Papel/identificador não pessoal do aprovador:** _________________________
- **Data (dia/mês/ano):** _________________________________________________
- **Versão aprovada:** _____________________________________________________
- **Referência do registro externo de aprovação:** _________________________
- **Ressalvas:** nenhuma / _________________________________________________

Somente depois desta homologação a #25 pode configurar envio real. A #24 pode
usar adaptador falso/Mailpit, mas não deve incorporar provedor, segredo ou
limite inventado.

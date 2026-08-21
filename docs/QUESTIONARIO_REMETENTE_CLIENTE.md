# Perguntas para definir o e-mail remetente do CRM

- **Versão:** 0.1 — 21 de agosto de 2026
- **Status:** aguardando respostas — não configurar nem enviar e-mails reais
- **Objetivo:** identificar conta, provedor, volume e regras de envio sem coletar
  credenciais

O CRM enviará mensagens operacionais sobre pendências documentais. Cobranças,
avisos de pagamento, boletos e financeiro estão fora do MVP e exigem nova issue
e repriorização. O endereço remetente ainda não foi informado. Preencha todas
as perguntas; use **não sei** quando depender do provedor e **não se aplica**
quando uma pergunta não fizer sentido para essa conta.

## Antes de responder: nunca envie segredos

Não escreva nem anexe:

- senha ou senha de aplicativo;
- token, chave de API ou código de autenticação;
- código de MFA, recuperação ou QR code;
- acesso ao domínio, DNS, webmail ou painel do provedor;
- captura de tela real, mesmo com tarjas ou desfoque.
- nome, endereço de e-mail ou lista real de clientes/destinatários.

O questionário preenchido não será commitado no repositório. A configuração de
acesso será feita posteriormente por um fluxo seguro, nunca por conversa,
issue, log ou arquivo de exemplo.

## 1. Conta e provedor

- **Qual serviço é usado para abrir/administrar esse e-mail?** ______________
- **Nome exato do plano ou produto, se souber:** ____________________________
- **Página pública do provedor:** __________________________________________
- **O endereço remetente já existe e recebe mensagens?** sim / não / não sei
- **É um e-mail da empresa ou pessoal?** empresa / pessoal / não sei
- **Usa domínio próprio depois do `@`?** sim / não / não sei
- **Quem administra o domínio/provedor?** papel ou empresa, sem nome pessoal —
  resposta: ________________________________________________________________

O endereço real do remetente deve ser informado apenas no registro externo de
aprovação ou digitado diretamente na configuração segura do aplicativo; não o
copie para um arquivo versionado.

## 2. Como o destinatário verá a mensagem

- **Nome empresarial ou marca que aparecerá como remetente:** ______________
- Se precisar exibir nome pessoal, informe somente um identificador externo não
  pessoal para essa decisão: _______________________________________________
- **As respostas devem voltar para a mesma caixa?** sim / não / não sei
- Se não, haverá outro endereço de resposta? **sim / não / não sei**
- **Essa caixa será acompanhada para ler respostas?** sim / não / não sei
- **Quem acompanhará as respostas?** papel, sem nome pessoal: ______________

## 3. Finalidade e destinatários

Marque o que será enviado no MVP:

- [ ] solicitação ou aviso de documento pendente;
- [ ] aviso de documento incorreto/incompleto;
- [ ] outro aviso exclusivamente sobre solicitação, correção ou entrega de
      documentos: _________________________________________________________

Cobrança, aviso de pagamento, marketing, propaganda e qualquer finalidade não
documental não são opções deste MVP. Qualquer pedido futuro precisa de nova
issue e repriorização explícita.

Responder também:

- **Estimativa máxima de destinatários em um lote:** _______________________
- **Estimativa máxima de lotes por dia:** __________________________________
- **Dias/horários permitidos para envio:** _________________________________
- **Pode haver mais de uma mensagem para o mesmo cliente no mesmo dia?**
  não / sim — quando: __________________ / não sei

Cada destinatário receberá uma mensagem separada; nenhum cliente poderá ver o
endereço de outro cliente.

## 4. Falha e reenvio

Proposta de segurança para evitar duplicidade:

1. o sistema registra sucesso ou falha por destinatário;
2. não repete automaticamente um envio com resultado incerto;
3. mostra os destinatários com falha e o motivo sanitizado;
4. o proprietário seleciona e confirma explicitamente qualquer nova tentativa.

Neste questionário:

- **resultado incerto**: o provedor não confirmou se enviou; repetir pode gerar
  mensagem duplicada;
- **motivo sanitizado**: explicação sem senha, token ou dado pessoal;
- **recusa permanente**: o provedor informou que o endereço não pode receber
  novas mensagens.

- **Aprova esse comportamento?** sim / quero alterar / não sei
- **Se deseja alterar, explique:** _________________________________________
- **Depois de quantas tentativas manuais deve parar?** _____________________
- **Endereço recusado permanentemente deve ser bloqueado para novos lotes?**
  sim / não / não sei

Os limites e códigos de erro reais serão documentados a partir da página
oficial do provedor depois que ele for identificado; nenhum número será
escolhido por hipótese.

## 5. Teste e ativação

- O desenvolvimento continuará usando **Mailpit**, que não envia mensagem para
  a internet.
- O primeiro teste externo usará conteúdo sintético e um endereço autorizado
  informado fora do repositório; nunca usará dados de cliente.
- O envio em lote só será ativado depois de autenticação, limites, falhas,
  auditoria e armazenamento seguro da credencial passarem pelos testes.

- **Quem pode autorizar o primeiro teste externo?** papel: _________________
- **Quem pode ativar o envio em lote?** papel: ______________________________

## 6. Confirmação das respostas

Qualquer campo vazio ou resposta **não sei** mantém a configuração bloqueada.
Após as respostas, o time apresentará o registro técnico baseado somente na
documentação oficial do provedor e pedirá uma segunda aprovação.

- [ ] Confirmo que revisei as respostas desta versão.
- **Papel/identificador não pessoal de quem respondeu:** ___________________
- **Data (dia/mês/ano):** _________________________________________________
- **Referência do registro externo da resposta:** __________________________
- **Ressalvas:** nenhuma / _________________________________________________

Somente decisões sem endereço real ou outro dado pessoal serão transcritas para
o documento técnico versionado.

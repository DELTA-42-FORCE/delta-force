# Manual de operação segura — Delta Force CRM

Este manual orienta o proprietário e a equipe de suporte na instalação e no uso
do CRM local Windows. Ele não substitui avaliação jurídica, contábil ou de
segurança quando houver uma solicitação de titular ou um incidente real.

## Limites desta versão

- O CRM é usado por um único proprietário em um único computador Windows.
- Banco, documentos e histórico ficam em `%LOCALAPPDATA%\br.com.deltaforce.crm`.
- O backup é manual, criptografado e gravado em HD externo.
- A restauração só é aceita numa instalação vazia, antes de criar a primeira
  conta. Ela não substitui uma instalação que já contém dados.
- A atualização é feita manualmente com um novo instalador aprovado. Não há
  atualização nem downgrade automáticos.
- A desinstalação remove o programa e os atalhos, mas preserva os dados locais.
- O instalador do aceite ainda precisa ter origem, hash e situação de assinatura
  registrados no checklist da entrega.

## Regras de ouro

1. Use uma senha exclusiva no login do CRM e outra no backup.
2. Não compartilhe banco, documentos, backup, senha ou credencial SMTP por
   WhatsApp, issue, pull request, e-mail comum ou ferramenta de suporte.
3. Mantenha Windows e o aplicativo atualizados e use criptografia de dispositivo
   ou BitLocker quando a edição do Windows oferecer o recurso.
4. Conecte o HD somente para criar, verificar ou restaurar um backup. Ejete-o com
   segurança e guarde-o separado do computador.
5. Nunca altere diretamente o SQLite nem renomeie, substitua ou apague arquivos
   dentro da pasta privada. Use o CRM ou peça um procedimento técnico revisado.
6. Use apenas instalador entregue pela equipe, com versão e hash conferidos.

## Instalação e primeiro acesso

1. Confirme que o computador é o equipamento autorizado e que o Windows está
   atualizado, protegido por senha e sem conta compartilhada.
2. Registre no checklist de aceite a versão do Windows, a versão do CRM, o hash
   do instalador e sua origem. Se o hash divergir, não execute o arquivo.
3. Feche outros instaladores e execute o instalador do CRM para o usuário atual.
4. Abra **Delta Force CRM** pelo atalho da área de trabalho.
5. Em instalação nova:
   - para começar vazio, crie a conta do proprietário;
   - para recuperar uma cópia existente, escolha **Restaurar pelo HD externo**
     antes de criar a conta e siga a seção de restauração.
6. Guarde a senha do login fora do computador. A equipe não possui senha mestra.

## Rotina de uso

- Bloqueie a sessão do Windows ao se afastar do computador.
- Antes de anexar ou importar, confirme que o arquivo pertence ao cliente certo.
- Aceite somente PDF e JPEG pelo CRM. Não contorne uma rejeição renomeando a
  extensão do arquivo.
- Revise destinatários e prévia antes de qualquer disparo. A senha SMTP é
  digitada na sessão de envio e não deve ser salva em anotações no computador.
- Consulte a auditoria pelo aplicativo. Não edite o banco para alterar histórico.
- Não coloque dados reais em prints ou chamados de suporte; use dados sintéticos
  para reproduzir o problema sempre que possível.

## Criar backup no HD externo

Crie um backup ao menos quando o aplicativo apresentar o lembrete de sete dias e
sempre antes de atualização, manutenção ou troca de computador.

1. Conecte o HD externo confiável e confira no Explorador de Arquivos que é o
   dispositivo correto e possui espaço livre.
2. Entre no CRM, abra **Backup** e escolha uma pasta no HD.
3. Digite e confirme uma senha exclusiva com pelo menos 12 bytes. Guarde-a num
   local seguro separado do computador e do próprio HD.
4. Selecione **Criar backup criptografado** e espere a confirmação
   **Backup concluído e verificado**.
5. Anote data, versão do CRM e nome do arquivo `.dfcrmbak` no registro de backup,
   sem anotar a senha.
6. Ejete o HD pelo Windows e guarde-o fisicamente separado.

O CRM cria uma nova versão e não sobrescreve automaticamente as anteriores. Um
arquivo `.partial` não é backup válido. Se houver erro, preserve o último backup
válido e não apague versões antigas até confirmar uma restauração em teste.

## Restaurar após perda ou troca do computador

Use um Windows limpo e confiável. Se a causa foi malware ou ransomware, não
conecte o HD até o equipamento ser reinstalado e liberado pela equipe técnica.

1. Instale a mesma versão do CRM que criou o backup ou uma versão declarada
   compatível pela equipe.
2. Abra o aplicativo e **não crie uma conta nova**.
3. Conecte o HD, escolha **Restaurar pelo HD externo**, selecione o `.dfcrmbak` e
   informe a senha do backup.
4. Aguarde a validação completa. Senha errada e arquivo corrompido usam a mesma
   mensagem para não revelar informação a terceiros.
5. Quando o aplicativo pedir, feche-o e abra novamente. A ativação acontece
   antes de o banco ser liberado.
6. Entre com a conta que já existia no backup e verifique uma amostra de clientes,
   documentos, ficha PDF, histórico de e-mails e auditoria.
7. Mantenha o arquivo original no HD. Só considere a recuperação concluída após
   registrar as verificações no checklist de aceite.

Se já existir conta ou dado local, não tente apagar pastas para forçar a
restauração. Preserve os dois conjuntos e peça orientação técnica.

## Atualizar o CRM

1. Feche o CRM e crie um backup verificado no HD externo.
2. Registre versão e hash do instalador novo e confirme sua origem com a equipe.
3. Execute o instalador para o mesmo usuário do Windows.
4. Abra o CRM e confira login, cliente, documento, auditoria e a versão esperada.
5. Se a abertura falhar, não reinstale repetidamente, não faça downgrade e não
   apague `%LOCALAPPDATA%\br.com.deltaforce.crm`. Guarde o backup, registre a
   mensagem sem dados pessoais e acione o suporte.

## Desinstalar ou trocar de computador

1. Crie e verifique um backup no HD externo.
2. Feche o CRM e confirme no Gerenciador de Tarefas que a janela foi encerrada.
3. Desinstale **Delta Force CRM** em **Aplicativos instalados** do Windows.
4. A desinstalação preserva os dados. A exclusão definitiva da pasta privada é
   uma ação separada, irreversível e só pode ocorrer depois de avaliar retenção,
   solicitações de titulares e obrigações aplicáveis.
5. Na troca de computador, restaure primeiro e valide a cópia nova. Só depois
   decida sobre o equipamento antigo e apague seus dados com método adequado.

## Solicitação de titular de dados

O responsável pelo tratamento, e não o software, decide a resposta aplicável.

1. Registre a data, o canal, o pedido e uma referência de protocolo fora de
   campos livres do cliente. Não copie documento de identidade além do necessário.
2. Confirme a identidade por meio proporcional ao risco antes de revelar ou
   alterar qualquer dado.
3. Identifique o pedido: confirmação/acesso, correção, informação sobre uso ou
   compartilhamento, oposição, portabilidade ou eliminação, entre outros direitos.
4. Localize os dados no CRM; use a ficha PDF e a exportação dos documentos quando
   isso for adequado. Revise o material antes de entregar e use canal seguro.
5. Para correção, altere pelo CRM e preserve a auditoria. Para eliminação,
   bloqueio ou pedido incompatível com obrigação de guarda, não apague arquivos
   diretamente: registre a decisão e obtenha orientação responsável. Esta versão
   não possui exclusão integral e auditada da pasta de um cliente.
6. Registre o que foi entregue, corrigido, recusado ou encaminhado e o motivo da
   decisão, sem inserir segredo ou documento real em issue técnica.

Os direitos não são absolutos; por exemplo, uma obrigação legal de guarda pode
impedir uma exclusão imediata. Confirme o prazo e o fundamento aplicáveis na
orientação vigente antes de responder.

## Incidente de segurança

Considere incidente: perda ou roubo do computador/HD, ransomware, acesso sem
autorização, documento enviado ao destinatário errado, exposição do backup ou
alteração/destruição indevida de dados pessoais.

### Primeiros passos

1. Anote quando e como o fato foi percebido. Não inclua dados pessoais em canais
   inseguros.
2. Isole o computador da rede se houver suspeita de invasão ou malware. Não
   conecte o HD de backup e não destrua evidências.
3. Encerre o envio de e-mails e o uso do CRM quando continuar puder ampliar o
   dano. Preserve logs, mensagens e backups existentes.
4. Troque credenciais possivelmente expostas a partir de um dispositivo limpo,
   priorizando Windows, e-mail e contas de suporte.
5. Acione o responsável pelo tratamento e o suporte. Registre natureza do fato,
   datas, categorias de dados, quantidade aproximada de pessoas, proteções que
   existiam, possíveis danos e medidas adotadas.

### Avaliação e comunicação

O controlador deve avaliar se o incidente confirmado envolve dados pessoais e
pode causar risco ou dano relevante. Quando esses critérios se acumulam, a regra
geral vigente da ANPD prevê comunicação à Autoridade e aos titulares em três dias
úteis; informações podem ser complementadas conforme o regulamento. Não presuma
prazo diferenciado de agente de pequeno porte sem confirmar o enquadramento.

A comunicação ao titular deve ser clara, direta quando possível e informar os
dados afetados, riscos, proteções, medidas de mitigação, data de conhecimento e
um contato. O registro do incidente, inclusive quando não comunicado, deve ser
mantido por no mínimo cinco anos, com a justificativa da decisão.

### Recuperação

- Restaure somente em ambiente limpo e depois de conter a causa.
- Nunca use a única cópia do backup como mídia de investigação.
- Após recuperar, valide integridade, clientes/documentos, histórico e auditoria.
- Documente causa, correção, impacto e prevenção antes de encerrar o incidente.

## Suporte seguro

Ao pedir ajuda, envie versão do CRM/Windows, horário aproximado, ação executada e
texto sanitizado do erro. Nunca envie o arquivo SQLite, pasta de documentos,
`.dfcrmbak`, senha, token, credencial SMTP ou print com dados reais. Qualquer
acesso remoto precisa ser previamente autorizado, acompanhado pelo proprietário
e encerrado ao final.

## Referências oficiais

- [ANPD — comunicação de incidente de segurança](https://www.gov.br/anpd/pt-br/canais_atendimento/agente-de-tratamento/comunicado-de-incidente-de-seguranca-cis)
- [ANPD — direitos e petição do titular](https://www.gov.br/anpd/pt-br/canais_atendimento/cidadao-titular-de-dados/denuncia-peticao-de-titular-referente-lgpd)
- [ANPD — guia de segurança para agentes de pequeno porte](https://www.gov.br/anpd/pt-br/assuntos/noticias/anpd-publica-guia-de-seguranca-para-agentes-de-tratamento-de-pequeno-porte)
- [Resolução CD/ANPD nº 2/2022](https://www.gov.br/anpd/pt-br/acesso-a-informacao/institucional/atos-normativos/regulamentacoes_anpd/resolucao-cd-anpd-no-2-de-27-de-janeiro-de-2022)

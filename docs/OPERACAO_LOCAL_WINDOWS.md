# Manual operacional — CRM local Windows (#26)

**Estado: rascunho para revisão; não é autorização para usar dados reais.**

Este manual descreve a operação prevista do aplicativo local para o proprietário.
As decisões ainda pendentes em `CLIENT_DECISIONS.md` precisam ser respondidas e
incorporadas antes de considerar o aceite operacional concluído. Use somente
dados sintéticos durante testes. Nunca envie banco, documentos, backup,
credenciais ou capturas com dados pessoais à equipe.

## Instalação e primeiro acesso

1. Obtenha o instalador somente pelo canal de distribuição que o time confirmar
   para a versão aprovada. Confira versão e origem antes de executar. O canal,
   responsável de suporte e procedimento de verificação do instalador ainda
   precisam ser preenchidos no pacote de entrega.
2. Instale no Windows e abra pelo atalho do aplicativo. O CRM mantém banco e
   documentos em diretório privado sob `LocalAppData`, fora da pasta do
   instalador, de pastas sincronizadas, rede e mídia removível.
3. Na primeira abertura, crie a conta do proprietário pelo fluxo apresentado
   pelo aplicativo. Não existe conta padrão. Use uma senha exclusiva e não a
   compartilhe com a equipe.
4. Antes de cadastrar dados reais, confirme com o time que a proteção do
   computador/disco e a custódia das credenciais foram definidas. A proteção em
   repouso do armazenamento local e o procedimento de recuperação de conta ainda
   exigem decisão explícita.

Não copie, mova, renomeie ou edite diretamente os arquivos internos do CRM no
Explorer. Use as operações do aplicativo. Acessar documentos pelo Windows não
significa alterar a árvore gerenciada: mudanças externas podem deixar o CRM
inconsistente e sem trilha de auditoria.

## Uso diário e armazenamento

- Crie uma pasta digital por cliente usando o nome de identificação. Outros
  campos e documentos podem ser acrescentados gradualmente.
- Anexe ou importe apenas PDF e JPEG aceitos pelo aplicativo. O aplicativo grava
  documentos fora do banco, em armazenamento privado local.
- Não remova manualmente arquivos gerenciados nem a pasta privada. Não guarde
  a única cópia de documentos importantes apenas em mídia removível.
- A decisão do cliente é manter os dados sem prazo de descarte automático. Isso
  não elimina uma eventual solicitação legítima de acesso, correção ou exclusão;
  consulte o procedimento abaixo e obtenha orientação do responsável antes de
  qualquer exclusão.

## Atualização e desinstalação

Atualizações são manuais. Antes de instalar uma versão nova:

1. Faça um backup pelo fluxo **Backup e restauração** e confirme que o aplicativo
   informou conclusão. Mantenha a senha do backup disponível em local seguro,
   separado do computador e do HD; a equipe não deve recebê-la.
2. Feche o aplicativo normalmente e execute o instalador aprovado. O instalador
   não deve apagar nem substituir a área privada de dados.
3. Abra o aplicativo e confirme login e acesso aos dados. Se a migração falhar,
   não tente contornar o bloqueio, editar o banco ou instalar uma versão antiga
   por conta própria. Interrompa o uso e contate o suporte definido para a
   entrega, sem anexar dados ou segredos.

A desinstalação remove binários e atalhos, mas preserva banco e documentos.
Não apague a área privada para “limpar” uma instalação. Remoção definitiva de
dados é um fluxo separado, autenticado e explicitamente confirmado.
Compatibilidade de downgrade não é garantida; não use instalador antigo para
tentar abrir dados já migrados.

## Backup e restauração por HD externo

O backup é manual e cifrado em arquivo `.dfcrmbak`. O aplicativo não guarda a
senha do backup nem executa cópia automática. O lembrete é opcional e começa
desativado; frequência e quantidade de versões a manter ainda devem ser
definidas pelo proprietário.

### Criar uma cópia

1. Conecte um HD externo de teste/uso, diferente do volume onde estão os dados.
   Não use pasta de rede, nuvem, FAT/FAT32 ou o próprio computador como destino.
2. No CRM, abra **Backup e restauração**, escolha a pasta pelo seletor nativo e
   confirme a estimativa de espaço. Aguarde a validação da mídia.
3. Informe e confirme a senha do backup (12–1024 bytes UTF-8 após NFC). Ela é
   diferente da senha de login e não é salva. Não a inclua em arquivo, e-mail,
   issue, log ou mensagem para a equipe.
4. Mantenha o HD conectado até a confirmação final. Só considere a cópia pronta
   quando o aplicativo confirmar a publicação e verificação do arquivo.
5. Ejete o HD pelo Windows. Armazene HD e cópia da senha de acordo com a decisão
   de custódia ainda pendente; não mantenha ambos juntos sem avaliar o risco.

Não há política de retenção aprovada para backups no HD. Até a definição, não
apague cópias antigas como se houvesse rotação automática. O cliente decidiu
guardar os dados do CRM sem prazo de descarte, mas isso não define quantas
versões de backup devem existir.

### Restaurar

Restaure após perda/troca do computador ou quando houver procedimento aprovado
de recuperação. Primeiro instale uma versão compatível do aplicativo e conecte o
HD. Se houver dados na instalação atual, a substituição exige autenticação,
revisão do impacto e confirmação explícita.

No fluxo do aplicativo, selecione o `.dfcrmbak`, informe a senha do backup,
revise a prévia e, quando solicitada, confirme com a senha atual do proprietário
e a palavra **RESTAURAR**. Após a conclusão, entre com a conta existente dentro
do backup. Se a operação for interrompida e o aplicativo pedir reinício, feche
e reinicie-o; não tente remover arquivos temporários manualmente. Se a senha do
backup for perdida, não há recuperação pela equipe ou chave mestra. Sem uma
cópia separada da senha, o backup não pode ser restaurado.

Para HD perdido, danificado ou com erro de leitura, preserve-o e não formate nem
repare por conta própria. Use outra cópia verificada, se existir, e contate o
suporte definido. Não envie o arquivo de backup à equipe.

## Incidente, falha ou suspeita de acesso indevido

1. Pare de usar o CRM se houver suspeita de acesso indevido, perda/roubo do
   computador ou HD, malware, corrupção ou publicação acidental. Não apague,
   reinstale, restaure nem tente “consertar” arquivos antes de orientação.
2. Anote data/hora aproximada, versão do aplicativo, ação imediatamente
   anterior e texto/código de erro. Remova nomes, caminhos pessoais, conteúdo de
   documentos, senhas, tokens e outros dados pessoais das anotações.
3. Avise o contato de suporte/responsável que será informado no pacote final,
   por canal previamente combinado. Não envie banco, documentos, arquivo de
   backup ou credenciais. Se necessário para diagnóstico, compartilhe somente
   logs sanitizados gerados pelo procedimento que o time aprovar.
4. Preserve o equipamento e as mídias. Siga a orientação do responsável antes
   de reconectar o HD ou retomar alterações. Registre ações tomadas sem copiar
   dados pessoais para o registro do incidente.

O contato, prazo de resposta, canal e responsabilidades formais de tratamento
de incidente ainda não estão definidos. Este procedimento não substitui
orientação jurídica nem determina obrigações legais.

## Solicitação de acesso, correção ou exclusão de dados

O CRM é interno; solicitações de titulares devem ser recebidas pelo proprietário,
fora do acesso direto ao aplicativo. Registre a data e o pedido sem reproduzir
documentos ou dados desnecessários. O proprietário deve confirmar a identidade
por um canal apropriado, localizar a pasta e revisar a solicitação antes de
exportar, corrigir ou remover qualquer informação. Não divulgue dados nem faça
exclusão automática ou irreversível apenas com base em um pedido informal.

O prazo de retenção indefinido informado pelo cliente significa que não haverá
descarte automático por prazo no MVP; não decide sozinho como atender pedidos
legítimos, obrigações legais ou retenção de cópias de backup. Obtenha orientação
do responsável designado antes de agir e registre no CRM apenas o evento mínimo
necessário, sem conteúdo documental.

## Decisões necessárias para fechar o manual e o aceite

Antes de declarar #26/#27 concluídas, confirmar e documentar:

- como o proprietário guardará a senha do backup, quem pode restaurar e o que
  fazer se ela for perdida;
- frequência de backup, retenção/rotação das versões e uso de BitLocker no
  computador e no HD;
- recuperação da conta do CRM após troca de computador e esquecimento da senha;
- canal e contato de suporte, fluxo de incidente e responsável por solicitações
  de titulares;
- procedência/versionamento do instalador e validação em instalação limpa;
- ensaio físico de criação e restauração usando HD USB de teste e somente dados
  sintéticos.

As respostas atuais estão em `CLIENT_DECISIONS.md`; não registrar senhas ou
credenciais ao resolver essas perguntas.

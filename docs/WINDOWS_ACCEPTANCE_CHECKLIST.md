# Checklist de aceite do MVP no Windows

Use dados, documentos, conta SMTP e destinatário **exclusivamente sintéticos e
autorizados**. O aceite final deve ocorrer numa instalação Windows limpa e num
HD externo de teste; a automação local/CI não substitui esta evidência.

## Evidência técnica já executada

Em 19 de setembro de 2026, no commit histórico `c997b3b`,
`just desktop-build` gerou o
instalador local `Delta Force CRM_0.1.0_x64-setup.exe` com SHA-256
`A1534C62BCA9FDD9363C0D4484C3CC572DDD3D8338F808764C77D2293AF1C609`. O comando
`just desktop-installer-smoke` comprovou instalação, inicialização, encerramento,
desinstalação, reinstalação e preservação de dados sintéticos. Ao terminar, não
restaram registro de produto, processo nem pasta de dados. Esta evidência usa a
máquina de desenvolvimento e, portanto, não marca os itens de aceite manual em
Windows limpo ou HD externo real.

Essa evidência é anterior ao rebase e às correções de segurança da #99. Refaça
o build e o smoke a partir do commit candidato final; não reutilize o hash acima
como aceite do artefato definitivo.

## Identificação da execução

- Data e responsável:
- Revisor presente:
- Commit/tag do CRM:
- Nome, origem e SHA-256 do instalador:
- Situação da assinatura do instalador:
- Edição/versão/build do Windows:
- Estado do Windows Update e WebView2:
- Identificação não sensível do HD de teste e filesystem:
- Conta/remetente SMTP de teste autorizado:
- Destinatário de teste autorizado:

## Pré-condições

- [ ] O computador/VM não possui instalação, processo nem dados anteriores do CRM.
- [ ] O instalador veio do commit registrado e seu SHA-256 confere.
- [ ] Windows e antivírus estão atualizados; o operador anotou alertas apresentados.
- [ ] O HD externo de teste está vazio ou contém somente dados sintéticos dispensáveis.
- [ ] A senha do backup não é a senha do login e não foi registrada neste checklist.
- [ ] PDF e JPEG sintéticos válidos, arquivo inválido e acervo legado sintético estão prontos.

## Instalação e primeiro acesso

- [ ] Instala para o usuário atual sem Docker, Python, Node, banco ou terminal.
- [ ] Cria atalhos esperados e abre uma única janela do Delta Force CRM.
- [ ] Não deixa prompt/console nem processo sidecar após fechar a janela.
- [ ] Primeiro acesso permite criar a conta do proprietário e depois exige login.
- [ ] Senha inválida e tentativa de repetir o primeiro acesso são recusadas sem detalhe sensível.

## Clientes, documentos e ficha

- [ ] Cria cliente somente com nome e depois edita campos opcionais, inclusive e-mail válido.
- [ ] Busca e abre a pasta do cliente correto.
- [ ] Anexa PDF e JPEG válidos e rejeita extensão/conteúdo inválido sem arquivo parcial.
- [ ] Abre/exporta o documento autorizado e altera/remove seu acompanhamento manual.
- [ ] Gera e confere a ficha cadastral PDF.
- [ ] Importa acervo sintético com prévia e relatório, preservando a origem.

## Comunicação e auditoria

- [ ] Cria modelo com `{{nome}}`, visualiza prévia e rejeita variável não permitida.
- [ ] Configura remetente SMTP; a credencial é digitada só no envio.
- [ ] Seleciona destinatário por pendência e envia mensagem individual ao alvo autorizado.
- [ ] Registra sucesso/falha no histórico; `SENT` nunca é repetido, e uma
      tentativa `UNKNOWN` só pode ser repetida com confirmação explícita e
      vínculo à tentativa anterior.
- [ ] Após interrupção/reinício durante envio, tentativa pendente torna-se
      incerta antes de novo envio; reabrir a tela não duplica a mensagem.
- [ ] Reiniciar o aplicativo não recupera a senha SMTP anterior.
- [ ] Auditoria mostra login, consulta/alteração relevante, documentos, PDF, e-mail e backup.

## Backup em HD externo

- [ ] Rejeita pasta no disco interno, rede, FAT/FAT32 e caminho com link/reparse point.
- [ ] Cria `.dfcrmbak` no HD aceito, sem sobrescrever versão anterior e sem `.partial` residual.
- [ ] A interface confirma conclusão; nome/data são registrados sem a senha.
- [ ] Arquivo alterado, truncado ou senha errada são recusados sem distinguir o motivo.
- [ ] Desconectar ou esgotar espaço durante teste controlado não publica backup incompleto.

## Restauração em instalação limpa

- [ ] Num segundo Windows/usuário limpo, a tela inicial oferece restauração antes da conta.
- [ ] Valida o backup no HD, pede reinício e não altera/apaga o arquivo de origem.
- [ ] Após reabrir, aceita o login que veio no backup e não oferece criar novo proprietário.
- [ ] Clientes, documentos, ficha, modelos, histórico e auditoria conferem com a amostra original.
- [ ] A auditoria contém a ativação da restauração.

## Restauração sobre dados existentes

- [ ] Sem login do proprietário atual, a substituição é recusada.
- [ ] A interface avisa que a geração local inteira será substituída, sem
      mesclar acervos, e exige `SUBSTITUIR DADOS` antes de aceitar.
- [ ] Confirmação ausente/incorreta, senha de backup errada e arquivo inválido
      não alteram a geração ativa nem apagam o backup de origem.
- [ ] Após reinício, login, clientes, documentos e auditoria são os do backup;
      a geração anterior só é removida depois da validação final, conforme a
      ADR 0004. A cópia externa dos dados substituídos continua disponível.
- [ ] Queda controlada antes da ativação e falha de validação mantêm os dados
      anteriores íntegros, sem mistura de gerações.

## Atualização, reinstalação e desinstalação

- [ ] Cria backup verificado antes de instalar versão mais nova.
- [ ] Atualização preserva login, banco e documentos e conclui migrations sem intervenção manual.
- [ ] Falha de migration simulada não publica banco parcial nem libera escrita.
- [ ] Desinstalação remove binários/atalhos, mas preserva dados locais.
- [ ] Reinstalação abre os mesmos dados preservados.
- [ ] Não há downgrade automático; tentativa incompatível falha sem alterar dados.

## Encerramento

- [ ] Evidências não contêm dados reais, senha, token, banco, documentos nem caminho pessoal.
- [ ] Falhas foram abertas como issue com reprodução sintética e severidade.
- [ ] Manual de operação foi entregue e o proprietário executou backup/restauração assistidos.
- [ ] Situação de assinatura/distribuição e computador Windows final foram aprovadas pelo time.
- [ ] Responsável e revisor assinaram o aceite ou registraram os bloqueios restantes.

Resultado: [ ] aprovado  [ ] reprovado  [ ] aprovado com ressalvas

Bloqueios/ressalvas:

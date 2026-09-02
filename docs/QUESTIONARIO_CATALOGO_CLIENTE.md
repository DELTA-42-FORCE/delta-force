# Histórico — questionário de catálogo cadastral rígido (fora do MVP)

> **Não aplicar ao MVP atual.** O time aprovou a pasta digital flexível em 25 de
> agosto de 2026. Este questionário é preservado apenas como referência para uma
> futura repriorização de campos formais.

- **Versão:** 0.1 — 21 de agosto de 2026
- **Objetivo:** definir exatamente o que o sistema deve guardar e mostrar

O uso por **um único proprietário**, sem papéis ou permissões de outros usuários
no MVP, já está confirmado e não precisa ser decidido novamente.

Marque uma opção em cada pergunta. Se não souber alguma resposta, marque
**não sei**; esse item ficará pendente e não será programado por suposição.
Quando uma pergunta legitimamente não se aplicar, escreva **não se aplica** em
vez de deixar o espaço vazio.

## Antes de responder: não envie dados reais

Não envie login, senha, token, QR code, código de barras, assinatura, foto,
nome, CPF, RG/CIN, endereço, telefone ou e-mail reais. Aceitamos somente página
pública, formulário vazio ou exemplo criado do zero com dados inventados. Não
envie material real nem mesmo com tarjas, desfoque ou partes ocultadas.

## 1. Qual formulário do governo serve de modelo?

Preencha uma linha para **cada** serviço. Para cada linha, informe o nome exato
e uma fonte: link público ou formulário vazio/sintético.

| ID       | Nome exato do serviço/procedimento | Link público | Data da consulta | Versão/data exibida | Nome do arquivo vazio/sintético |
| -------- | ---------------------------------- | ------------ | ---------------- | ------------------- | ------------------------------- |
| FONTE-01 | __________                         | __________   | __________       | __________          | __________                      |
| FONTE-02 | __________                         | __________   | __________       | __________          | __________                      |
| FONTE-03 | __________                         | __________   | __________       | __________          | __________                      |

Se o formulário só aparece depois do login, informe apenas o nome exato do
procedimento e envie um formulário vazio ou exemplo criado com dados
inventados. Não envie tela real, ainda que ocultada, nem dados de acesso. Se uma
coluna não se aplicar, escreva **não se aplica**.

Associe cada fonte aos dados que ela pede:

| Fonte    | Dados/campos pedidos por essa fonte                            |
| -------- | -------------------------------------------------------------- |
| FONTE-01 | ______________________________________________________________ |
| FONTE-02 | ______________________________________________________________ |
| FONTE-03 | ______________________________________________________________ |

## 2. Quais dados serão usados no cadastro?

Para cada linha, marque uma opção em **Este dado será**:

- **O** = obrigatório;
- **P** = opcional;
- **C** = somente quando ocorrer uma condição;
- **N** = não usar;
- **?** = não sei ainda.

Se marcar **C**, escreva a condição completa.

| Dado                                 | Este dado será (O/P/C/N/?) | Condição, se houver            |
| ------------------------------------ | -------------------------- | ------------------------------ |
| Nome completo                        | ___                        | ______________________________ |
| Foto do cliente                      | ___                        | ______________________________ |
| E-mail                               | ___                        | ______________________________ |
| Endereço                             | ___                        | ______________________________ |
| CPF                                  | ___                        | ______________________________ |
| Tipo de identidade: RG antigo ou CIN | ___                        | ______________________________ |
| Título de eleitor                    | ___                        | ______________________________ |
| Certidão de nascimento               | ___                        | ______________________________ |
| Sexo informado no cadastro           | ___                        | ______________________________ |
| Reservista                           | ___                        | ______________________________ |
| Data de nascimento                   | ___                        | ______________________________ |
| Telefone/celular                     | ___                        | ______________________________ |
| Nome social                          | ___                        | ______________________________ |
| Nacionalidade                        | ___                        | ______________________________ |
| Naturalidade                         | ___                        | ______________________________ |
| Estado civil                         | ___                        | ______________________________ |
| Nome da mãe                          | ___                        | ______________________________ |
| Nome do pai                          | ___                        | ______________________________ |
| Outro: __________________            | ___                        | ______________________________ |

### Endereço

Marque os componentes que existirão e indique quais são obrigatórios:

| Componente                | Usar? (sim/não/?) | Obrigatório? (sim/não/condicional) | Quando será obrigatório? |
| ------------------------- | ----------------- | ---------------------------------- | ------------------------ |
| CEP                       | ___               | ___                                | ________________________ |
| Logradouro                | ___               | ___                                | ________________________ |
| Número                    | ___               | ___                                | ________________________ |
| Complemento               | ___               | ___                                | ________________________ |
| Bairro                    | ___               | ___                                | ________________________ |
| Município                 | ___               | ___                                | ________________________ |
| UF                        | ___               | ___                                | ________________________ |
| País                      | ___               | ___                                | ________________________ |
| Outro: __________________ | ___               | ___                                | ________________________ |

### Dados digitados e arquivos anexados

Para cada documento, marque se seus dados serão digitados, se haverá arquivo
anexado ou se haverá os dois.

| Documento              | Digitar dados? (sim/não/?) | Anexar arquivo? (sim/não/?) |
| ---------------------- | -------------------------- | --------------------------- |
| CPF                    | ___                        | ___                         |
| RG antigo              | ___                        | ___                         |
| CIN                    | ___                        | ___                         |
| Título de eleitor      | ___                        | ___                         |
| Certidão de nascimento | ___                        | ___                         |
| Reservista             | ___                        | ___                         |

- A foto mostrada no cadastro e a foto anexada em “documentos” serão o mesmo
  arquivo? **sim / não / não sei**

Quando houver dados digitados, marque cada subcampo com **O/P/C/N/?**, usando os
mesmos códigos da seção 2. Se marcar **C**, escreva a condição. Nenhuma célula
pode ficar vazia na aprovação.

| Documento              | Subcampo candidato    | Este subcampo será (O/P/C/N/?) | Condição |
| ---------------------- | --------------------- | ------------------------------ | -------- |
| CPF                    | Número                | ___                            | ________ |
| RG antigo              | Número                | ___                            | ________ |
| RG antigo              | Órgão emissor         | ___                            | ________ |
| RG antigo              | UF de emissão         | ___                            | ________ |
| RG antigo              | Data de emissão       | ___                            | ________ |
| CIN                    | Número/CPF            | ___                            | ________ |
| CIN                    | Órgão emissor         | ___                            | ________ |
| CIN                    | UF de emissão         | ___                            | ________ |
| CIN                    | Data de emissão       | ___                            | ________ |
| Título de eleitor      | Número                | ___                            | ________ |
| Título de eleitor      | Zona                  | ___                            | ________ |
| Título de eleitor      | Seção                 | ___                            | ________ |
| Certidão de nascimento | Matrícula/número      | ___                            | ________ |
| Certidão de nascimento | Cartório              | ___                            | ________ |
| Certidão de nascimento | Livro                 | ___                            | ________ |
| Certidão de nascimento | Folha                 | ___                            | ________ |
| Certidão de nascimento | Termo                 | ___                            | ________ |
| Certidão de nascimento | Data de emissão       | ___                            | ________ |
| Reservista             | Número                | ___                            | ________ |
| Reservista             | Série                 | ___                            | ________ |
| Reservista             | Categoria             | ___                            | ________ |
| Reservista             | Órgão emissor         | ___                            | ________ |
| Reservista             | Data de emissão       | ___                            | ________ |
| Outro                  | _____________________ | ___                            | ________ |

### Regras que precisam de resposta direta

- Regra já registrada: validar o CPF e impedir dois clientes com o mesmo CPF.
  **aprovo / solicito alteração / não sei**
- Se solicitou alteração, explique: ________________________________________
  Essa alteração não é aprovada por este questionário; ela exige mudança
  explícita no backlog e na issue antes da homologação.
- Quem não possui CPF pode ser cadastrado? **não / sim**, quando: ___________
- O cliente usa **RG antigo ou CIN**, nunca ambos? **sim / não / não sei**
- Quais opções devem existir no campo “sexo informado”? ____________________
- Pode escolher “não informar”? **sim / não / não sei**
- Regra exata do reservista: _______________________________________________
- Exceções à regra do reservista: __________________________________________

### O que acontece quando falta um dado obrigatório?

- [ ] não deixa salvar o cliente;
- [ ] salva como cadastro incompleto para terminar depois;
- [ ] outro: ______________________________________________________________

Se permitir cadastro incompleto, explique como identificar que ainda falta
informação e quando ele passa a ser completo: _______________________________

## 3. Lista final de documentos

PDF está confirmado para documentos. JPEG está confirmado para fotos. Preencha
todas as linhas necessárias para que a lista fique completa.

| Tipo de documento/foto    | Obrigatório, opcional, condicional ou não usar | Condição                   |
| ------------------------- | ---------------------------------------------- | -------------------------- |
| Foto do cliente           | __________                                     | __________________________ |
| Identidade — RG antigo    | __________                                     | __________________________ |
| Identidade — CIN          | __________                                     | __________________________ |
| CPF separado              | __________                                     | __________________________ |
| Título de eleitor         | __________                                     | __________________________ |
| Certidão de nascimento    | __________                                     | __________________________ |
| Reservista                | __________                                     | __________________________ |
| Outro: __________________ | __________                                     | __________________________ |
| Outro: __________________ | __________                                     | __________________________ |
| Outro: __________________ | __________                                     | __________________________ |

### Fotos, PDF e arquivos com problema

- JPEG será usado somente para a foto do cliente? **sim / não / não sei**
- Se não, quais documentos podem ser fotografados? _________________________
- PDF com várias páginas será aceito? **sim / não / não sei**
- Um PDF pode juntar frente e verso? **sim / não / não sei**
- Proposta: PDF protegido por senha, corrompido ou ilegível não será importado;
  o sistema mostrará o motivo no relatório. **aprovo / quero alterar / não sei**
- Se quiser alterar, explique: _____________________________________________

### Tamanho máximo de cada arquivo

**Decisão posterior registrada:** não há teto comercial fixo por PDF/JPEG. O
limite operacional é a capacidade livre do computador; o CRM grava por streaming
e recusa com mensagem clara a operação que não puder ser concluída sem conteúdo
parcial. Esta seção é mantida apenas como histórico do questionário.

### Quantidade e versões

- Para cada tipo, pode existir **um arquivo atual / vários arquivos atuais /
  depende do tipo / não sei**.
- Se depende do tipo, detalhe: _____________________________________________
- Ao enviar uma nova versão, a antiga deve ficar no histórico?
  **sim / não / não sei**
- Deve existir limite de versões antigas? **não / sim:** ______ / **não sei**

### O que acontece quando falta um documento obrigatório?

- [ ] salva o cliente e marca o documento como **pendente**;
- [ ] não deixa salvar o cliente;
- [ ] outro: ______________________________________________________________

Se salvar com pendência, ela será criada **automaticamente pelo sistema /
manualmente pelo proprietário / não sei**.

Quando um documento está **incorreto/incompleto**, o cliente continua salvo e o
proprietário pede correção? **sim / não / não sei**

Depois que um arquivo for recebido, a proposta é o proprietário fazer a
conferência e marcar manualmente um dos dois resultados:

- **pendente:** o documento esperado ainda não foi recebido; sua criação segue
  a resposta acima;
- **recebido/regular:** o arquivo foi recebido e o proprietário o conferiu como
  adequado;
- **incorreto/incompleto:** o arquivo foi recebido, mas a conferência manual
  encontrou documento errado, informação faltando ou problema de leitura.

- [ ] aprovo os três status, os significados e a conferência manual acima;
- [ ] quero alterar para: _________________________________________________
- [ ] não sei ainda.

## 4. Ficha do cliente em PDF

- Já existe um modelo? **não / sim** — envie somente uma cópia vazia.
- Se existe, informe nome/data/versão: _____________________________________
- Se não existe, o time apresentará um protótipo com dados inventados. Esse
  protótipo precisará de aprovação antes da programação final.
- Para qualquer campo marcado como “mascarado”, o formato exato da máscara deve
  aparecer e ser aprovado nesse modelo/protótipo.

Para cada dado abaixo, marque **mostrar completo**, **mostrar mascarado** ou
**não mostrar**. Para a foto, escolha somente **mostrar** ou **não mostrar**.

| Dado                         | Completo / mascarado / não mostrar |
| ---------------------------- | ---------------------------------- |
| Nome completo                | __________                         |
| Foto                         | mostrar / não mostrar              |
| E-mail                       | __________                         |
| Telefone                     | __________                         |
| Endereço                     | __________                         |
| CPF                          | __________                         |
| RG antigo                    | __________                         |
| CIN                          | __________                         |
| Título de eleitor            | __________                         |
| Certidão de nascimento       | __________                         |
| Reservista                   | __________                         |
| Outro aprovado: ____________ | __________                         |
| Outro aprovado: ____________ | __________                         |
| Outro aprovado: ____________ | __________                         |

Responder também:

- A ficha deve listar documentos e seus status? **sim / não / não sei**
- Quais informações da lista? tipo / status / data de envio / data de emissão /
  data de conferência / observação / outras: _______________________________
- Deve destacar documento pendente ou incorreto? **sim / não / não sei**
- Campo sem valor deve ser: **omitido / mostrado em branco / não sei**
- A foto pode ser ajustada sem cortar? **sim / não / não sei**
- Pode haver mais de uma página? **sim / não / não sei**
- Se houver várias páginas, deve numerá-las? **sim / não / não sei**
- Precisa de título, logotipo ou rodapé? ____________________________________
- Precisa de espaço para assinatura? **não / sim** — de quem: ______________

## 5. Confirmação das respostas

Uma resposta **não está pronta para homologação** enquanto houver campo vazio,
“não sei” ou ressalva sem solução. Depois de todas as respostas, o time deverá
registrar o catálogo técnico e apresentar o modelo/protótipo da ficha PDF. A
homologação final só ocorre quando esses dois artefatos também forem aprovados.

- [ ] Confirmo que revisei todas as respostas desta versão para o time preparar
      o catálogo técnico e o modelo/protótipo da ficha PDF.
- **Papel/identificador não pessoal de quem respondeu:** ___________________
- **Data (dia/mês/ano):** _________________________________________________
- **Referência do registro externo da resposta:** __________________________
- **Ressalvas:** nenhuma / _________________________________________________

O questionário preenchido e o registro externo da resposta não serão
versionados no repositório. Somente decisões sem dados pessoais serão
transcritas para o catálogo técnico.

Qualquer alteração posterior deverá gerar uma nova versão aprovada antes de
mudar o cadastro, os documentos ou a ficha PDF do sistema.

# Catálogo cadastral e documental — registro técnico para homologação

- **Status:** aguardando homologação do cliente — **não implementar ainda**
- **Versão do rascunho:** 0.1
- **Data:** 21 de agosto de 2026
- **Issue relacionada:** #14

Este documento interno transforma a resposta “os mesmos dados pedidos para
criar conta em sites do governo (`gov.br`)” em decisões objetivas. As perguntas
em linguagem simples ficam em `QUESTIONARIO_CATALOGO_CLIENTE.md`; as respostas
aprovadas devem ser transcritas aqui sem interpretação adicional.

Este registro não é contrato de API, banco, interface ou ficha PDF enquanto o
bloco de aprovação ao final não estiver preenchido.

## Como completar este registro

1. Colete as respostas no questionário do cliente e identifique a fonte `gov.br`.
2. Em cada linha, registre uma das opções: **obrigatório**, **opcional**,
   **condicional** ou **não usado**.
3. Para um item condicional, escreva a condição completa.
4. O time traduz a resposta aprovada para um tipo simples (**texto**, **data**,
   **sim/não**, **lista** ou **arquivo**), cardinalidade, formato e limites; a
   tradução também precisa ser revisada antes do status **aprovado**.
5. Não registre dados reais de clientes nem credenciais neste arquivo.
6. Preencha **não se aplica** quando um espaço for legitimamente inaplicável;
   nenhum espaço pode permanecer vazio no catálogo aprovado.

## 1. Decisões já confirmadas

Estas decisões vieram das respostas posteriores do cliente e não precisam ser
respondidas novamente:

- o CRM local será usado somente pelo proprietário; não há matriz de usuários,
  papéis ou permissões no MVP;
- o cadastro deve se basear nos dados pedidos para criar conta em serviços
  `gov.br`, mas o serviço/formulário exato ainda não foi identificado;
- documentos pessoais serão aceitos em **PDF**;
- arquivos de **foto** serão aceitos em **JPEG**; ainda é preciso confirmar se
  isso vale somente para a foto do cliente ou também para fotos de documentos;
- PNG, DOCX e outros formatos não fazem parte do MVP;
- a ficha cadastral em PDF faz parte do MVP;
- os documentos não terão vencimento operacional nem prazo de descarte definido;
- o acervo legado tem cerca de 500 documentos, inclusive arquivos possivelmente
  corrompidos, e o volume novo estimado é de 30 a 40 documentos.

O tamanho máximo de PDF/JPEG ainda não foi informado. Nenhum limite será
escolhido por hipótese.

## 2. Fonte `gov.br` a homologar

Registrar uma linha por serviço. Se não houver link público, usar somente
formulário vazio ou integralmente sintético. O SHA-256 é obrigatório apenas
quando houver arquivo anexado.

| ID       | Nome exato | Link público | Data da consulta | Versão/data exibida | Arquivo vazio/sintético e SHA-256 | Campos CAM de origem |
| -------- | ---------- | ------------ | ---------------- | ------------------- | --------------------------------- | -------------------- |
| FONTE-01 | __________ | __________   | __________       | __________          | __________                        | __________           |
| FONTE-02 | __________ | __________   | __________       | __________          | __________                        | __________           |
| FONTE-03 | __________ | __________   | __________       | __________          | __________                        | __________           |

Adicionar linhas se houver mais serviços e preencher **não se aplica** onde for
legítimo. Todo campo aprovado deve apontar para pelo menos uma `FONTE-*` ou ser
identificado explicitamente como decisão posterior do cliente. A expressão
genérica “conta no `gov.br`” não basta para definir o banco.

## 3. Campos citados no levantamento

As linhas abaixo são candidatas porque aparecem no PDF de requisitos. A presença
na fonte não define, por si só, obrigatoriedade nem formato.

### 3.1 Classificação e regra de negócio

| ID     | Campo candidato        | Regra já registrada                                                               | Obrigatório/opcional/condicional/não usado | Condição completa ou observação |
| ------ | ---------------------- | --------------------------------------------------------------------------------- | ------------------------------------------ | ------------------------------- |
| CAM-01 | Nome completo          | Citado em CAD-01                                                                  | __________                                 | __________                      |
| CAM-02 | Foto do cliente        | Citada em CAD-01; foto em JPEG                                                    | __________                                 | __________                      |
| CAM-03 | E-mail                 | Citado em CAD-01                                                                  | __________                                 | __________                      |
| CAM-04 | Endereço               | Citado em CAD-01                                                                  | __________                                 | __________                      |
| CAM-05 | CPF                    | Citado em CAD-02; validação e unicidade constam no backlog; separado no RG antigo | __________                                 | Regra para quem não possui: ___ |
| CAM-06 | Tipo de identidade     | RG antigo ou CIN, conforme CAD-03                                                 | __________                                 | Outras opções: __________       |
| CAM-07 | Dados do RG antigo     | O CPF permanece separado                                                          | __________                                 | __________                      |
| CAM-08 | Dados da CIN           | Novo modelo de identidade                                                         | __________                                 | __________                      |
| CAM-09 | Título de eleitor      | Citado em CAD-02                                                                  | __________                                 | __________                      |
| CAM-10 | Certidão de nascimento | Citada em CAD-02                                                                  | __________                                 | __________                      |
| CAM-11 | Sexo cadastrado        | Necessário para a regra provisória de reservista                                  | __________                                 | __________                      |
| CAM-12 | Reservista             | Relacionado no levantamento ao sexo masculino                                     | __________                                 | Regra e exceções: __________    |

### 3.2 Tipo, formato e cardinalidade

Preencher uma linha por campo simples. Para campo composto, preencher também os
subcampos da seção seguinte.

| ID     | Tipo do dado | Um ou vários | Formato, máscara ou opções permitidas | Mínimo | Máximo  |
| ------ | ------------ | ------------ | ------------------------------------- | ------ | ------- |
| CAM-01 | __________   | __________   | __________                            | ______ | ______  |
| CAM-02 | arquivo      | __________   | JPEG; detalhes na seção 5             | n/a    | seção 5 |
| CAM-03 | __________   | __________   | __________                            | ______ | ______  |
| CAM-04 | composto     | __________   | subcampos na seção 3.3                | n/a    | n/a     |
| CAM-05 | __________   | __________   | __________                            | ______ | ______  |
| CAM-06 | lista        | um           | RG antigo / CIN / outras: __________  | n/a    | n/a     |
| CAM-07 | composto     | __________   | subcampos na seção 3.3                | n/a    | n/a     |
| CAM-08 | composto     | __________   | subcampos na seção 3.3                | n/a    | n/a     |
| CAM-09 | composto     | __________   | subcampos na seção 3.3                | n/a    | n/a     |
| CAM-10 | composto     | __________   | subcampos na seção 3.3                | n/a    | n/a     |
| CAM-11 | lista        | um           | opções e “não informado”: __________  | n/a    | n/a     |
| CAM-12 | composto     | __________   | subcampos na seção 3.3                | n/a    | n/a     |

“Mínimo/máximo” significa quantidade de caracteres para texto, faixa para
número ou quantidade de itens. Datas devem indicar se aceitam data incompleta.
Não use um número como exemplo se ele pertencer a um cliente real.

### 3.3 Subcampos de endereço e documentos

Estes subcampos são **candidatos**, não decisões. Marque cada um separadamente e
adicione/remova linhas conforme o formulário `gov.br` identificado.

| Grupo                  | Subcampo candidato    | Classificação | Condição   | Tipo e formato | Mínimo/máximo |
| ---------------------- | --------------------- | ------------- | ---------- | -------------- | ------------- |
| Endereço               | CEP                   | __________    | __________ | __________     | __________    |
| Endereço               | Logradouro            | __________    | __________ | __________     | __________    |
| Endereço               | Número                | __________    | __________ | __________     | __________    |
| Endereço               | Complemento           | __________    | __________ | __________     | __________    |
| Endereço               | Bairro                | __________    | __________ | __________     | __________    |
| Endereço               | Município             | __________    | __________ | __________     | __________    |
| Endereço               | UF                    | __________    | __________ | __________     | __________    |
| Endereço               | País                  | __________    | __________ | __________     | __________    |
| RG antigo              | Número                | __________    | __________ | __________     | __________    |
| RG antigo              | Órgão emissor         | __________    | __________ | __________     | __________    |
| RG antigo              | UF de emissão         | __________    | __________ | __________     | __________    |
| RG antigo              | Data de emissão       | __________    | __________ | __________     | __________    |
| CIN                    | Número/CPF            | __________    | __________ | __________     | __________    |
| CIN                    | Órgão/UF de emissão   | __________    | __________ | __________     | __________    |
| CIN                    | Data de emissão       | __________    | __________ | __________     | __________    |
| Título de eleitor      | Número                | __________    | __________ | __________     | __________    |
| Título de eleitor      | Zona                  | __________    | __________ | __________     | __________    |
| Título de eleitor      | Seção                 | __________    | __________ | __________     | __________    |
| Certidão de nascimento | Matrícula/número      | __________    | __________ | __________     | __________    |
| Certidão de nascimento | Cartório              | __________    | __________ | __________     | __________    |
| Certidão de nascimento | Livro/folha/termo     | __________    | __________ | __________     | __________    |
| Certidão de nascimento | Data de emissão       | __________    | __________ | __________     | __________    |
| Reservista             | Número                | __________    | __________ | __________     | __________    |
| Reservista             | Série/categoria       | __________    | __________ | __________     | __________    |
| Reservista             | Órgão/data de emissão | __________    | __________ | __________     | __________    |
| Outro                  | __________________    | __________    | __________ | __________     | __________    |

Para cada grupo composto, a classificação do grupo e a de seus subcampos devem
ser compatíveis. Exemplo: se RG antigo for condicional, registre a condição no
grupo e quais subcampos são obrigatórios quando essa condição ocorrer.

### 3.4 Dado digitado, anexo ou ambos

O catálogo deve distinguir o dado pesquisável no cadastro do arquivo guardado.

| Referência                   | Dados serão digitados? | Arquivo será anexado? | Relação entre dado e anexo                     |
| ---------------------------- | ---------------------- | --------------------- | ---------------------------------------------- |
| CAM-02 / DOC-01 — foto       | n/a                    | __________            | mesmo arquivo / arquivos distintos: __________ |
| CAM-05 / DOC-04 — CPF        | __________             | __________            | __________                                     |
| CAM-07 / DOC-02 — RG antigo  | __________             | __________            | __________                                     |
| CAM-08 / DOC-03 — CIN        | __________             | __________            | __________                                     |
| CAM-09 / DOC-05 — título     | __________             | __________            | __________                                     |
| CAM-10 / DOC-06 — certidão   | __________             | __________            | __________                                     |
| CAM-12 / DOC-07 — reservista | __________             | __________            | __________                                     |

### 3.5 Efeito de campo obrigatório

- **Campo obrigatório ausente:** bloquear o primeiro salvamento / permitir
  rascunho incompleto / outro: _____________________________________________
- **Se houver rascunho:** quem pode vê-lo, como é identificado e o que o torna
  completo: ________________________________________________________________
- **Campo condicional:** a condição é avaliada quando: ______________________

## 4. Campos não citados que precisam ser confirmados na fonte

Os itens abaixo são apenas perguntas comuns em cadastros. Eles **não aparecem
como campos explícitos no levantamento** e só entrarão no produto se o cliente
confirmar que fazem parte do formulário de referência.

| Campo candidato           | Classificação | Condição | Tipo/cardinalidade | Formato/opções | Mínimo/máximo |
| ------------------------- | ------------- | -------- | ------------------ | -------------- | ------------- |
| Data de nascimento        | __________    | ________ | __________         | __________     | __________    |
| Telefone/celular          | __________    | ________ | __________         | __________     | __________    |
| Nome social               | __________    | ________ | __________         | __________     | __________    |
| Nacionalidade             | __________    | ________ | __________         | __________     | __________    |
| Naturalidade              | __________    | ________ | __________         | __________     | __________    |
| Estado civil              | __________    | ________ | __________         | __________     | __________    |
| Nome da mãe               | __________    | ________ | __________         | __________     | __________    |
| Nome do pai               | __________    | ________ | __________         | __________     | __________    |
| Outro: __________________ | __________    | ________ | __________         | __________     | __________    |

## 5. Catálogo de documentos

Para cada tipo, marque **obrigatório**, **opcional**, **condicional** ou
**não usado**. Documento pessoal é PDF; foto do cliente é JPEG.

### 5.1 Política técnica proposta para PDF/JPEG

Esta tradução técnica precisa ser aprovada junto com o catálogo:

- PDF: extensão `.pdf`, conteúdo reconhecido como PDF e tipo esperado
  `application/pdf`;
- JPEG: extensões `.jpg` e `.jpeg`, conteúdo reconhecido como JPEG e tipo
  esperado `image/jpeg`;
- o sistema não confiará somente no nome/extensão ou no tipo informado pelo
  navegador; extensão e conteúdo divergentes serão rejeitados;
- arquivos vazios, truncados, estruturalmente ilegíveis ou protegidos por senha
  devem ser rejeitados com motivo claro e, na importação, constar do relatório.

Aprovação:

- [ ] aprovar a política acima;
- [ ] alterar para: ________________________________________________________

O limite será registrado em **MiB** e também em número exato de bytes
(`1 MiB = 1.048.576 bytes`), evitando a ambiguidade de “MB”.

### 5.2 Tipos, limites e multiplicidade

| ID     | Tipo candidato            | Formato          | Classificação | Condição | Máximo (MiB/bytes) | Máximo de arquivos ativos | Preservar versões antigas? |
| ------ | ------------------------- | ---------------- | ------------- | -------- | ------------------ | ------------------------- | -------------------------- |
| DOC-01 | Foto do cliente           | JPEG             | __________    | ________ | ______ / ______    | __________                | sim / não                  |
| DOC-02 | Identidade — RG antigo    | PDF              | __________    | ________ | ______ / ______    | __________                | sim / não                  |
| DOC-03 | Identidade — CIN          | PDF              | __________    | ________ | ______ / ______    | __________                | sim / não                  |
| DOC-04 | CPF separado              | PDF              | __________    | ________ | ______ / ______    | __________                | sim / não                  |
| DOC-05 | Título de eleitor         | PDF              | __________    | ________ | ______ / ______    | __________                | sim / não                  |
| DOC-06 | Certidão de nascimento    | PDF              | __________    | ________ | ______ / ______    | __________                | sim / não                  |
| DOC-07 | Reservista                | PDF              | __________    | ________ | ______ / ______    | __________                | sim / não                  |
| DOC-08 | Outro: __________________ | PDF              | __________    | ________ | ______ / ______    | __________                | sim / não                  |
| DOC-09 | Outro: __________________ | PDF/JPEG: ______ | __________    | ________ | ______ / ______    | __________                | sim / não                  |
| DOC-10 | Outro: __________________ | PDF/JPEG: ______ | __________    | ________ | ______ / ______    | __________                | sim / não                  |

Responder também:

- CAM-02 e DOC-01 representam o mesmo arquivo de foto? **sim / não**
- JPEG será exclusivo da foto do cliente? **sim / não**
- Se não, quais documentos também podem ser fotografados? ___________________
- Um PDF pode reunir frente e verso ou páginas do mesmo documento? **sim / não**
- PDF gerado por scanner e PDF com várias páginas são aceitos? **sim / não**
- Ao enviar uma nova versão, a antiga fica apenas no histórico? **sim / não**
- Há limite total de versões históricas? não / sim — quantidade: ____________

### 5.3 Efeito de documento obrigatório

- **Documento obrigatório ausente:** permitir cliente salvo e marcar pendente /
  bloquear cadastro / outro: ______________________________________________
- **Criação da pendência, se o cadastro for salvo:** automática / manual / não
  se aplica: _______________________________________________________________
- **Documento incorreto/incompleto:** manter cliente e solicitar correção /
  bloquear outra ação — qual: __________ / outro: __________________________
- **Condição para um cliente/documento ser considerado regular:** ___________

Após o recebimento, os resultados são atribuídos manualmente pelo proprietário:

- **pendente:** documento esperado ainda não recebido; criação automática ou
  manual conforme a regra acima;
- **recebido/regular:** recebido e conferido manualmente como adequado;
- **incorreto/incompleto:** recebido, mas a conferência manual identificou
  documento errado, informação faltante ou problema de leitura.

Aprovação:

- [ ] manter exatamente esses três status e significados;
- [ ] alterar para: ________________________________________________________

## 6. Ficha cadastral em PDF do MVP

A inclusão no MVP está confirmada; conteúdo e layout ainda não estão.

- **Existe um formulário/modelo atual?** não / sim — anexar cópia vazia e
  informar nome, data ou versão: ___________________________________________
- **Se não existe, qual protótipo com dados sintéticos foi aprovado?**
  arquivo/versão: __________________________________________________________
- **Tamanho da página:** A4 / outro: _______________________________________
- **Campos que devem aparecer:** listar IDs CAM: ___________________________
- **Ordem ou grupos dos campos:** __________________________________________
- **Máscaras de CPF, datas, CEP e demais campos:** _________________________
- **Campo sem valor:** omitir / mostrar em branco / texto: _________________
- **A foto deve aparecer?** não / sim — tamanho: ___________________________
- **Tratamento da foto:** ajustar sem corte / cortar / outro: ______________
- **Deve listar documentos e status?** não / sim
- **Colunas exatas da lista documental:** _________________________________
- **Deve destacar pendentes/incorretos?** não / sim — como: _______________
- **Conteúdo longo:** quebrar linha / reduzir fonte / outro: _______________
- **Mais de uma página:** permitir / não permitir
- **Se houver mais de uma página:** repetir cabeçalho: sim / não; numerar:
  sim / não; regra de continuação: _________________________________________
- **Título, logotipo e rodapé aprovados:** _________________________________
- **Precisa de espaço para assinatura?** não / sim — de quem: ______________
- **Padrão do nome do arquivo:** ___________________________________________

Se não houver modelo existente, o time deverá apresentar um protótipo com dados
sintéticos para uma rodada separada de aprovação visual.

## 7. Decisões que bloqueiam a implementação

- [ ] serviço/formulário `gov.br` identificado;
- [ ] data da consulta e, quando existirem, versão/hash da fonte registrados;
- [ ] todos os campos classificados e seus formatos/limites aprovados;
- [ ] efeito de campo obrigatório ausente aprovado;
- [ ] uso como dado digitado, anexo ou ambos aprovado por documento;
- [ ] componentes de endereço aprovados;
- [ ] dados digitados de RG, CIN, título, certidão e reservista aprovados;
- [ ] regra condicional do reservista e suas exceções aprovadas;
- [ ] tipos documentais, condições e multiplicidade aprovados;
- [ ] extensões, MIME/conteúdo e tratamento de arquivo ilegível aprovados;
- [ ] tamanho máximo em MiB e bytes por PDF/JPEG aprovado;
- [ ] limites de arquivos ativos e histórico de versões aprovados;
- [ ] efeito de documento obrigatório/irregular aprovado;
- [ ] significados dos status, criação da pendência e conferência manual após
      recebimento aprovados;
- [ ] protótipo/modelo identificado e conteúdo/layout da ficha PDF aprovados;
- [ ] máscaras, foto e paginação/overflow da ficha PDF aprovados;
- [ ] respostas sem dados pessoais reais anexados à decisão.

Enquanto qualquer item estiver aberto, as issues dependentes podem receber
somente backlog, critérios de aceite e plano de testes. É proibido implementar
schema, migration, API, interface, upload ou geração de PDF antes da homologação.

## 8. Homologação

Qualquer campo vazio, resposta “não sei” ou ressalva sem solução mantém o
catálogo bloqueado. A aprovação abaixo vale para a versão inteira deste arquivo
e para o modelo/protótipo da ficha PDF aqui identificado.

- **Aprovado por (papel/identificador não pessoal):** _______________________
- **Data (dia/mês/ano):** _________________________________________________
- **Versão aprovada:** _____________________________________________________
- **Modelo/protótipo da ficha PDF aprovado:** ______________________________
- **Referência do registro externo de aprovação:** _________________________
- **Ressalvas:** ___________________________________________________________

O questionário preenchido e a mensagem/registro externo de aprovação não devem
ser commitados. Somente decisões sanitizadas e o identificador não pessoal são
versionados aqui.

Após a homologação, este arquivo deverá ser atualizado com as respostas finais,
ter o status alterado para **aprovado** e se tornar a fonte dos modelos,
validações, migrations, testes e da ficha cadastral do MVP.

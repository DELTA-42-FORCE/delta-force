# Backlog derivado do levantamento de requisitos

Este arquivo é a fonte para abertura inicial de issues. Cada seção abaixo corresponde a uma issue; os IDs finais serão os números criados no GitHub. As pendências devem ser resolvidas antes de colocar a issue relacionada em **Ready**.

## MVP

### 1. Formalizar a pasta digital flexível

**Labels:** `type: feature`, `area: docs`, `priority: mvp`.

**Critérios de aceite:** criar cliente requer somente nome de identificação;
demais informações e documentos são opcionais e podem ser incluídos depois.
PDF/JPEG são os formatos aceitos, sem teto comercial fixo por arquivo: a
capacidade livre do disco determina o limite operacional. Não há
catálogo rígido de `gov.br`, regra de reservista ou documento obrigatório. No
MVP há somente o proprietário, portanto não existe matriz de papéis.

### 2. Configurar e autenticar o proprietário local

**Labels:** `type: feature`, `area: api`, `area: web`, `priority: mvp`.

**Critérios de aceite:** primeira execução permite criar a conta do proprietário
sem segredos em código/ambiente; proprietário autentica-se no aplicativo; sessão
inválida não acessa recursos; tokens são protegidos em repouso; não existe rota
ou tela de login do cliente. Atende ACC-01, ACC-04 e NF-01.

### 3. Gerenciar usuários autorizados e papéis aprovados

**Labels:** `type: feature`, `area: api`, `area: web`, `priority: future`.
Fora do MVP: somente o proprietário utilizará o CRM local.

**Critérios de aceite:** administrador cria, consulta, edita, ativa/desativa usuários; autorização respeita a matriz aprovada. Atende ACC-02 e ACC-03.

### 4. Criar fundação de auditoria de ações sensíveis

**Labels:** `type: security`, `area: api`, `priority: mvp`. **Depende de:** 2.

**Critérios de aceite:** ações de consulta, inclusão, edição, importação,
download, backup e restauração relevantes registram ator, data/hora, recurso e
resultado; acesso sem sessão válida é negado. Atende NF-02 e NF-06.

### 5. Modelar e persistir a pasta de cliente

**Labels:** `type: feature`, `area: api`, `priority: mvp`. **Depende de:** 1.

**Critérios de aceite:** modelo começa com nome de identificação obrigatório e
campos opcionais extensíveis; migration e testes garantem que dados podem ser
completados gradualmente, sem exigir CPF, reservista ou arquivos. Depende da
transição para SQLite.

### 6. Disponibilizar cadastro, busca, consulta e edição de clientes

**Labels:** `type: feature`, `area: api`, `area: web`, `priority: mvp`. **Depende de:** 2, 4 e 5.

**Critérios de aceite:** proprietário cria, pesquisa, consulta e edita cliente;
nome é obrigatório e os campos adicionais são opcionais. Dados só são visíveis
na sessão autenticada.

### 7. Reavaliar campos formais e reservista

**Labels:** `type: feature`, `area: api`, `area: web`, `priority: future`.

Fora do MVP. Só retomar se uma necessidade operacional concreta do proprietário
justificar campos ou validações rígidas.

### 8. Provisionar armazenamento privado de documentos e política operacional

**Labels:** `type: security`, `area: api`, `area: infra`, `priority: mvp`. **Depende de:** 5.

**Critérios de aceite:** documentos PDF/JPEG são armazenados fora do banco em
área privada local; acesso exige sessão válida; retenção sem prazo de descarte,
backup em HD externo e recuperação são documentados; nenhuma credencial fica no
repositório. A escrita é em streaming, verifica espaço livre e não publica
arquivo parcial em caso de falta de disco; o CRM oferece abrir pasta e exportar
cópia sem tratar alterações manuais externas como ações auditadas. Atende
DOC-02, NF-03 e NF-04.

### 9. Anexar e consultar documentos de clientes por tipo

**Labels:** `type: feature`, `area: api`, `area: web`, `priority: mvp`. **Depende de:** 4, 6 e 8.

**Critérios de aceite:** proprietário anexa manualmente PDF/JPEG a um cliente e
tipo documental; consulta e download autorizados funcionam; formatos/tamanhos
inválidos ou falta de espaço têm mensagem clara. Não há teto comercial fixo;
o limite é a capacidade operacional do disco. Atende DOC-01, DOC-04 e NF-05.

### 10. Implementar checklist e status de documentos

**Labels:** `type: feature`, `area: api`, `area: web`, `priority: mvp`. **Depende de:** 1 e 9.

**Critérios de aceite:** cada documento possui status pendente, recebido/regular
ou incorreto/incompleto; não há vencimento operacional; alterações têm histórico
e podem ser filtradas para comunicação. Atende DOC-03 e NF-06.

### 11. Criar modelos de e-mail e seleção de destinatários

**Labels:** `type: feature`, `area: api`, `area: web`, `priority: mvp`. **Depende de:** 1, 6 e 10.

**Critérios de aceite:** administrador mantém modelos aprovados; pode selecionar clientes por pendência/status; variáveis como nome e situação são preenchidas sem expor destinatários entre si. Atende Comunicação MVP.

### 12. Enviar mala direta e registrar o histórico de disparos

**Labels:** `type: feature`, `area: api`, `area: web`, `priority: mvp`. **Depende de:** 4 e 11.

**Critérios de aceite:** envio em lote registra destinatário, assunto, modelo/conteúdo renderizado, horário e resultado; falhas são identificáveis e não duplicam envio sem confirmação. Atende Comunicação MVP e NF-06.

### 13. Definir operação local Windows, LGPD e resposta a incidentes

**Labels:** `type: security`, `area: infra`, `area: docs`, `priority: mvp`, `status: blocked`.

**Critérios de aceite:** instalação local Windows, backup/restauração por HD
externo, responsáveis e guarda sem prazo definido são documentados; existe
procedimento para solicitação do titular e incidente. Atende NF-03 e NF-04.

### 14. Validar o cenário ponta a ponta do MVP

**Labels:** `type: chore`, `area: api`, `area: web`, `priority: mvp`. **Depende de:** 2 a 12.

**Critérios de aceite:** proprietário cria a conta, autentica-se, cadastra
cliente, anexa/classifica/importa documentos, gera ficha PDF, seleciona uma
pendência, envia e-mail, consulta históricos e executa/restaura um backup de HD
externo. Este é o aceite do MVP local.

## Etapa posterior — priorizar depois do MVP

| Issue | Requisitos | Prioridade |
| --- | --- | --- |
| Definir regra operacional que libera parcelamento | pendência financeira | next |
| Cadastrar contrato, entrada, saldo, parcelas e vencimentos | FIN-01 | next |
| Integrar emissão e consulta de boleto PagBank | FIN-02 | next |
| Calcular juros de 1% ao dia e multa única de 2% | FIN-03 | next |
| Emitir segunda via de boleto e recibo | FIN-04 | next |
| Criar relatório financeiro por período e situação | REL-02, REL-03 | next |
| Integrar emissão fiscal | FIN-05 | future — depende de definição contábil/fiscal |
| Avaliar portal de cliente e IA para documentos | seção 10 | future — requer prova de conceito de custo, privacidade e precisão |

### Regras financeiras confirmadas para a etapa posterior

- sinal fixo de R$ 2.000,00 em todos os contratos;
- saldo em quantidade `N`, definida no contrato, de parcelas iguais, com
  vencimento no mesmo dia de cada período;
- estados persistidos `Ativo`, `Quitado` e `Cancelado`, com atraso derivado
  automaticamente das parcelas vencidas e não pagas do contrato ativo;
- valores em BRL com precisão exata, sem ponto flutuante binário;
- vencimentos representados somente como data civil, sem horário ou fuso.

Antes de mover as issues financeiras para **Ready**, ainda é necessário definir:
o evento que libera o parcelamento (#28), como estabelecer o primeiro
vencimento, o tratamento dos dias 29, 30 e 31 e a alocação da diferença de
centavos quando o saldo não for divisível igualmente. Essas respostas não
alteram a prioridade do MVP.

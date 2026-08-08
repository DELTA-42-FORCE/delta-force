# Backlog derivado do levantamento de requisitos

Este arquivo é a fonte para abertura inicial de issues. Cada seção abaixo corresponde a uma issue; os IDs finais serão os números criados no GitHub. As pendências devem ser resolvidas antes de colocar a issue relacionada em **Ready**.

## MVP

### 1. Definir catálogo cadastral, documentos aceitos e matriz de permissões

**Labels:** `type: feature`, `area: docs`, `priority: mvp`, `status: blocked`.

**Critérios de aceite:** catálogo de campos obrigatórios/opcionais; lista de documentos, formatos e tamanhos; matriz administrador × usuário autorizado aprovada; prioridade da ficha PDF formalizada. Atende às pendências de ACC-03, CAD-01/02/05 e NF-05.

### 2. Implementar autenticação com contas internas individuais

**Labels:** `type: feature`, `area: api`, `area: web`, `priority: mvp`.

**Critérios de aceite:** usuário interno consegue autenticar-se com conta própria; sessão inválida não acessa recursos; não existe rota ou tela de login do cliente. Atende ACC-01, ACC-04 e NF-01.

### 3. Gerenciar usuários autorizados e papéis aprovados

**Labels:** `type: feature`, `area: api`, `area: web`, `priority: mvp`. **Depende de:** 1 e 2.

**Critérios de aceite:** administrador cria, consulta, edita, ativa/desativa usuários; autorização respeita a matriz aprovada. Atende ACC-02 e ACC-03.

### 4. Criar fundação de auditoria e autorização de ações sensíveis

**Labels:** `type: security`, `area: api`, `priority: mvp`. **Depende de:** 2 e 3.

**Critérios de aceite:** ações de consulta, inclusão, edição e download relevantes registram ator, data/hora, recurso e resultado; acesso sem permissão é negado. Atende NF-02 e NF-06.

### 5. Modelar e persistir o cadastro de clientes

**Labels:** `type: feature`, `area: api`, `priority: mvp`. **Depende de:** 1.

**Critérios de aceite:** modelo contempla foto, contatos, endereço, CPF, tipo de identidade, RG/CIN, certidão e demais campos homologados; migração e testes cobrem as regras de identidade. Atende CAD-01, CAD-02 e CAD-03.

### 6. Disponibilizar cadastro, busca, consulta e edição de clientes

**Labels:** `type: feature`, `area: api`, `area: web`, `priority: mvp`. **Depende de:** 2, 4 e 5.

**Critérios de aceite:** usuário autorizado cria, pesquisa, consulta e edita cliente; CPF tem validação e unicidade; dados são visíveis somente a quem tem autorização.

### 7. Aplicar regra de reservista conforme sexo cadastrado

**Labels:** `type: feature`, `area: api`, `area: web`, `priority: mvp`. **Depende de:** 5 e 6.

**Critérios de aceite:** ao indicar sexo masculino, o cadastro solicita e valida a presença do dado de reservista conforme a regra homologada; demais casos seguem o catálogo aprovado. Atende CAD-04.

### 8. Provisionar armazenamento privado de documentos e política operacional

**Labels:** `type: security`, `area: api`, `area: infra`, `priority: mvp`. **Depende de:** 1.

**Critérios de aceite:** documentos são armazenados fora do banco em área privada; acesso usa autorização; existem decisão de retenção, backup e recuperação; nenhuma credencial fica no repositório. Atende DOC-02, NF-03 e NF-04.

### 9. Anexar e consultar documentos de clientes por tipo

**Labels:** `type: feature`, `area: api`, `area: web`, `priority: mvp`. **Depende de:** 4, 6 e 8.

**Critérios de aceite:** operador anexa arquivo manualmente a um cliente e tipo documental; consulta e download autorizados funcionam; formatos/tamanhos inválidos têm mensagem clara. Atende DOC-01, DOC-04 e NF-05.

### 10. Implementar checklist e status de documentos

**Labels:** `type: feature`, `area: api`, `area: web`, `priority: mvp`. **Depende de:** 1 e 9.

**Critérios de aceite:** cada documento possui status pendente, recebido/regular ou incorreto/incompleto; alterações têm histórico e podem ser filtradas para comunicação. Atende DOC-03 e NF-06.

### 11. Criar modelos de e-mail e seleção de destinatários

**Labels:** `type: feature`, `area: api`, `area: web`, `priority: mvp`. **Depende de:** 1, 6 e 10.

**Critérios de aceite:** administrador mantém modelos aprovados; pode selecionar clientes por pendência/status; variáveis como nome e situação são preenchidas sem expor destinatários entre si. Atende Comunicação MVP.

### 12. Enviar mala direta e registrar o histórico de disparos

**Labels:** `type: feature`, `area: api`, `area: web`, `priority: mvp`. **Depende de:** 4 e 11.

**Critérios de aceite:** envio em lote registra destinatário, assunto, modelo/conteúdo renderizado, horário e resultado; falhas são identificáveis e não duplicam envio sem confirmação. Atende Comunicação MVP e NF-06.

### 13. Definir operação de produção, LGPD e resposta a incidentes

**Labels:** `type: security`, `area: infra`, `area: docs`, `priority: mvp`, `status: blocked`.

**Critérios de aceite:** hospedagem, capacidade, backup, restauração, responsáveis e política de guarda/descarte são aprovados; existe procedimento para solicitação do titular e incidente. Atende NF-03 e NF-04.

### 14. Validar o cenário ponta a ponta do MVP

**Labels:** `type: chore`, `area: api`, `area: web`, `priority: mvp`. **Depende de:** 2 a 12.

**Critérios de aceite:** usuário autorizado autentica-se, cadastra cliente, anexa/classifica documentos, seleciona uma pendência, envia e-mail em lote e consulta os históricos. Este é o aceite da seção 12 do levantamento.

## Etapa posterior — priorizar depois do MVP

| Issue | Requisitos | Prioridade |
| --- | --- | --- |
| Definir regra operacional que libera parcelamento | pendência financeira | next |
| Cadastrar contrato, entrada, saldo, parcelas e vencimentos | FIN-01 | next |
| Integrar emissão e consulta de boleto PagBank | FIN-02 | next |
| Calcular juros de 1% ao dia e multa única de 2% | FIN-03 | next |
| Emitir segunda via de boleto e recibo | FIN-04 | next |
| Criar relatório financeiro por período e situação | REL-02, REL-03 | next |
| Gerar ficha cadastral em PDF | CAD-05, REL-01 | next — depende da decisão de prioridade |
| Integrar emissão fiscal | FIN-05 | future — depende de definição contábil/fiscal |
| Avaliar portal de cliente e IA para documentos | seção 10 | future — requer prova de conceito de custo, privacidade e precisão |

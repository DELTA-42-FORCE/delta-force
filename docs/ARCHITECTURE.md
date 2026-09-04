# Arquitetura inicial

O repositório é um monorepo: a API e a interface compartilham documentação, automações e infraestrutura, mas preservam dependências e testes isolados.

## Desenvolvimento e dados locais

```text
apps/web ────────────────► apps/api ─────────────► SQLite em arquivo
  interface interna          autenticação e regras      dados operacionais
                              │
                              ├──────────────────────► filesystem privado
                              │                         documentos PDF/JPEG
                              └──────────────────────► provedor de e-mail
                                                        (Mailpit, quando aplicável)
```

SQLite e filesystem privado são o alvo para desenvolvimento e entrega, conforme
a [ADR 0003](adr/0003-sqlite-como-persistencia-local.md). Docker, PostgreSQL e
MinIO não são pré-requisitos. A fundação SQLite foi entregue pela #54; o suporte
PostgreSQL restante existe apenas no check legado de compatibilidade e não é
base para funcionalidades novas.

## Entrega ao cliente

O cenário aprovado é um aplicativo local Windows, usado somente pelo
proprietário e com dados/documentos no próprio dispositivo. A
[ADR 0002](adr/0002-aplicativo-local-windows.md), com status **Aceita**,
define a entrega: Tauri 2 como shell e supervisor mínimo, React na janela e
FastAPI empacotada com PyInstaller `onedir`. A implementação da #57 materializa
esse desenho em `apps/desktop`: o Rust inicia o sidecar como recurso privado,
mantém-no em um Windows Job Object, envia o segredo de bootstrap por `stdin` e
devolve à janela uma capability de uma única execução por IPC. A API usa porta
dinâmica em `127.0.0.1`, recusa origem/Host/capability inválidos e não expõe
OpenAPI no runtime desktop. A persistência SQLite já está decidida pela ADR 0003
e não faz parte do escopo da ADR 0002. O spike da issue #43 (PR #49) permanece
experimento isolado e não deve ser integrado ao produto.

Versão/edição do Windows, proteção do disco, assinatura do instalador e método de
recuperação do backup ainda são decisões operacionais pendentes. Elas não devem
ser registradas como fatos confirmados pelo cliente.

Na API, a evolução deve manter as fronteiras abaixo:

- `domain`: entidades, regras e interfaces sem dependência de HTTP ou banco;
- `application`: casos de uso, DTOs e autorização;
- `infrastructure`: SQLite, armazenamento de arquivos, e-mail e integrações;
- `presentation`: rotas HTTP, serialização e autenticação de requisição.

Essa separação reproduz o princípio adotado no Genesi, mas inicia pequena: não crie camadas vazias sem uma funcionalidade real. Toda decisão estrutural que mude este desenho deve ser registrada em `docs/adr/`.

## Persistência

SQLite será acessado somente pelo adaptador em
`apps/api/src/crm_api/infrastructure/database.py`. A configuração não deve ser
lida diretamente por rotas HTTP. Migrations são controladas pelo Alembic em
`apps/api/alembic/`; cada alteração de esquema futura requer migration reversível
e teste correspondente. A fundação persistente SQLite já foi portada pela #54;
as próximas entidades devem usar esse adaptador, sem acoplamento ao PostgreSQL.

Na instalação do cliente, documentos continuarão fora do banco e em área privada
gerenciada pela aplicação; somente metadados podem ser persistidos no banco. O
CRM oferece ao proprietário abrir a pasta local e exportar cópias. Arquivos
alterados diretamente pelo Windows não são ações auditadas nem atualizam os
metadados, portanto a alteração de documentos gerenciados deve ocorrer pelo
CRM. Backup e restauração devem contemplar banco, documentos e metadados como
uma unidade.

## Armazenamento de documentos

A fundação entregue pela #21 vive em
`apps/api/src/crm_api/infrastructure/documents/`. A árvore privada fica ao lado
do arquivo SQLite — `DOCUMENTS_ROOT` só é necessário quando o banco não é um
arquivo local — para que o snapshot da #44 trate banco, documentos e metadados
como uma unidade. A tabela `documents` guarda nome declarado, formato, tamanho,
checksum e a chave interna do arquivo; o binário nunca entra no banco e a chave
deriva apenas do identificador do documento, nunca do nome enviado.

A gravação é sempre por streaming: o formato vem da assinatura lida no início do
fluxo — a extensão declarada só é aceita se concordar com ele —, a capacidade
livre é verificada antes e durante a escrita, e o arquivo só aparece no destino
final por `os.replace` depois de íntegro e sincronizado. Qualquer falha remove o
arquivo parcial e também o que já tenha sido publicado, inclusive quando a falha
ocorre depois do `os.replace`; um documento cujos metadados não persistirem é
descartado junto do rollback da transação.

As regras de nome ficam em `domain/documents/naming.py` porque valem tanto para
o arquivo quanto para os metadados: o caso de uso normaliza uma única vez na
borda e passa exatamente o mesmo nome ao armazenamento e ao repositório.

A #22 expõe essa fundação em `/clients/{client_id}/documents`: anexo por
multipart, listagem paginada por cursor `(stored_at, id)`, consulta de metadados
e exportação de cópia. Título, categoria e observação são anotações livres e
opcionais — não existe tipo documental obrigatório. Um documento só é alcançável
pela pasta a que pertence, e o acesso por outra pasta responde como inexistente
para não revelar anexos de outro cliente. A cópia sai sempre como `attachment`,
com `X-Content-Type-Options: nosniff`, e as ações `document.stored`,
`document.viewed` e `document.exported` entram na trilha de auditoria. O
`stored_at` é definido pela aplicação, como na auditoria: o `CURRENT_TIMESTAMP`
do SQLite tem resolução de segundo e desalinharia o cursor.

A fatia de API da #23 acrescenta acompanhamento opcional aos metadados do
documento. Todo anexo começa como `pending` e pode mudar para
`received_regular` ou `incorrect_incomplete`; nenhum estado cria catálogo
obrigatório, vencimento ou bloqueio sobre cliente e outros anexos. A listagem
aceita filtro por estado, e a alteração usa a mesma transação do evento
`document.status_updated`, cujo contexto fechado registra apenas os estados
anterior e novo. A interface desse fluxo será entregue depois da definição de
design.

Na interface, os documentos abrem a partir da pasta do cliente, em
`apps/web/src/documents/`. A tela traduz a falha do servidor em uma frase por
causa — formato recusado, nome inválido, disco sem espaço, acesso negado e falha
de armazenamento —, porque a mensagem técnica da API não orienta o proprietário.
A cópia é baixada pela rota autenticada de conteúdo: a chave interna do arquivo
não aparece no contrato HTTP nem na interface.

## Ficha cadastral em PDF

A ficha da #34 é gerada localmente, sob demanda, a partir dos campos que
existirem na pasta flexível: o caso de uso projeta a pasta em
`domain/clients/reporting.py` (nome de identificação e apenas os campos
preenchidos) e delega a uma porta de renderização. O adaptador em
`infrastructure/reporting/` monta o PDF à mão, com as fontes padrão do formato
(Helvetica) e `WinAnsiEncoding` para os acentos do português, **sem embutir
fontes nem acrescentar dependências** — coerente com a operação local e com o
`uv.lock` estável. A ficha não é persistida: cada exportação é auditada e a
resposta entrega os bytes com `Content-Disposition: attachment`. A ausência de
qualquer campo nunca impede a geração.

## Importação do acervo legado

A importação da #45 é entregue em fatias. A primeira é a **prévia** em
`domain/imports/`, `application/imports/` e `infrastructure/imports/`: um ensaio
**somente leitura** que varre a pasta de origem — convenção confirmada de uma
pasta por cliente, cujo nome é o nome do cliente — e classifica cada arquivo pelo
conteúdo real, reutilizando o mesmo reconhecimento da gravação de documentos. A
associação casa o nome da pasta com um cliente já cadastrado (`find_by_display_name`);
o que não casa de forma única fica de fora, para o proprietário revisar antes de
confirmar. A varredura não segue symlinks, tem teto de arquivos e nunca escreve
na origem.

A segunda fatia é a **execução** (`ImportLegacyArchiveUseCase`): cada arquivo
elegível é copiado por streaming para a área privada reutilizando o mesmo
armazenamento, metadados e auditoria (`document.stored`) da gravação normal —
importar um arquivo legado é gravar um documento, então não há ação nem migração
novas. O conteúdo já anexado ao cliente é deduplicado por checksum e descartado
sem criar metadados; falta de espaço, formato inválido ou erro de leitura são
registrados por arquivo sem interromper os demais, e a origem permanece intacta.
O web (seleção de pasta, revisão da prévia e confirmação) vem na fatia seguinte.

## Auditoria

A trilha de auditoria é append-only na aplicação. Casos de uso registram ações
de negócio explicitamente; a dependência de autenticação centraliza apenas as
tentativas negadas por sessão ausente ou inválida. Não existe endpoint de
criação, edição ou exclusão manual de eventos.

Uma mutação relevante e seu evento usam a mesma sessão e o mesmo commit. Se o
evento não puder ser persistido, a mutação é revertida. Falhas técnicas que já
forçaram rollback não são gravadas nesta fundação; uma futura exigência desse
tipo deverá usar uma transação independente ou outbox sem comprometer a
atomicidade do fluxo principal.

O contexto é limitado a rota parametrizada pelo servidor, método HTTP e códigos
de motivo fechados. E-mail submetido, nome, senha, token, hash de token,
cabeçalho `Authorization`, corpo da requisição, IP e user-agent não pertencem ao
log. Cada issue futura de clientes, documentos, importação, PDF, e-mail e backup
deve acrescentar os próprios eventos no caso de uso correspondente.

Ações e tipos de recurso pertencem a catálogos fechados; identificadores de
recurso são UUIDs internos, nunca CPF, e-mail ou outro dado do cliente. O ator
autenticado referencia a conta preservada no banco, que não pode ser removida
enquanto houver histórico. A consulta usa cursor por `(occurred_at, id)`, não
offset, para que o próprio evento de visualização ou novos registros não
desloquem páginas já percorridas.

No SQLite, habilitar e testar `PRAGMA foreign_keys=ON` em toda conexão é
obrigatório antes de considerar uma FK efetiva. A transição também deve definir e
testar journal, timeout de lock, `synchronous=FULL`, timestamps UTC e a
integridade após reabrir o arquivo; compilar DDL isoladamente não prova essas
garantias.

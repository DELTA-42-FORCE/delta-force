# Plano de entrega do MVP local Windows

Este plano organiza o trabalho por dependência, não por quem o executará. Cada
PR continua curto, nasce de `develop`, referencia uma issue e volta para
`develop` após revisão.

## Marco 0 — fechar a base de decisão

1. **#54 — persistência SQLite:** a ADR 0003 definiu SQLite em arquivo e filesystem
   privado para desenvolvimento e entrega. A issue deve portar o
   adaptador, migrations, autenticação e auditoria antes de novas entidades.
2. **#43 — arquitetura de entrega local Windows:** decidir somente o shell,
   instalador, diretórios privados finais, primeira execução e atualização. A
   escolha de persistência já não está pendente nessa issue.
3. **#14 — pasta digital flexível:** formalizar que nome é o único dado exigido
   para criar cliente; demais dados e documentos são opcionais. O limite de
   tamanho de PDF/JPEG permanece pendente.
4. **#46 — remetente:** aguardar a conta/provedor informado pelo cliente e
   documentar sua configuração segura.

## Marco 1 — aplicação local segura

1. **#15 concluída:** primeira conta do proprietário, login, sessão segura e
   logout. A transição SQLite deve provar esses fluxos no arquivo local.
2. **#17 concluída:** auditoria append-only das ações e tentativas negadas. A
   transição SQLite deve provar sua integridade no arquivo local.
3. Executar **#44** após a persistência SQLite: backup protegido em HD externo, restauração
   testada e proteção contra alvo errado, arquivo corrompido e falta de espaço.

## Marco 2 — clientes e documentos

1. **#18 e #19:** modelo, API e telas da pasta digital flexível: nome obrigatório
   para criação, demais dados opcionais. A issue #20 sai do MVP.
2. **#21 e #22:** armazenamento privado local, anexo/consulta/download de PDF e
   JPEG, validação de conteúdo/tamanho, autorização e auditoria.
3. **#23:** checklist e status documental, sem vencimento operacional.
4. **#45:** importação assistida do acervo legado, com prévia, confirmação e
   relatório de itens importados, ignorados ou corrompidos.
5. **#34:** gerar a ficha cadastral em PDF a partir dos dados disponíveis.

## Marco 3 — comunicação e aceite

1. **#24:** modelos de e-mail e seleção de destinatários por pendência.
2. **#25:** envio, histórico e tratamento de falhas usando o remetente definido
   em #46; Mailpit é exclusivamente local de desenvolvimento.
3. **#26:** consolidar operação local, LGPD, retenção, procedimento de incidente
   e manual de backup/restauração.
4. **#27:** executar o aceite de ponta a ponta em instalação Windows limpa,
   incluindo primeiro acesso, cliente, documento, ficha PDF, e-mail, backup e
   restauração.

## Fora do MVP

Gestão de múltiplos usuários/papéis (#16), portal do cliente, financeiro,
PagBank, emissão fiscal e IA permanecem fora do escopo. Não devem aparecer em
PRs deste plano sem repriorização explícita.

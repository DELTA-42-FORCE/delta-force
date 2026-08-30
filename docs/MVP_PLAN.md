# Plano de entrega do MVP local Windows

Este plano organiza o trabalho por dependência, não por quem o executará. Cada
PR continua curto, nasce de `develop`, referencia uma issue e volta para
`develop` após revisão.

## Marco 0 — fechar a base de decisão

1. **#54 — concluída:** a ADR 0003 definiu SQLite em arquivo e filesystem
   privado para desenvolvimento e entrega. A issue portou adaptador, migrations,
   autenticação, auditoria e os checks de integração antes de novas entidades.
2. **#43 — arquitetura de entrega local Windows:** a ADR 0002 aceita definiu
   shell Tauri 2, FastAPI empacotada com PyInstaller `onedir`, diretórios
   privados, primeira execução e atualização manual. A escolha de persistência
   já não está pendente nessa issue.
3. **#14 — pasta digital flexível:** formalizar que nome é o único dado exigido
   para criar cliente; demais dados e documentos são opcionais. O limite de
   tamanho de PDF/JPEG permanece pendente.
4. **#46 — remetente:** aguardar a conta/provedor informado pelo cliente e
   documentar sua configuração segura.

### Próximos passos da entrega Windows

A ADR 0002 já é a decisão de produção. Sua implementação deve seguir esta
ordem:

1. abrir uma issue pequena de integração desktop baseada em `develop`, sem
   reutilizar a PR #49, para shell/sidecar, bootstrap/capability por IPC e
   lifecycle do processo, validando no runtime local a autenticação (#15) e a
   auditoria (#17) já integradas;
2. decidir na #44 a proteção e a recuperação do backup em HD externo;
3. validar instalação, atualização manual, desinstalação e restauração na #27.

Versão/edição do Windows, proteção do disco, assinatura/custódia e recuperação do
backup permanecem pendentes. O plano não antecipa essas escolhas como aprovadas.

## Marco 1 — aplicação local segura

1. **#15 — concluída:** primeira conta do proprietário, login, sessão segura e
   logout estão integrados. A transição SQLite (#54) e a futura issue desktop
   devem validar esse fluxo no arquivo local sem alterar sua regra de negócio.
2. **#17 — concluída:** a auditoria append-only e sua consulta autenticada estão
   integradas. A transição SQLite (#54) e a futura issue desktop devem provar
   esses eventos no arquivo local, inclusive negações do bootstrap/capability.
3. Executar **#44** após a persistência SQLite e #43: backup protegido conforme
   a decisão da própria issue, restauração testada por HD externo e proteção
   contra alvo errado, arquivo corrompido e falta de espaço.

## Marco 2 — clientes e documentos

1. **#18 e #19:** modelo, API e telas da pasta digital flexível: nome
   obrigatório para criação, demais dados opcionais. A issue #20 sai do MVP.
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

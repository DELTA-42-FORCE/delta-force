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
   para criar cliente; demais dados e documentos são opcionais. Não há limite
   comercial fixo de PDF/JPEG: o aplicativo usa a capacidade livre do disco e
   escrita em streaming com falha segura.
4. **#46 — remetente:** aguardar a conta/provedor informado pelo cliente e
   documentar sua configuração segura.

### Próximos passos da entrega Windows

A ADR 0002 já é a decisão de produção. A integração essencial foi entregue pela
#57; os próximos passos específicos da entrega Windows são:

1. revisar a correção empilhada #105, integrá-la à #103 e revalidar o envio;
   depois rebasear e revisar a implementação de backup da #99;
2. validar instalação, atualização manual, desinstalação e restauração na #27.

Versão/edição do Windows, assinatura/custódia e o aceite em HD externo real
permanecem gates operacionais. O formato e a recuperação do backup já não são
decisões pendentes.

## Marco 1 — aplicação local segura

1. **#15 — concluída:** primeira conta do proprietário, login, sessão segura e
   logout estão integrados. A transição SQLite (#54) e a futura issue desktop
   devem validar esse fluxo no arquivo local sem alterar sua regra de negócio.
2. **#17 — concluída:** a auditoria append-only e sua consulta autenticada estão
   integradas. A transição SQLite (#54) e a futura issue desktop devem provar
   esses eventos no arquivo local, inclusive negações do bootstrap/capability.
3. **#44 — em revisão:** backup AES-256-GCM versionado, senha efêmera,
   validação de mídia externa, snapshot consistente e restauração por geração
   única foram implementados. A instalação vazia usa o mesmo protocolo; substituir
   dados existentes exige autenticação e confirmação reforçada. O aceite final
   ainda deve exercitar um HD externo real e uma instalação Windows limpa.

## Marco 2 — clientes e documentos

1. **#18 e #19:** modelo, API e telas da pasta digital flexível: nome
   obrigatório para criação, demais dados opcionais. A issue #20 sai do MVP.
2. **#21 e #22:** armazenamento privado local, anexo/consulta/download de PDF e
   JPEG, validação de formato/conteúdo/nome, capacidade disponível em disco,
   autorização e auditoria. Não há teto comercial fixo por arquivo; a gravação
   é em streaming e deve falhar sem conteúdo parcial quando faltar espaço.
3. **#23:** checklist e status documental, sem vencimento operacional.
4. **#45:** importação assistida do acervo legado, com prévia, confirmação e
   relatório de itens importados, ignorados ou corrompidos.
5. **#34:** gerar a ficha cadastral em PDF a partir dos dados disponíveis.

## Marco 3 — comunicação e aceite

1. **#24 — concluída:** modelos, candidatos, e-mail opcional do cliente, prévia
   e variável {{nome}} estão integrados.
2. **#25 — correções solicitadas na #103:** envio/histórico, credencial efêmera,
   classificação SMTP, vínculo de repetição e auditoria de lote estão na PR
   empilhada. A #105 corrige a reserva transacional e a conciliação de
   tentativas interrompidas; ambas exigem revisão e checks no head integrado.
   Mailpit é somente desenvolvimento.
3. **#26 — rascunho bloqueado na #100:** manual de operação/LGPD e checklist
   Windows estão escritos para revisão técnica, mas não estão homologados;
   dependem das bases finais, da validação operacional e do aceite físico.
4. **#27:** executar o aceite de ponta a ponta em instalação Windows limpa,
   incluindo primeiro acesso, cliente, documento, ficha PDF, e-mail, backup e
   restauração.

## Fora do MVP

Gestão de múltiplos usuários/papéis (#16), portal do cliente, financeiro,
PagBank, emissão fiscal e IA permanecem fora do escopo. Não devem aparecer em
PRs deste plano sem repriorização explícita.

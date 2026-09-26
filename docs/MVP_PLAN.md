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
#57. A ADR 0004 também foi aceita e definiu o formato seguro; o trabalho de
backup/restauração agora segue em entregas pequenas, diretamente para `develop`:

1. **#106 — codec criptográfico DFCRMBK1 v1**;
2. em paralelo após #106, **#108 — snapshot consistente** e **#110 — validação
   da restauração em staging isolado**;
3. após #108, **#109 — publicação segura em mídia externa Windows**; após #110,
   **#111 — ativação recuperável com journal e rollback**;
4. após #109 e #111, **#112 — rotas e fluxo autenticado no aplicativo Windows**;
5. completar **#26** (operação, manual e incidente) e executar o aceite em
   instalação Windows limpa e HD de teste pela **#27**.

Custódia da senha, frequência/retenção do HD, proteção do equipamento e
recuperação da conta continuam pendentes para calibrar o manual e o aceite em
#26/#27; não bloqueiam o codec. O primeiro aceite deve usar dados sintéticos e
HD de teste, nunca a única cópia de dados do cliente.

## Marco 1 — aplicação local segura

1. **#15 — concluída:** primeira conta do proprietário, login, sessão segura e
   logout estão integrados. A transição SQLite (#54) e a futura issue desktop
   devem validar esse fluxo no arquivo local sem alterar sua regra de negócio.
2. **#17 — concluída:** a auditoria append-only e sua consulta autenticada estão
   integradas. A transição SQLite (#54) e a futura issue desktop devem provar
   esses eventos no arquivo local, inclusive negações do bootstrap/capability.
3. Backup e restauração estão decompostos nas issues **#106 e #108–#112**,
   conforme a sequência da seção de entrega Windows. A #44 só termina após
   essas entregas e os gates operacionais/finais da #26 e #27.

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

1. **#24 — concluída pela PR #97:** cadastro do e-mail opcional, modelos,
   renderização e seleção de candidatos por pendência. Isso não exige nem
   habilita envio real sem a configuração autorizada da #46.
2. **#25:** a fundação de envio individual, histórico e tratamento de falhas foi
   integrada pela PR #103. A configuração e o teste com o remetente real ainda
   dependem dos dados do cliente na #46; Mailpit é exclusivamente local de
   desenvolvimento.
3. **#26:** consolidar operação local, LGPD, retenção, procedimento de incidente
   e manual de backup/restauração.
4. **#27:** executar o aceite de ponta a ponta em instalação Windows limpa,
   incluindo primeiro acesso, cliente, documento, ficha PDF, e-mail, backup e
   restauração.

## Fora do MVP

Gestão de múltiplos usuários/papéis (#16), portal do cliente, financeiro,
PagBank, emissão fiscal e IA permanecem fora do escopo. Não devem aparecer em
PRs deste plano sem repriorização explícita.

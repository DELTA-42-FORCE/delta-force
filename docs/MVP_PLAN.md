# Plano de entrega do MVP local Windows

Este plano organiza o trabalho por dependência, não por quem o executará. Cada
PR continua curto, nasce de `develop`, referencia uma issue e volta para
`develop` após revisão.

## Marco 0 — fechar a base de decisão

1. **#43 — arquitetura de entrega local Windows:** ADR para instalador,
   persistência, diretórios privados, primeira execução e atualização. Nenhuma
   troca de PostgreSQL/MinIO ou inclusão de framework desktop no produto deve
   ocorrer antes dessa ADR. A proposta está na ADR 0002 e ainda depende das
   confirmações e aprovações registradas nela.
2. **#14 — catálogo cadastral/documental:** transformar a referência ao `gov.br`
   em dicionário de dados versionado; formalizar tipos de documentos, campos
   condicionais e o limite de tamanho de PDF/JPEG.
3. **#46 — remetente:** aguardar a conta/provedor informado pelo cliente e
   documentar sua configuração segura.

### Plano de instalação Windows da #43

Este plano só se torna decisão de produção quando a ADR 0002 mudar para
**Aceita**. Até lá, serve para revisão e para um spike isolado, não distribuível
e sem dados reais.

1. **Decidir e provar:** confirmar Windows/criptografia do computador,
   responsabilidade pela assinatura e contratos de backup; ainda com a ADR como
   **Proposta**, autorizar e executar o spike estreito de runtime no notebook de
   referência; revisar suas evidências e somente então aceitar a ADR. Instalação
   e aceite em VM limpa ficam para #27.
2. **Empacotar em issue própria:** antes de encerrar a #43, criar e vincular uma
   issue de implementação desktop/SQLite. Ela implementará shell Tauri, árvore
   FastAPI/PyInstaller `onedir`, adapter local, launcher e empacotamento
   NSIS/WebView2, sem Docker, Python, serviço ou UAC no runtime. O build assinado
   e o aceite em VM limpa pertencem à #27.
3. **Instalar sem dados:** gravar binários em diretórios versionados e imutáveis,
   criar diretórios privados separados e validar Windows, espaço, DACL protegida
   e criptografia em todos os volumes de dados antes de abrir dados reais.
4. **Primeiro uso:** iniciar a API somente em loopback com capability por
   execução, aplicar migrations, concluir health check e permitir uma única
   criação autenticada do proprietário.
5. **Atualizar com rollback:** instalar versão e geração candidatas inativas,
   migrar/testar sem mutações e só então confirmar o par em registro durável.
   Antes da primeira mutação, falha pode voltar ao par anterior; depois dela,
   rollback automático que perderia dados é proibido.
6. **Desinstalar sem perda:** remover apenas binários e atalhos, preservar
   gerações, blobs e recuperação e comprovar reinstalação no aceite da #27.

A #44 implementa o backup criptografado no HD; a #27 comprova assinatura,
instalação, atualização, desinstalação, backup e restauração ponta a ponta. A
#43 termina na decisão/documentação aprovada, não na antecipação dessas features.

## Marco 1 — aplicação local segura

1. Corrigir e concluir **#15**: primeira conta do proprietário, login do
   aplicativo, sessão segura e logout. Tokens de sessão são secretos: apenas o
   hash pode ser persistido e a interface futura não pode usar `localStorage`.
2. Adaptar **#17** para auditoria das ações do proprietário e das tentativas de
   acesso, sem antecipar uma matriz de múltiplos papéis.
3. Executar **#44** após #43: backup criptografado em HD externo, restauração
   testada e proteção contra alvo errado, arquivo corrompido e falta de espaço.

## Marco 2 — clientes e documentos

1. **#18, #19 e #20:** modelo, API e telas de cadastro/busca/edição conforme o
   catálogo homologado, incluindo a regra de reservista quando aplicável.
2. **#21 e #22:** armazenamento privado local, anexo/consulta/download de PDF e
   JPEG, validação de conteúdo/tamanho, autorização e auditoria.
3. **#23:** checklist e status documental, sem vencimento operacional.
4. **#45:** importação assistida do acervo legado, com prévia, confirmação e
   relatório de itens importados, ignorados ou corrompidos.
5. **#34:** gerar a ficha cadastral em PDF a partir dos dados homologados.

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

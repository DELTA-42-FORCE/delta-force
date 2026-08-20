# Plano de entrega do MVP local Windows

Este plano organiza o trabalho por dependência, não por quem o executará. Cada
PR continua curto, nasce de `develop`, referencia uma issue e volta para
`develop` após revisão.

## Marco 0 — fechar a base de decisão

1. **#43 — arquitetura de entrega local Windows:** ADR para instalador,
   persistência, diretórios privados, primeira execução e atualização. Nenhuma
   troca de PostgreSQL/MinIO ou inclusão de framework desktop deve ocorrer antes
   dessa ADR.
2. **#14 — catálogo cadastral/documental:** transformar a referência ao `gov.br`
   em dicionário de dados versionado; formalizar tipos de documentos, campos
   condicionais e o limite de tamanho de PDF/JPEG.
3. **#46 — remetente:** aguardar a conta/provedor informado pelo cliente e
   documentar sua configuração segura.

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

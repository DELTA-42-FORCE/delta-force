# Backup e restauração no aplicativo Windows — #112

O fluxo usa os serviços de #106/#108–#111 sem alterar DFCRMBK1 nem o protocolo
de ativação. Exige sessão do proprietário e capability do sidecar. Não está
habilitado na API HTTP de desenvolvimento sem runtime desktop.

## Operação

1. Abra **Backup e restauração** e selecione uma pasta pelo diálogo nativo.
   O servidor valida que é mídia externa USB, diferente do volume dos dados,
   e estima espaço no HD e espaço temporário local com margem conservadora.
2. Informe e repita a senha do backup: 12–1024 bytes UTF-8 após NFC. Ela não é
   salva pelo CRM. Mantenha o HD conectado durante preparação, criptografia,
   gravação e verificação; o progresso é indeterminado, sem percentual fictício.
3. Para restaurar, selecione um `.dfcrmbak` local e informe sua senha. A prévia
   valida conteúdo, documentos e banco; migra apenas a candidata temporária e
   mostra contagens atuais e da cópia. O plaintext temporário é descartado.
4. Leia a consequência, informe a senha de acesso do proprietário atual,
   digite **RESTAURAR** e informe novamente a senha do backup. A prévia vale por
   dez minutos, pertence à conta que a solicitou e é consumida na tentativa.
   Mudanças nos dados ou no arquivo exigem nova revisão.
5. A troca encerra as conexões e remove as sessões presentes na candidata.
   Após sucesso, entre com a conta presente **no backup**. Se a ativação for
   interrompida, o servidor bloqueia as próximas operações e solicita reinício;
   o bootstrap recupera o journal conforme #111.

Não há cópia agendada automática: o proprietário pode configurar um lembrete
de 1–365 dias ou deixá-lo desativado (padrão). O intervalo e a última cópia
concluída ficam em `backup-reminder.json` na área privada desta instalação,
fora da geração restaurada. O lembrete é conferido no acesso e exibido na tela;
o aplicativo não escolhe frequência comercial nem política de retenção.
Se gravar/consultar o lembrete falhar depois de publicar a cópia, a interface
preserva o resultado de sucesso e avisa sobre o lembrete separadamente.

## Contrato HTTP

Todas as rotas abaixo exigem autenticação; no pacote Windows, também capability,
Host e Origin válidos. Não retornam senha nem caminho do arquivo publicado.

| Rota | Entrada | Resultado |
|---|---|---|
| `GET /backups/status` | — | `interval_days`, `last_backup_at`, `reminder_due`, `recovery_required` |
| `PUT /backups/reminder` | `interval_days`: inteiro 1–365 ou `null` | status atualizado |
| `POST /backups/estimate` | `destination`: seleção absoluta nativa | `required_bytes`, `available_bytes`, `local_required_bytes`, `local_available_bytes` |
| `POST /backups` | `destination`, `passphrase` | `completed`, `reminder_updated` |
| `POST /backups/restore/preview` | `source`, `passphrase` | `preview_token`, `current_records`, `candidate_records`, `replacement_required`, `expires_in_seconds` |
| `POST /backups/restore` | `preview_token`, `passphrase`, `owner_password`, `confirmation` | `completed`, `login_required` |

O token da prévia vive apenas em memória; associa proprietário, geração ativa,
digest do arquivo e prazo. A API não aceita tokens após mutação ou expiração.
Requisições desktop são serializadas durante essas operações, inclusive streams
e limpeza das dependências. Fechar o WebView/cancelar a requisição não libera a
exclusão antes de o worker terminar.

Erros são códigos seguros: `backup_invalid_input`/`backup_operation_failed`
(422), `backup_insufficient_space` (422, staging), `backup_preview_expired`
(409), `backup_confirmation_required` (403), `backup_requires_desktop` (404) e
`backup_restart_required` (503). Validação não ecoa o corpo recebido.

## Auditoria e compatibilidade

A migration `20260930_0017` amplia o catálogo append-only para `backup.created`,
`backup.restore_reviewed`, `backup.restore_authorized`, `backup.restore_applied`
e `backup.reminder_updated`, com recurso `backup`. Contexto não contém senha,
token, caminho pessoal nem nome de arquivo. A autorização fica na geração
anterior; a geração restaurada recebe evento de ativação pelo sistema, sem
atribuir a conta antiga a uma conta eventualmente diferente da cópia.

O downgrade recusa apagar auditoria de backup existente. Instalações antigas
continuam seguindo o gate de atualização manual da ADR 0002: backup verificado
antes de atualizar o banco; a nova tela não migra o banco ativo silenciosamente.

## Verificação e gates operacionais

- Testes temporários de API/SQLite exercitam criação real cifrada (volume
  simulado), prévia, reautenticação, dados substituídos, sessões revogadas,
  expiração/alteração da cópia, interrupção, lembrete e downgrade protegido.
- Testes React cobrem seleção cancelada, campos secretos, confirmação,
  mensagens seguras e preservação do sucesso após falha de refresh.
- `just api-test-backup-windows` inclui o fluxo completo; build/instalador/smoke
  Windows permanecem gates obrigatórios de integração.
- O aceite com instalação Windows limpa e HD físico de teste pertence a #27.
  Custódia da senha, recuperação de conta, retenção e proteção do equipamento
  permanecem decisões para #26/#27; não usar a única cópia do acervo do cliente.

import { useEffect, useRef, useState } from 'react'

import type { AuthenticatedGet } from '../audit/auditApi'
import type { AuthenticatedRequest } from '../clients/clientsApi'
import { pickBackupFile, pickBackupFolder } from '../lib/desktopShell'
import { backupFailure, formatBytes, validBackupPassphrase } from './backupApi'
import type { BackupEstimate, BackupStatus, RestorePreview } from './backupApi'

interface Props {
  get: AuthenticatedGet
  request: AuthenticatedRequest
  available: boolean
  onBack: () => void
  onRestored: () => void
  onBackupCreated: () => void
  onReminderChange?: (due: boolean) => void
  onBusyChange: (busy: boolean) => void
  pickFolder?: () => Promise<string | null>
  pickFile?: () => Promise<string | null>
}

const RECORD_LABELS: Record<string, string> = {
  clients: 'Clientes',
  documents: 'Documentos',
  contracts: 'Contratos',
  installments: 'Parcelas',
  message_templates: 'Modelos de e-mail',
  email_dispatches: 'Disparos de e-mail',
  sender_settings: 'Configuração do remetente',
  users: 'Contas',
  sessions: 'Sessões',
  audit_events: 'Registros de auditoria',
  owner_slot: 'Proprietário',
  other_tables: 'Outros conjuntos de registros',
}

export function BackupPage({
  get,
  request,
  available,
  onBack,
  onRestored,
  onBackupCreated,
  onReminderChange,
  onBusyChange,
  pickFolder = pickBackupFolder,
  pickFile = pickBackupFile,
}: Props) {
  const [status, setStatus] = useState<BackupStatus | null>(null)
  const [interval, setInterval] = useState('')
  const [destination, setDestination] = useState('')
  const [estimate, setEstimate] = useState<BackupEstimate | null>(null)
  const [source, setSource] = useState('')
  const [preview, setPreview] = useState<RestorePreview | null>(null)
  const [backupPassword, setBackupPassword] = useState('')
  const [repeatPassword, setRepeatPassword] = useState('')
  const [restorePassword, setRestorePassword] = useState('')
  const [ownerPassword, setOwnerPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [phase, setPhase] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const running = useRef(false)
  const busy = phase !== null

  useEffect(() => {
    if (!available) return
    let active = true
    get<BackupStatus>('/backups/status')
      .then((value) => {
        if (active) {
          setStatus(value)
          onReminderChange?.(value.reminder_due)
          setInterval(value.interval_days?.toString() ?? '')
        }
      })
      .catch((failure: unknown) => {
        if (active) setError(backupFailure(failure))
      })
    return () => {
      active = false
    }
  }, [available, get, onReminderChange])

  async function run(label: string, operation: () => Promise<void>) {
    if (running.current) return
    running.current = true
    setError(null)
    setNotice(null)
    setPhase(label)
    onBusyChange(true)
    try {
      await operation()
    } catch (failure) {
      setError(backupFailure(failure))
    } finally {
      running.current = false
      setPhase(null)
      onBusyChange(false)
    }
  }

  async function selectDestination() {
    await run('Conferindo o HD e o espaço disponível…', async () => {
      const selected = await pickFolder()
      if (selected === null) return
      setDestination(selected)
      setEstimate(null)
      setEstimate(
        await request<BackupEstimate>('/backups/estimate', {
          method: 'POST',
          body: { destination: selected },
        }),
      )
    })
  }

  async function createBackup() {
    if (
      !validBackupPassphrase(backupPassword) ||
      backupPassword !== repeatPassword
    ) {
      setError(
        'Use uma senha de 12 a 1024 bytes e repita a mesma senha nos dois campos.',
      )
      return
    }
    await run('Preparando, protegendo e gravando a cópia no HD…', async () => {
      try {
        const result = await request<{
          completed: boolean
          reminder_updated: boolean
        }>('/backups', {
          method: 'POST',
          body: {
            destination,
            passphrase: backupPassword,
          },
        })
        setNotice(
          'Cópia criada e verificada no HD externo. Guarde a senha em um local separado.',
        )
        onBackupCreated()
        try {
          setStatus(await get<BackupStatus>('/backups/status'))
          if (!result.reminder_updated)
            setNotice(
              'Cópia criada e verificada no HD externo. O lembrete não foi atualizado; confira-o depois.',
            )
        } catch {
          setNotice(
            'Cópia criada e verificada no HD externo. Não foi possível atualizar o lembrete agora.',
          )
        }
      } finally {
        setBackupPassword('')
        setRepeatPassword('')
      }
    })
  }

  async function reviewRestore() {
    if (!validBackupPassphrase(restorePassword)) {
      setError('Informe a senha do backup, com 12 a 1024 bytes.')
      return
    }
    await run('Validando o backup e preparando a revisão…', async () => {
      setPreview(null)
      try {
        setPreview(
          await request<RestorePreview>('/backups/restore/preview', {
            method: 'POST',
            body: { source, passphrase: restorePassword },
          }),
        )
      } finally {
        setRestorePassword('')
        setOwnerPassword('')
        setConfirmation('')
      }
    })
  }

  async function restore() {
    if (preview === null) return
    if (
      confirmation !== 'RESTAURAR' ||
      !ownerPassword ||
      !validBackupPassphrase(restorePassword)
    ) {
      setError(
        'Informe as duas senhas e digite RESTAURAR para confirmar a substituição.',
      )
      return
    }
    await run('Conferindo a autorização e restaurando os dados…', async () => {
      try {
        await request('/backups/restore', {
          method: 'POST',
          body: {
            preview_token: preview.preview_token,
            passphrase: restorePassword,
            owner_password: ownerPassword,
            confirmation,
          },
        })
        onRestored()
      } catch (failure) {
        setPreview(null)
        throw failure
      } finally {
        setRestorePassword('')
        setOwnerPassword('')
        setConfirmation('')
      }
    })
  }

  const insufficient =
    estimate !== null &&
    (estimate.required_bytes > estimate.available_bytes ||
      estimate.local_required_bytes > estimate.local_available_bytes)

  return (
    <section
      className="backup-page"
      aria-labelledby="backup-title"
      aria-busy={busy}
    >
      <header className="backup-heading">
        <div>
          <p className="eyebrow">Proteção do acervo</p>
          <h1 id="backup-title">Backup e restauração</h1>
          <p>
            Uma cópia protegida de clientes, documentos e histórico no seu HD
            externo.
          </p>
        </div>
        <button className="secondary-button" onClick={onBack} disabled={busy}>
          Voltar
        </button>
      </header>
      {!available ? (
        <p role="status">Este fluxo está disponível no aplicativo Windows.</p>
      ) : (
        <>
          {error && (
            <p className="backup-error" role="alert">
              {error}
            </p>
          )}
          {notice && (
            <p className="backup-notice" role="status">
              {notice}
            </p>
          )}
          {phase && (
            <div className="backup-progress" role="status">
              <progress aria-label={phase} />
              <span>
                {phase} Mantenha o HD conectado e o aplicativo aberto.
              </span>
            </div>
          )}
          <section
            className="backup-create"
            aria-labelledby="backup-create-title"
          >
            <p className="eyebrow">Criar uma cópia</p>
            <h2 id="backup-create-title">Proteja os dados deste computador</h2>
            <p>
              Escolha uma pasta no HD externo. A cópia será criptografada e os
              arquivos anteriores serão preservados.
            </p>
            <label className="backup-selection">
              Pasta no HD externo
              <input
                readOnly
                value={destination}
                placeholder="Nenhuma pasta selecionada"
              />
            </label>
            <button
              className="secondary-button"
              disabled={busy}
              onClick={() => void selectDestination()}
            >
              Selecionar HD externo
            </button>
            {estimate && (
              <dl className="backup-space">
                <div>
                  <dt>Estimativa da cópia</dt>
                  <dd>{formatBytes(estimate.required_bytes)}</dd>
                </div>
                <div>
                  <dt>Disponível no HD</dt>
                  <dd>{formatBytes(estimate.available_bytes)}</dd>
                </div>
                <div>
                  <dt>Espaço temporário no computador</dt>
                  <dd>
                    {formatBytes(estimate.local_required_bytes)} /{' '}
                    {formatBytes(estimate.local_available_bytes)} livres
                  </dd>
                </div>
              </dl>
            )}
            {insufficient && (
              <p role="alert">
                O HD ou o computador não tem espaço suficiente. Libere espaço e
                selecione o HD novamente.
              </p>
            )}
            <form
              noValidate
              onSubmit={(event) => {
                event.preventDefault()
                void createBackup()
              }}
            >
              <fieldset disabled={busy || estimate === null || insufficient}>
                <div className="backup-fields">
                  <label>
                    Senha para proteger o backup
                    <input
                      type="password"
                      autoComplete="new-password"
                      value={backupPassword}
                      onChange={(event) =>
                        setBackupPassword(event.target.value)
                      }
                    />
                  </label>
                  <label>
                    Repita a senha do backup
                    <input
                      type="password"
                      autoComplete="new-password"
                      value={repeatPassword}
                      onChange={(event) =>
                        setRepeatPassword(event.target.value)
                      }
                    />
                  </label>
                </div>
                <p className="backup-help">
                  A senha não é salva pelo CRM. Sem ela, não será possível
                  restaurar a cópia.
                </p>
                <button className="primary-button" type="submit">
                  Criar backup no HD
                </button>
              </fieldset>
            </form>
          </section>
          <section className="backup-reminder" aria-labelledby="reminder-title">
            <div>
              <h2 id="reminder-title">Lembrete de backup</h2>
              <p>
                {status?.last_backup_at
                  ? `Última cópia: ${new Date(status.last_backup_at).toLocaleString('pt-BR')}`
                  : 'Nenhuma cópia criada por este aplicativo ainda.'}
              </p>
              {status?.reminder_due && (
                <p role="status">Está na hora de criar uma nova cópia.</p>
              )}
            </div>
            <form
              noValidate
              onSubmit={(event) => {
                event.preventDefault()
                const days = interval === '' ? null : Number(interval)
                if (
                  days !== null &&
                  (!Number.isInteger(days) || days < 1 || days > 365)
                ) {
                  setError(
                    'Escolha um intervalo de 1 a 365 dias, ou deixe vazio para desativar.',
                  )
                  return
                }
                void run('Salvando o lembrete…', async () => {
                  const updated = await request<BackupStatus>(
                    '/backups/reminder',
                    {
                      method: 'PUT',
                      body: { interval_days: days },
                    },
                  )
                  setStatus(updated)
                  onReminderChange?.(updated.reminder_due)
                  setNotice('Lembrete atualizado.')
                })
              }}
            >
              <label>
                Intervalo em dias
                <input
                  type="number"
                  min="1"
                  max="365"
                  value={interval}
                  disabled={busy || status === null}
                  onChange={(event) => setInterval(event.target.value)}
                  aria-describedby="reminder-help"
                />
              </label>
              <small id="reminder-help">
                Deixe vazio para desativar. A cópia é feita por você ao conectar
                o HD.
              </small>
              <button
                className="secondary-button"
                disabled={busy || status === null}
              >
                Salvar lembrete
              </button>
            </form>
          </section>
          <section className="backup-restore" aria-labelledby="restore-title">
            <p className="eyebrow">Recuperar uma cópia</p>
            <h2 id="restore-title">Restaurar dados do backup</h2>
            <p>
              A restauração substitui os dados deste computador. Crie uma cópia
              atual antes de continuar.
            </p>
            <label className="backup-selection">
              Arquivo de backup
              <input
                readOnly
                value={source}
                placeholder="Nenhum arquivo selecionado"
              />
            </label>
            <button
              className="secondary-button"
              disabled={busy}
              onClick={() =>
                void run('Selecionando o backup…', async () => {
                  const selected = await pickFile()
                  if (selected !== null) {
                    setSource(selected)
                    setPreview(null)
                    setRestorePassword('')
                    setOwnerPassword('')
                    setConfirmation('')
                  }
                })
              }
            >
              Selecionar backup
            </button>
            <form
              noValidate
              onSubmit={(event) => {
                event.preventDefault()
                void (preview === null ? reviewRestore() : restore())
              }}
            >
              <fieldset disabled={busy || source === ''}>
                {preview !== null && (
                  <div className="backup-review">
                    <h3>Confira o que será substituído</h3>
                    <table>
                      <caption>
                        Comparação dos registros antes da restauração
                      </caption>
                      <thead>
                        <tr>
                          <th>Registros</th>
                          <th>Atuais</th>
                          <th>No backup</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.keys(RECORD_LABELS)
                          .filter(
                            (key) =>
                              key in preview.current_records ||
                              key in preview.candidate_records,
                          )
                          .map((key) => (
                            <tr key={key}>
                              <th scope="row">{RECORD_LABELS[key]}</th>
                              <td>{preview.current_records[key] ?? 0}</td>
                              <td>{preview.candidate_records[key] ?? 0}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                    <p>
                      A revisão vale por 10 minutos e é cancelada quando os
                      dados mudam. Após restaurar, entre com a conta presente no
                      backup; todas as sessões serão encerradas.
                    </p>
                    <label>
                      Senha de acesso ao CRM
                      <input
                        type="password"
                        autoComplete="current-password"
                        value={ownerPassword}
                        onChange={(event) =>
                          setOwnerPassword(event.target.value)
                        }
                      />
                    </label>
                    <label>
                      Digite RESTAURAR para substituir os dados
                      <input
                        value={confirmation}
                        autoComplete="off"
                        onChange={(event) =>
                          setConfirmation(event.target.value)
                        }
                      />
                    </label>
                  </div>
                )}
                <label>
                  {preview === null
                    ? 'Senha do backup selecionado'
                    : 'Digite novamente a senha do backup'}
                  <input
                    type="password"
                    autoComplete="off"
                    value={restorePassword}
                    onChange={(event) => setRestorePassword(event.target.value)}
                  />
                </label>
                <button
                  className={
                    preview === null
                      ? 'secondary-button'
                      : 'backup-danger-button'
                  }
                  type="submit"
                >
                  {preview === null
                    ? 'Validar e revisar backup'
                    : 'Confirmar restauração'}
                </button>
              </fieldset>
            </form>
          </section>
        </>
      )}
    </section>
  )
}

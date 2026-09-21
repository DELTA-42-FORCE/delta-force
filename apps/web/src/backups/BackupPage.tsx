import { useCallback, useEffect, useState, type FormEvent } from 'react'

import { ApiError } from '../lib/apiClient'
import type { BackupCreationResult, BackupStatus } from './backupsApi'
import type { RestoreStagingResult, StageRestoreInput } from './backupsApi'
import { RestoreBackupPanel } from './RestoreBackupPanel'

interface BackupPageProps {
  loadStatus: () => Promise<BackupStatus>
  createBackup: (input: {
    destination_directory: string
    passphrase: string
  }) => Promise<BackupCreationResult>
  pickFolder?: () => Promise<string | null>
  pickFile?: () => Promise<string | null>
  stageRestore: (input: StageRestoreInput) => Promise<RestoreStagingResult>
  onBack: () => void
}

function describeFailure(error: unknown): string {
  if (error instanceof ApiError && error.status === 507) {
    return 'O HD ou o computador não tem espaço livre suficiente.'
  }
  if (error instanceof ApiError && error.status === 422) {
    return 'O destino não é um HD externo aceito ou a senha não atende aos requisitos.'
  }
  if (error instanceof ApiError && error.status === 409) {
    return 'Os dados locais não puderam ser copiados com consistência. Verifique os documentos e tente novamente.'
  }
  return 'Não foi possível criar o backup. Nenhum arquivo incompleto foi publicado.'
}

export function BackupPage({
  loadStatus,
  createBackup,
  pickFolder,
  pickFile,
  stageRestore,
  onBack,
}: BackupPageProps) {
  const [status, setStatus] = useState<BackupStatus | null>(null)
  const [destination, setDestination] = useState('')
  const [passphrase, setPassphrase] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<BackupCreationResult | null>(null)
  const [restoreResult, setRestoreResult] =
    useState<RestoreStagingResult | null>(null)

  useEffect(() => {
    let active = true
    loadStatus()
      .then((next) => {
        if (active) setStatus(next)
      })
      .catch(() => {
        if (active) setStatus(null)
      })
    return () => {
      active = false
    }
  }, [loadStatus])

  const chooseFolder = useCallback(async () => {
    if (pickFolder === undefined) return
    const chosen = await pickFolder()
    if (chosen !== null) setDestination(chosen)
  }, [pickFolder])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setResult(null)
    const passphraseBytes = new TextEncoder().encode(passphrase).length
    if (destination.trim() === '') {
      setError('Escolha uma pasta no HD externo.')
      return
    }
    if (passphraseBytes < 12 || passphraseBytes > 1024) {
      setError('A senha do backup deve ter entre 12 e 1024 bytes.')
      return
    }
    if (passphrase !== confirmation) {
      setError('As senhas do backup precisam ser iguais.')
      return
    }
    setBusy(true)
    try {
      const created = await createBackup({
        destination_directory: destination.trim(),
        passphrase,
      })
      setResult(created)
      setStatus({
        last_successful_at: created.created_at,
        reminder_due: false,
      })
      setPassphrase('')
      setConfirmation('')
    } catch (caught) {
      setError(describeFailure(caught))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="import-panel" aria-labelledby="backup-title">
      <header className="section-heading">
        <div>
          <p className="eyebrow">Proteção local</p>
          <h1 id="backup-title">Backup em HD externo</h1>
          <p>
            Crie uma cópia criptografada do banco e de todos os documentos. O
            arquivo anterior não será sobrescrito.
          </p>
        </div>
        <button
          className="secondary-button"
          type="button"
          onClick={onBack}
          disabled={busy}
        >
          Voltar
        </button>
      </header>

      {status?.reminder_due === true && (
        <p className="feedback feedback--warning" role="status">
          Está na hora de criar um backup. O lembrete aparece quando não há uma
          cópia bem-sucedida nos últimos sete dias.
        </p>
      )}

      <form
        className="import-form"
        noValidate
        onSubmit={(event) => void submit(event)}
      >
        <label htmlFor="backup-destination">Pasta no HD externo</label>
        <div className="import-form__source">
          <input
            id="backup-destination"
            value={destination}
            onChange={(event) => setDestination(event.target.value)}
            readOnly={pickFolder !== undefined}
            disabled={busy}
            autoComplete="off"
            spellCheck={false}
            placeholder="Ex.: E:\\Backups"
          />
          {pickFolder !== undefined && (
            <button
              className="secondary-button"
              type="button"
              onClick={() => void chooseFolder()}
              disabled={busy}
            >
              Escolher pasta…
            </button>
          )}
        </div>

        <div className="field">
          <label htmlFor="backup-passphrase">Senha exclusiva do backup</label>
          <input
            id="backup-passphrase"
            type="password"
            autoComplete="new-password"
            minLength={12}
            value={passphrase}
            onChange={(event) => setPassphrase(event.target.value)}
            disabled={busy}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="backup-confirmation">Confirmar senha do backup</label>
          <input
            id="backup-confirmation"
            type="password"
            autoComplete="new-password"
            minLength={12}
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            disabled={busy}
            required
          />
        </div>
        <p className="privacy-note">
          Guarde essa senha separada do computador e do HD. Ela não é salva e
          não pode ser recuperada pela equipe.
        </p>
        <button className="primary-button" type="submit" disabled={busy}>
          {busy ? 'Criando e verificando…' : 'Criar backup criptografado'}
        </button>
      </form>

      {error !== null && (
        <p className="feedback feedback--error" role="alert">
          {error}
        </p>
      )}
      {result !== null && (
        <section className="import-result" aria-label="Backup concluído">
          <h2>Backup concluído e verificado</h2>
          <p>
            Arquivo <strong>{result.filename}</strong> criado com{' '}
            {result.document_count} documento(s). Ejete o HD com segurança e
            guarde-o separado do computador.
          </p>
        </section>
      )}
      {restoreResult === null ? (
        <RestoreBackupPanel
          stageRestore={stageRestore}
          pickFile={pickFile}
          onStaged={setRestoreResult}
          replaceExisting
        />
      ) : (
        <section className="import-result" aria-label="Restauração preparada">
          <h2>Restauração validada</h2>
          <p>
            Feche completamente o CRM e abra novamente. A geração anterior será
            preservada até o novo banco e os documentos passarem pelas
            verificações finais.
          </p>
        </section>
      )}
    </section>
  )
}

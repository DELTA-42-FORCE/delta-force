import { useCallback, useState, type FormEvent } from 'react'

import { ApiError } from '../lib/apiClient'
import type { RestoreStagingResult } from './backupsApi'

interface RestoreBackupPanelProps {
  stageRestore: (input: {
    source_file: string
    passphrase: string
  }) => Promise<RestoreStagingResult>
  pickFile?: () => Promise<string | null>
  onStaged: (result: RestoreStagingResult) => void
}

function describeRestoreFailure(error: unknown): string {
  if (error instanceof ApiError && error.status === 507) {
    return 'O computador não tem espaço livre suficiente para validar a restauração.'
  }
  if (error instanceof ApiError && error.status === 409) {
    return 'A restauração só pode ser preparada antes de criar a primeira conta.'
  }
  if (error instanceof ApiError && error.status === 422) {
    return 'A senha está incorreta, o arquivo está corrompido ou não veio de um HD externo aceito.'
  }
  return 'Não foi possível validar o backup. Os dados atuais não foram alterados.'
}

export function RestoreBackupPanel({
  stageRestore,
  pickFile,
  onStaged,
}: RestoreBackupPanelProps) {
  const [expanded, setExpanded] = useState(false)
  const [sourceFile, setSourceFile] = useState('')
  const [passphrase, setPassphrase] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const chooseFile = useCallback(async () => {
    if (pickFile === undefined) return
    const chosen = await pickFile()
    if (chosen !== null) setSourceFile(chosen)
  }, [pickFile])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    const passphraseBytes = new TextEncoder().encode(passphrase).length
    if (sourceFile.trim() === '') {
      setError('Escolha o arquivo de backup no HD externo.')
      return
    }
    if (passphraseBytes < 12 || passphraseBytes > 1024) {
      setError('A senha do backup deve ter entre 12 e 1024 bytes.')
      return
    }
    setBusy(true)
    try {
      onStaged(
        await stageRestore({
          source_file: sourceFile.trim(),
          passphrase,
        }),
      )
      setPassphrase('')
    } catch (caught) {
      setError(describeRestoreFailure(caught))
    } finally {
      setBusy(false)
    }
  }

  if (!expanded) {
    return (
      <div className="privacy-note">
        <p>Já possui um backup deste CRM?</p>
        <button
          className="secondary-button"
          type="button"
          onClick={() => setExpanded(true)}
        >
          Restaurar pelo HD externo
        </button>
      </div>
    )
  }

  return (
    <form
      className="auth-form"
      noValidate
      onSubmit={(event) => void submit(event)}
    >
      <div className="field">
        <label htmlFor="restore-source">Arquivo de backup</label>
        <input
          id="restore-source"
          value={sourceFile}
          onChange={(event) => setSourceFile(event.target.value)}
          readOnly={pickFile !== undefined}
          disabled={busy}
          autoComplete="off"
          spellCheck={false}
          placeholder="Ex.: E:\\Backups\\delta-force-crm.dfcrmbak"
        />
        {pickFile !== undefined && (
          <button
            className="secondary-button"
            type="button"
            onClick={() => void chooseFile()}
            disabled={busy}
          >
            Escolher arquivo…
          </button>
        )}
      </div>
      <div className="field">
        <label htmlFor="restore-passphrase">Senha do backup</label>
        <input
          id="restore-passphrase"
          type="password"
          autoComplete="current-password"
          value={passphrase}
          onChange={(event) => setPassphrase(event.target.value)}
          disabled={busy}
          minLength={12}
          required
        />
      </div>
      <p className="privacy-note">
        O arquivo será verificado antes de qualquer troca. O backup no HD não é
        apagado.
      </p>
      {error !== null && (
        <p className="feedback feedback--error" role="alert">
          {error}
        </p>
      )}
      <button className="primary-button" type="submit" disabled={busy}>
        {busy ? 'Validando…' : 'Validar e preparar restauração'}
      </button>
      <button
        className="secondary-button"
        type="button"
        onClick={() => setExpanded(false)}
        disabled={busy}
      >
        Voltar à criação da conta
      </button>
    </form>
  )
}

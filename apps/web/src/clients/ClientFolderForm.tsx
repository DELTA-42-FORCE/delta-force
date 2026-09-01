import { useState, type FormEvent } from 'react'

import { ApiError } from '../lib/apiClient'
import type { ClientFolder } from './clientsApi'

interface ProfileEntry {
  key: string
  value: string
}

interface ClientFolderFormProps {
  mode: 'create' | 'edit'
  initialFolder?: ClientFolder
  onSubmit: (input: {
    display_name: string
    profile_data: Record<string, string>
  }) => Promise<void>
  onCancel: () => void
}

function toProfileEntries(
  profileData: Record<string, string> | undefined,
): ProfileEntry[] {
  if (profileData == null) return []
  return Object.entries(profileData).map(([key, value]) => ({ key, value }))
}

export function ClientFolderForm({
  mode,
  initialFolder,
  onSubmit,
  onCancel,
}: ClientFolderFormProps) {
  const [displayName, setDisplayName] = useState(
    initialFolder?.display_name ?? '',
  )
  const [entries, setEntries] = useState<ProfileEntry[]>(
    toProfileEntries(initialFolder?.profile_data),
  )
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function updateEntry(index: number, field: 'key' | 'value', value: string) {
    setEntries((current) =>
      current.map((entry, entryIndex) =>
        entryIndex === index ? { ...entry, [field]: value } : entry,
      ),
    )
  }

  function removeEntry(index: number) {
    setEntries((current) =>
      current.filter((_, entryIndex) => entryIndex !== index),
    )
  }

  function addEntry() {
    setEntries((current) => [...current, { key: '', value: '' }])
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      const profileData = Object.fromEntries(
        entries
          .map(({ key, value }) => [key.trim(), value] as const)
          .filter(([key]) => key !== ''),
      )
      await onSubmit({ display_name: displayName, profile_data: profileData })
    } catch (submitError) {
      if (submitError instanceof ApiError && submitError.status === 422) {
        setError('Verifique o nome informado e tente novamente.')
      } else {
        setError('Não foi possível salvar a pasta do cliente. Tente novamente.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form className="client-folder-form" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="client-display-name">Nome do cliente</label>
        <input
          id="client-display-name"
          required
          minLength={1}
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
          placeholder="Nome de identificação"
        />
      </div>

      <div className="client-folder-form__profile">
        <div className="client-folder-form__profile-heading">
          <span>Dados adicionais (opcional)</span>
          <button className="text-button" type="button" onClick={addEntry}>
            + Adicionar campo
          </button>
        </div>
        {entries.map((entry, index) => (
          <div className="client-folder-form__profile-row" key={index}>
            <input
              aria-label="Nome do campo"
              value={entry.key}
              onChange={(event) =>
                updateEntry(index, 'key', event.target.value)
              }
              placeholder="Ex.: telefone"
            />
            <input
              aria-label="Valor do campo"
              value={entry.value}
              onChange={(event) =>
                updateEntry(index, 'value', event.target.value)
              }
              placeholder="Ex.: (92) 0000-0000"
            />
            <button
              className="text-button"
              type="button"
              onClick={() => removeEntry(index)}
              aria-label="Remover campo"
            >
              Remover
            </button>
          </div>
        ))}
      </div>

      {error !== null && (
        <p className="feedback feedback--error" role="alert">
          {error}
        </p>
      )}

      <div className="client-folder-form__actions">
        <button
          className="secondary-button"
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
        >
          Cancelar
        </button>
        <button
          className="primary-button"
          type="submit"
          disabled={isSubmitting}
        >
          {isSubmitting
            ? 'Salvando…'
            : mode === 'create'
              ? 'Criar cliente'
              : 'Salvar alterações'}
        </button>
      </div>
    </form>
  )
}

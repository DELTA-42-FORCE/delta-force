import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'

import type { ClientFolder } from '../clients/clientsApi'
import type { DownloadedFile } from '../lib/apiClient'
import {
  describeAttachFailure,
  describeExportFailure,
  describeMediaType,
  formatByteSize,
} from './documentMessages'
import type {
  ClientDocument,
  ClientDocumentPage,
  DocumentAnnotations,
  DocumentCursor,
} from './documentsApi'

interface ClientDocumentsPanelProps {
  folder: ClientFolder
  loadPage: (cursor: DocumentCursor | null) => Promise<ClientDocumentPage>
  attachDocument: (input: {
    file: File
    annotations: DocumentAnnotations
  }) => Promise<ClientDocument>
  exportDocument: (document: ClientDocument) => Promise<DownloadedFile>
  onBack: () => void
}

function saveToDisk(file: DownloadedFile, fallbackName: string) {
  const url = URL.createObjectURL(file.blob)
  try {
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = file.filename ?? fallbackName
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
  } finally {
    URL.revokeObjectURL(url)
  }
}

export function ClientDocumentsPanel({
  folder,
  loadPage,
  attachDocument,
  exportDocument,
  onBack,
}: ClientDocumentsPanelProps) {
  const [documents, setDocuments] = useState<ClientDocument[]>([])
  const [nextCursor, setNextCursor] = useState<DocumentCursor | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [moreState, setMoreState] = useState<'idle' | 'loading' | 'error'>(
    'idle',
  )
  const [loadSequence, setLoadSequence] = useState(0)
  const [attachState, setAttachState] = useState<'idle' | 'sending'>('idle')
  const [attachError, setAttachError] = useState<string | null>(null)
  const [attachNotice, setAttachNotice] = useState<string | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)
  const [exportingId, setExportingId] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState('')
  const [notes, setNotes] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const initialRequestRef = useRef<{
    key: string
    request: Promise<ClientDocumentPage>
  } | null>(null)

  useEffect(() => {
    let active = true
    const requestKey = `${folder.id}:${loadSequence}`
    const cachedRequest = initialRequestRef.current
    const request =
      cachedRequest?.key === requestKey ? cachedRequest.request : loadPage(null)
    initialRequestRef.current = { key: requestKey, request }

    void request
      .then((page) => {
        if (!active) return
        setDocuments(page.items)
        setNextCursor(page.nextCursor)
        setState('ready')
      })
      .catch(() => {
        if (active) setState('error')
      })

    return () => {
      active = false
    }
  }, [folder.id, loadPage, loadSequence])

  const refresh = useCallback(() => {
    initialRequestRef.current = null
    setDocuments([])
    setNextCursor(null)
    setMoreState('idle')
    setState('loading')
    setLoadSequence((current) => current + 1)
  }, [])

  const loadMore = useCallback(async () => {
    if (nextCursor === null || moreState === 'loading') return
    setMoreState('loading')
    try {
      const page = await loadPage(nextCursor)
      setDocuments((current) => [...current, ...page.items])
      setNextCursor(page.nextCursor)
      setMoreState('idle')
    } catch {
      setMoreState('error')
    }
  }, [loadPage, moreState, nextCursor])

  async function handleAttach(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAttachError(null)
    setAttachNotice(null)

    const file = fileInputRef.current?.files?.[0]
    if (file === undefined) {
      setAttachError('Escolha um arquivo PDF ou JPEG para anexar.')
      return
    }

    setAttachState('sending')
    try {
      const stored = await attachDocument({
        file,
        annotations: { title, category, notes },
      })
      setAttachNotice(`"${stored.original_filename}" foi anexado à pasta.`)
      setTitle('')
      setCategory('')
      setNotes('')
      if (fileInputRef.current !== null) fileInputRef.current.value = ''
      refresh()
    } catch (error) {
      setAttachError(describeAttachFailure(error))
    } finally {
      setAttachState('idle')
    }
  }

  async function handleExport(item: ClientDocument) {
    setExportError(null)
    setExportingId(item.id)
    try {
      saveToDisk(await exportDocument(item), item.original_filename)
    } catch (error) {
      setExportError(describeExportFailure(error))
    } finally {
      setExportingId(null)
    }
  }

  return (
    <section className="documents-panel" aria-labelledby="documents-title">
      <div className="clients-page__heading">
        <div>
          <p className="eyebrow">Documentos</p>
          <h1 id="documents-title">{folder.display_name}</h1>
          <p>
            Anexe PDFs e fotos JPEG desta pasta. Os arquivos ficam neste
            computador, em área privada do CRM.
          </p>
        </div>
        <button
          className="secondary-button compact-button"
          type="button"
          onClick={onBack}
        >
          Voltar
        </button>
      </div>

      <form
        className="document-form"
        onSubmit={(event) => void handleAttach(event)}
      >
        <div className="document-form__row">
          <label htmlFor="document-file">Arquivo (PDF ou JPEG)</label>
          <input
            id="document-file"
            ref={fileInputRef}
            type="file"
            accept=".pdf,.jpg,.jpeg,application/pdf,image/jpeg"
          />
        </div>

        <div className="document-form__row">
          <label htmlFor="document-title">Título (opcional)</label>
          <input
            id="document-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Ex.: contrato assinado"
          />
        </div>

        <div className="document-form__row">
          <label htmlFor="document-category">Categoria (opcional)</label>
          <input
            id="document-category"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            placeholder="Texto livre — não há lista fixa"
          />
        </div>

        <div className="document-form__row">
          <label htmlFor="document-notes">Observação (opcional)</label>
          <textarea
            id="document-notes"
            value={notes}
            rows={2}
            onChange={(event) => setNotes(event.target.value)}
          />
        </div>

        <div className="document-form__actions">
          <button
            className="primary-button compact-button"
            type="submit"
            disabled={attachState === 'sending'}
          >
            {attachState === 'sending' ? 'Anexando…' : 'Anexar documento'}
          </button>
        </div>

        {attachError !== null && (
          <p className="feedback feedback--error" role="alert">
            {attachError}
          </p>
        )}
        {attachNotice !== null && (
          <p className="feedback feedback--success" role="status">
            {attachNotice}
          </p>
        )}
      </form>

      <div className="activity-card" aria-live="polite">
        {state === 'loading' && (
          <div className="activity-state" aria-busy="true">
            <span className="loader" aria-hidden="true" />
            <p>Carregando documentos…</p>
          </div>
        )}

        {state === 'error' && (
          <div className="activity-state">
            <p role="alert">
              Não foi possível consultar os documentos desta pasta agora.
            </p>
            <button
              className="secondary-button"
              type="button"
              onClick={refresh}
            >
              Tentar novamente
            </button>
          </div>
        )}

        {state === 'ready' && documents.length === 0 && (
          <div className="activity-state">
            <span className="activity-state__icon" aria-hidden="true">
              ▤
            </span>
            <p>Nenhum documento anexado a esta pasta ainda.</p>
          </div>
        )}

        {state === 'ready' && documents.length > 0 && (
          <>
            {exportError !== null && (
              <p className="feedback feedback--error" role="alert">
                {exportError}
              </p>
            )}
            <ul className="documents-list">
              {documents.map((item) => (
                <li className="documents-list__item" key={item.id}>
                  <div className="documents-list__info">
                    <strong>{item.title ?? item.original_filename}</strong>
                    <small>
                      {describeMediaType(item.media_type)} ·{' '}
                      {formatByteSize(item.byte_size)}
                      {item.category !== null && ` · ${item.category}`}
                    </small>
                    {item.notes !== null && (
                      <small className="documents-list__notes">
                        {item.notes}
                      </small>
                    )}
                  </div>
                  <button
                    className="text-button"
                    type="button"
                    disabled={exportingId === item.id}
                    onClick={() => void handleExport(item)}
                  >
                    {exportingId === item.id ? 'Exportando…' : 'Exportar cópia'}
                  </button>
                </li>
              ))}
            </ul>
            {(nextCursor !== null || moreState === 'error') && (
              <div className="clients-page__more">
                {moreState === 'error' && (
                  <p role="alert">Não foi possível carregar mais documentos.</p>
                )}
                <button
                  className="secondary-button"
                  type="button"
                  disabled={moreState === 'loading'}
                  onClick={() => void loadMore()}
                >
                  {moreState === 'loading'
                    ? 'Carregando…'
                    : moreState === 'error'
                      ? 'Tentar carregar novamente'
                      : 'Carregar mais'}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  )
}

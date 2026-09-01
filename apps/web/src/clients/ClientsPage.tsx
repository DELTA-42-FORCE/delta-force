import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'

import { ClientFolderForm } from './ClientFolderForm'
import type { ClientCursor, ClientFolder, ClientFolderPage } from './clientsApi'

interface ClientsPageProps {
  loadPage: (
    cursor: ClientCursor | null,
    query: string | null,
  ) => Promise<ClientFolderPage>
  createFolder: (input: {
    display_name: string
    profile_data: Record<string, string>
  }) => Promise<ClientFolder>
  updateFolder: (
    id: string,
    input: { display_name: string; profile_data: Record<string, string> },
  ) => Promise<ClientFolder>
}

type View =
  { mode: 'list' } | { mode: 'create' } | { mode: 'edit'; folder: ClientFolder }

export function ClientsPage({
  loadPage,
  createFolder,
  updateFolder,
}: ClientsPageProps) {
  const [folders, setFolders] = useState<ClientFolder[]>([])
  const [nextCursor, setNextCursor] = useState<ClientCursor | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [moreState, setMoreState] = useState<'idle' | 'loading' | 'error'>(
    'idle',
  )
  const [searchInput, setSearchInput] = useState('')
  const [activeQuery, setActiveQuery] = useState<string | null>(null)
  const [loadSequence, setLoadSequence] = useState(0)
  const [view, setView] = useState<View>({ mode: 'list' })
  const initialRequestRef = useRef<{
    key: string
    request: Promise<ClientFolderPage>
  } | null>(null)

  useEffect(() => {
    let active = true
    const requestKey = `${activeQuery ?? 'all'}:${loadSequence}`
    const cachedRequest = initialRequestRef.current
    const request =
      cachedRequest?.key === requestKey
        ? cachedRequest.request
        : loadPage(null, activeQuery)
    initialRequestRef.current = { key: requestKey, request }

    void request
      .then((page) => {
        if (!active) return
        setFolders(page.items)
        setNextCursor(page.nextCursor)
        setState('ready')
      })
      .catch(() => {
        if (active) setState('error')
      })

    return () => {
      active = false
    }
  }, [activeQuery, loadPage, loadSequence])

  const retryInitial = useCallback(() => {
    initialRequestRef.current = null
    setState('loading')
    setLoadSequence((current) => current + 1)
  }, [])

  const refresh = useCallback(() => {
    initialRequestRef.current = null
    setFolders([])
    setNextCursor(null)
    setMoreState('idle')
    setState('loading')
    setLoadSequence((current) => current + 1)
  }, [])

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    refresh()
    setActiveQuery(searchInput.trim() === '' ? null : searchInput.trim())
  }

  const loadMore = useCallback(async () => {
    if (nextCursor === null || moreState === 'loading') return
    setMoreState('loading')
    try {
      const page = await loadPage(nextCursor, activeQuery)
      setFolders((current) => [...current, ...page.items])
      setNextCursor(page.nextCursor)
      setMoreState('idle')
    } catch {
      setMoreState('error')
    }
  }, [activeQuery, loadPage, moreState, nextCursor])

  async function handleCreate(input: {
    display_name: string
    profile_data: Record<string, string>
  }) {
    await createFolder(input)
    setView({ mode: 'list' })
    refresh()
  }

  async function handleUpdate(
    folderId: string,
    input: { display_name: string; profile_data: Record<string, string> },
  ) {
    await updateFolder(folderId, input)
    setView({ mode: 'list' })
    refresh()
  }

  if (view.mode === 'create') {
    return (
      <section className="clients-page" aria-labelledby="clients-title">
        <h1 id="clients-title">Novo cliente</h1>
        <ClientFolderForm
          mode="create"
          onSubmit={handleCreate}
          onCancel={() => setView({ mode: 'list' })}
        />
      </section>
    )
  }

  if (view.mode === 'edit') {
    return (
      <section className="clients-page" aria-labelledby="clients-title">
        <h1 id="clients-title">Editar cliente</h1>
        <ClientFolderForm
          mode="edit"
          initialFolder={view.folder}
          onSubmit={(input) => handleUpdate(view.folder.id, input)}
          onCancel={() => setView({ mode: 'list' })}
        />
      </section>
    )
  }

  return (
    <section className="clients-page" aria-labelledby="clients-title">
      <div className="clients-page__heading">
        <div>
          <p className="eyebrow">Diretório</p>
          <h1 id="clients-title">Clientes</h1>
          <p>Cadastre, busque e edite as pastas de clientes.</p>
        </div>
        <button
          className="primary-button compact-button"
          type="button"
          onClick={() => setView({ mode: 'create' })}
        >
          Novo cliente
        </button>
      </div>

      <form className="clients-page__search" onSubmit={handleSearchSubmit}>
        <label htmlFor="client-search" className="sr-only">
          Buscar cliente
        </label>
        <input
          id="client-search"
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
          placeholder="Buscar por nome"
        />
        <button className="secondary-button" type="submit">
          Buscar
        </button>
      </form>

      <div className="activity-card" aria-live="polite">
        {state === 'loading' && (
          <div className="activity-state" aria-busy="true">
            <span className="loader" aria-hidden="true" />
            <p>Carregando clientes…</p>
          </div>
        )}

        {state === 'error' && (
          <div className="activity-state">
            <p role="alert">Não foi possível consultar os clientes agora.</p>
            <button
              className="secondary-button"
              type="button"
              onClick={retryInitial}
            >
              Tentar novamente
            </button>
          </div>
        )}

        {state === 'ready' && folders.length === 0 && (
          <div className="activity-state">
            <span className="activity-state__icon" aria-hidden="true">
              ✓
            </span>
            <p>Nenhum cliente cadastrado ainda.</p>
          </div>
        )}

        {state === 'ready' && folders.length > 0 && (
          <>
            <ul className="clients-list">
              {folders.map((folder) => (
                <li className="clients-list__item" key={folder.id}>
                  <span>{folder.display_name}</span>
                  <button
                    className="text-button"
                    type="button"
                    onClick={() => setView({ mode: 'edit', folder })}
                  >
                    Editar
                  </button>
                </li>
              ))}
            </ul>
            {(nextCursor !== null || moreState === 'error') && (
              <div className="clients-page__more">
                {moreState === 'error' && (
                  <p role="alert">Não foi possível carregar mais clientes.</p>
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

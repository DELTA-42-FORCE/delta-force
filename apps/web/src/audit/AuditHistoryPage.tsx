import { useCallback, useEffect, useRef, useState } from 'react'

import type {
  AuditActionFilter,
  AuditCursor,
  AuditEvent,
  AuditEventPage,
  AuditFilters,
  AuditResultFilter,
} from './auditApi'
import { AuditEventList } from './AuditEventList'

interface AuditHistoryPageProps {
  loadPage: (
    cursor: AuditCursor | null,
    filters: AuditFilters,
  ) => Promise<AuditEventPage>
  onBack: () => void
}

const ACTION_FILTER_OPTIONS: ReadonlyArray<
  readonly [AuditActionFilter, string]
> = [
  ['auth.owner_setup', 'Criação da conta'],
  ['auth.login', 'Entradas'],
  ['auth.owner_profile_view', 'Consultas ao perfil'],
  ['auth.logout', 'Saídas'],
  ['auth.access_denied', 'Acessos negados'],
  ['audit.log_view', 'Consultas à auditoria'],
]

const RESULT_FILTER_OPTIONS: ReadonlyArray<
  readonly [AuditResultFilter, string]
> = [
  ['success', 'Concluídas'],
  ['denied', 'Negadas'],
  ['failure', 'Falhas'],
]

export function AuditHistoryPage({ loadPage, onBack }: AuditHistoryPageProps) {
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [nextCursor, setNextCursor] = useState<AuditCursor | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [moreState, setMoreState] = useState<'idle' | 'loading' | 'error'>(
    'idle',
  )
  const [actionFilter, setActionFilter] = useState<AuditActionFilter | null>(
    null,
  )
  const [resultFilter, setResultFilter] = useState<AuditResultFilter | null>(
    null,
  )
  const [loadSequence, setLoadSequence] = useState(0)
  const initialRequestRef = useRef<{
    key: string
    request: Promise<AuditEventPage>
  } | null>(null)

  useEffect(() => {
    let active = true
    const requestKey = `${actionFilter ?? 'all'}:${resultFilter ?? 'all'}:${loadSequence}`
    const cachedRequest = initialRequestRef.current
    const request =
      cachedRequest?.key === requestKey
        ? cachedRequest.request
        : loadPage(null, { action: actionFilter, result: resultFilter })
    initialRequestRef.current = { key: requestKey, request }

    void request
      .then((page) => {
        if (!active) return
        setEvents(page.items)
        setNextCursor(page.nextCursor)
        setState('ready')
      })
      .catch(() => {
        if (active) setState('error')
      })

    return () => {
      active = false
    }
  }, [actionFilter, loadPage, loadSequence, resultFilter])

  const retryInitial = useCallback(() => {
    initialRequestRef.current = null
    setState('loading')
    setLoadSequence((current) => current + 1)
  }, [])

  const resetForFilter = useCallback(() => {
    initialRequestRef.current = null
    setEvents([])
    setNextCursor(null)
    setMoreState('idle')
    setState('loading')
  }, [])

  const changeActionFilter = useCallback(
    (value: string) => {
      resetForFilter()
      setActionFilter(value === '' ? null : (value as AuditActionFilter))
    },
    [resetForFilter],
  )

  const changeResultFilter = useCallback(
    (value: string) => {
      resetForFilter()
      setResultFilter(value === '' ? null : (value as AuditResultFilter))
    },
    [resetForFilter],
  )

  const loadMore = useCallback(async () => {
    if (nextCursor === null || moreState === 'loading') return
    setMoreState('loading')
    try {
      const page = await loadPage(nextCursor, {
        action: actionFilter,
        result: resultFilter,
      })
      setEvents((current) => [...current, ...page.items])
      setNextCursor(page.nextCursor)
      setMoreState('idle')
    } catch {
      setMoreState('error')
    }
  }, [actionFilter, loadPage, moreState, nextCursor, resultFilter])

  return (
    <section className="audit-page" aria-labelledby="audit-history-title">
      <button
        className="text-button audit-page__back"
        type="button"
        onClick={onBack}
      >
        ← Voltar para visão geral
      </button>
      <div className="audit-page__heading">
        <div>
          <p className="eyebrow">Segurança e controle</p>
          <h1 id="audit-history-title">Histórico de auditoria</h1>
          <p>
            Consulte as ações relevantes registradas pelo CRM neste computador.
          </p>
        </div>
        <span className="status-pill">
          <span aria-hidden="true">●</span> Acesso protegido
        </span>
      </div>

      <div className="audit-filters" aria-label="Filtros do histórico">
        <label>
          Tipo de ação
          <select
            value={actionFilter ?? ''}
            onChange={(event) => changeActionFilter(event.target.value)}
          >
            <option value="">Todas as ações</option>
            {ACTION_FILTER_OPTIONS.map(([value, label]) => (
              <option value={value} key={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Resultado
          <select
            value={resultFilter ?? ''}
            onChange={(event) => changeResultFilter(event.target.value)}
          >
            <option value="">Todos os resultados</option>
            {RESULT_FILTER_OPTIONS.map(([value, label]) => (
              <option value={value} key={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="activity-card" aria-live="polite">
        {state === 'loading' && (
          <div className="activity-state" aria-busy="true">
            <span className="loader" aria-hidden="true" />
            <p>Carregando histórico…</p>
          </div>
        )}

        {state === 'error' && (
          <div className="activity-state">
            <p role="alert">Não foi possível consultar o histórico agora.</p>
            <button
              className="secondary-button"
              type="button"
              onClick={retryInitial}
            >
              Tentar novamente
            </button>
          </div>
        )}

        {state === 'ready' && events.length === 0 && (
          <div className="activity-state">
            <span className="activity-state__icon" aria-hidden="true">
              ✓
            </span>
            <p>Nenhuma atividade registrada ainda.</p>
          </div>
        )}

        {state === 'ready' && events.length > 0 && (
          <>
            <AuditEventList events={events} />
            {(nextCursor !== null || moreState === 'error') && (
              <div className="audit-page__more">
                {moreState === 'error' && (
                  <p role="alert">
                    Não foi possível carregar os registros anteriores.
                  </p>
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

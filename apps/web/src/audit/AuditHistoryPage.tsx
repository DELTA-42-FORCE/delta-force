import { useCallback, useEffect, useRef, useState } from 'react'

import type { AuditCursor, AuditEvent, AuditEventPage } from './auditApi'
import { AuditEventList } from './AuditEventList'

interface AuditHistoryPageProps {
  loadPage: (cursor: AuditCursor | null) => Promise<AuditEventPage>
  onBack: () => void
}

export function AuditHistoryPage({ loadPage, onBack }: AuditHistoryPageProps) {
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [nextCursor, setNextCursor] = useState<AuditCursor | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [moreState, setMoreState] = useState<'idle' | 'loading' | 'error'>(
    'idle',
  )
  const [loadSequence, setLoadSequence] = useState(0)
  const initialRequestRef = useRef<Promise<AuditEventPage> | null>(null)

  useEffect(() => {
    let active = true
    const request = initialRequestRef.current ?? loadPage(null)
    initialRequestRef.current = request

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
  }, [loadPage, loadSequence])

  const retryInitial = useCallback(() => {
    initialRequestRef.current = null
    setState('loading')
    setLoadSequence((current) => current + 1)
  }, [])

  const loadMore = useCallback(async () => {
    if (nextCursor === null || moreState === 'loading') return
    setMoreState('loading')
    try {
      const page = await loadPage(nextCursor)
      setEvents((current) => [...current, ...page.items])
      setNextCursor(page.nextCursor)
      setMoreState('idle')
    } catch {
      setMoreState('error')
    }
  }, [loadPage, moreState, nextCursor])

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

import { useCallback, useEffect, useRef, useState } from 'react'

import type { AuditEvent } from './auditApi'
import { AuditEventList } from './AuditEventList'

interface RecentActivityProps {
  loadEvents: () => Promise<AuditEvent[]>
  onViewAll: () => void
}

export function RecentActivity({ loadEvents, onViewAll }: RecentActivityProps) {
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [loadSequence, setLoadSequence] = useState(0)
  const requestRef = useRef<Promise<AuditEvent[]> | null>(null)

  useEffect(() => {
    let active = true
    const request = requestRef.current ?? loadEvents()
    requestRef.current = request

    void request
      .then((items) => {
        if (!active) return
        setEvents(items)
        setState('ready')
      })
      .catch(() => {
        if (active) setState('error')
      })

    return () => {
      active = false
    }
  }, [loadEvents, loadSequence])

  const retry = useCallback(() => {
    requestRef.current = null
    setState('loading')
    setLoadSequence((current) => current + 1)
  }, [])

  return (
    <section className="activity-section" aria-labelledby="activity-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Segurança e controle</p>
          <h2 id="activity-title">Atividade recente</h2>
        </div>
        <button className="text-button" type="button" onClick={onViewAll}>
          Ver histórico completo
        </button>
      </div>

      <div className="activity-card" aria-live="polite">
        {state === 'loading' && (
          <div className="activity-state" aria-busy="true">
            <span className="loader" aria-hidden="true" />
            <p>Carregando atividades…</p>
          </div>
        )}

        {state === 'error' && (
          <div className="activity-state">
            <p role="alert">Não foi possível consultar as atividades agora.</p>
            <button className="secondary-button" type="button" onClick={retry}>
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
          <AuditEventList events={events} />
        )}
      </div>
    </section>
  )
}

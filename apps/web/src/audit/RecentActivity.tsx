import { useCallback, useEffect, useRef, useState } from 'react'

import type { AuditEvent } from './auditApi'

interface RecentActivityProps {
  loadEvents: () => Promise<AuditEvent[]>
}

const ACTION_LABELS: Readonly<Record<string, string>> = {
  'auth.owner_setup': 'Conta do proprietário criada',
  'auth.login': 'Entrada realizada',
  'auth.owner_profile_view': 'Perfil consultado',
  'auth.logout': 'Saída realizada',
  'auth.access_denied': 'Acesso negado',
  'audit.log_view': 'Atividades consultadas',
}

const RESULT_LABELS: Readonly<Record<string, string>> = {
  success: 'Concluída',
  denied: 'Negada',
  failure: 'Falhou',
}

function formatOccurredAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Horário indisponível'
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date)
}

function resultClassName(result: string): string {
  if (result === 'success' || result === 'denied' || result === 'failure') {
    return `activity-result activity-result--${result}`
  }
  return 'activity-result'
}

export function RecentActivity({ loadEvents }: RecentActivityProps) {
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
        <span>Últimos 5 registros</span>
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
          <ol className="activity-list">
            {events.map((event, index) => (
              <li
                className="activity-list__item"
                key={`${event.occurred_at}-${index}`}
              >
                <span className="activity-list__marker" aria-hidden="true" />
                <div>
                  <strong>
                    {ACTION_LABELS[event.action] ?? 'Atividade registrada'}
                  </strong>
                  <time dateTime={event.occurred_at}>
                    {formatOccurredAt(event.occurred_at)}
                  </time>
                </div>
                <span className={resultClassName(event.result)}>
                  {RESULT_LABELS[event.result] ?? 'Registrada'}
                </span>
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  )
}

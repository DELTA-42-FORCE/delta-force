import type { AuditEvent } from './auditApi'

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

export function AuditEventList({ events }: { events: AuditEvent[] }) {
  return (
    <ol className="activity-list">
      {events.map((event, index) => (
        <li
          className="activity-list__item"
          key={`${event.occurred_at}-${event.action}-${index}`}
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
  )
}

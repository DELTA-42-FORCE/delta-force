export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand${compact ? ' brand--compact' : ''}`}>
      <span className="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 32 32">
          <path d="M6 7h8v8H6zM18 7h8v8h-8zM6 19h8v6H6zM18 19h8v6h-8z" />
        </svg>
      </span>
      <span className="brand-name">
        Delta Force <small>CRM</small>
      </span>
    </div>
  )
}

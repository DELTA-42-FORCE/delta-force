import type { ReactNode } from 'react'

import { Brand } from '../ui/Brand'

interface AuthLayoutProps {
  eyebrow: string
  title: string
  description: string
  children: ReactNode
}

export function AuthLayout({
  eyebrow,
  title,
  description,
  children,
}: AuthLayoutProps) {
  return (
    <main className="auth-shell">
      <section className="auth-brand-panel" aria-label="Delta Force CRM">
        <Brand />
        <div className="auth-brand-copy">
          <p className="eyebrow eyebrow--light">Gestão local e segura</p>
          <h2>Seus clientes e documentos em um só lugar.</h2>
          <p>
            Um ambiente privado para organizar o trabalho do escritório neste
            computador.
          </p>
        </div>
        <p className="auth-local-note">
          <span aria-hidden="true">●</span> Dados mantidos localmente
        </p>
      </section>

      <section className="auth-form-panel">
        <div className="auth-mobile-brand">
          <Brand compact />
        </div>
        <div className="auth-card">
          <div className="auth-heading">
            <p className="eyebrow">{eyebrow}</p>
            <h1>{title}</h1>
            <p>{description}</p>
          </div>
          {children}
        </div>
        <p className="auth-footer">
          Delta Force CRM · Aplicativo local Windows
        </p>
      </section>
    </main>
  )
}

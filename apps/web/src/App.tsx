import { useCallback, useState } from 'react'

import { listAuditEvents, listRecentAuditEvents } from './audit/auditApi'
import type { AuditCursor, AuditFilters } from './audit/auditApi'
import { AuditHistoryPage } from './audit/AuditHistoryPage'
import { RecentActivity } from './audit/RecentActivity'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { LoginPage } from './auth/LoginPage'
import { SetupPage } from './auth/SetupPage'
import { Brand } from './ui/Brand'

function Root() {
  const { status, user, authenticatedGet, logout, retry } = useAuth()
  const [logoutNotice, setLogoutNotice] = useState<string | null>(null)
  const [activeView, setActiveView] = useState<'overview' | 'audit'>('overview')

  const loadRecentActivity = useCallback(
    () => listRecentAuditEvents(authenticatedGet),
    [authenticatedGet],
  )

  const loadAuditPage = useCallback(
    (cursor: AuditCursor | null, filters: AuditFilters) =>
      listAuditEvents(authenticatedGet, { limit: 20, cursor, filters }),
    [authenticatedGet],
  )

  async function handleLogout() {
    setLogoutNotice(null)
    setActiveView('overview')
    try {
      await logout()
    } catch {
      setLogoutNotice(
        'Você saiu deste aplicativo, mas não foi possível confirmar o encerramento no serviço local.',
      )
    }
  }

  if (status === 'checking-setup') {
    return (
      <main className="status-screen" aria-busy="true">
        <Brand />
        <span className="loader" aria-hidden="true" />
        <p>Preparando seu ambiente…</p>
      </main>
    )
  }
  if (status === 'setup-required') return <SetupPage />
  if (status === 'signed-out') return <LoginPage notice={logoutNotice} />
  if (status === 'unavailable') {
    return (
      <main className="status-screen">
        <Brand />
        <div className="status-icon" aria-hidden="true">
          !
        </div>
        <h1>Serviço local indisponível</h1>
        <p role="alert">
          Não foi possível conectar ao serviço do CRM neste computador.
        </p>
        <button
          className="primary-button compact-button"
          type="button"
          onClick={retry}
        >
          Tentar novamente
        </button>
      </main>
    )
  }
  if (user === null) return null

  const initials = user.full_name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()

  return (
    <div className="workspace-shell">
      <aside className="workspace-sidebar">
        <Brand compact />
        <nav aria-label="Navegação principal">
          <p className="nav-label">Menu</p>
          <ul className="workspace-nav">
            <li>
              <button
                className={`workspace-nav__item${activeView === 'overview' ? ' workspace-nav__item--active' : ''}`}
                type="button"
                aria-current={activeView === 'overview' ? 'page' : undefined}
                onClick={() => setActiveView('overview')}
              >
                <span aria-hidden="true">⌂</span>
                <span>Visão geral</span>
              </button>
            </li>
            <li>
              <button
                className={`workspace-nav__item${activeView === 'audit' ? ' workspace-nav__item--active' : ''}`}
                type="button"
                aria-current={activeView === 'audit' ? 'page' : undefined}
                onClick={() => setActiveView('audit')}
              >
                <span aria-hidden="true">◷</span>
                <span>Auditoria</span>
              </button>
            </li>
            <li className="workspace-nav__item">
              <span aria-hidden="true">◎</span> Clientes <small>em breve</small>
            </li>
            <li className="workspace-nav__item">
              <span aria-hidden="true">▤</span> Documentos{' '}
              <small>em breve</small>
            </li>
            <li className="workspace-nav__item">
              <span aria-hidden="true">✉</span> E-mails <small>em breve</small>
            </li>
          </ul>
        </nav>
        <div className="sidebar-security">
          <span aria-hidden="true">✓</span>
          <div>
            <strong>Ambiente local</strong>
            <small>Conectado com segurança</small>
          </div>
        </div>
      </aside>

      <main className="workspace-main">
        <header className="workspace-header">
          <div className="workspace-mobile-brand">
            <Brand compact />
          </div>
          <div className="profile-summary">
            <span className="profile-avatar" aria-hidden="true">
              {initials}
            </span>
            <div>
              <strong>{user.full_name}</strong>
              <small>{user.email}</small>
            </div>
          </div>
          <button
            className="secondary-button"
            type="button"
            onClick={() => void handleLogout()}
          >
            Sair
          </button>
        </header>

        <div className="workspace-content">
          {activeView === 'audit' ? (
            <AuditHistoryPage
              loadPage={loadAuditPage}
              onBack={() => setActiveView('overview')}
            />
          ) : (
            <>
              <section className="welcome-panel">
                <div>
                  <p className="eyebrow">Visão geral</p>
                  <h1>Bem-vindo, {user.full_name}</h1>
                  <p>
                    Seu acesso está funcionando. A próxima etapa adicionará o
                    cadastro e a organização de clientes.
                  </p>
                </div>
                <span className="status-pill">
                  <span aria-hidden="true">●</span> Sessão ativa
                </span>
              </section>

              <section
                className="progress-card"
                aria-labelledby="progress-title"
              >
                <div className="progress-card__icon" aria-hidden="true">
                  ✓
                </div>
                <div>
                  <p className="eyebrow">Primeira etapa concluída</p>
                  <h2 id="progress-title">Conta do proprietário protegida</h2>
                  <p>
                    Criação de conta, entrada e saída já usam o serviço local do
                    CRM. A sessão não é salva no navegador.
                  </p>
                </div>
              </section>

              <section
                className="module-section"
                aria-labelledby="modules-title"
              >
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">Construção do MVP</p>
                    <h2 id="modules-title">Próximos módulos</h2>
                  </div>
                  <span>1 de 4 disponível</span>
                </div>
                <div className="module-grid">
                  {[
                    [
                      '01',
                      'Acesso seguro',
                      'Conta única, login e logout.',
                      'Disponível',
                    ],
                    [
                      '02',
                      'Clientes',
                      'Cadastro, busca, consulta e edição.',
                      'Próxima etapa',
                    ],
                    [
                      '03',
                      'Documentos',
                      'PDFs e fotos JPEG por cliente.',
                      'Planejado',
                    ],
                    [
                      '04',
                      'Comunicação',
                      'Modelos e histórico de e-mails.',
                      'Planejado',
                    ],
                  ].map(([number, title, description, state], index) => (
                    <article
                      className={`module-card${index === 0 ? ' module-card--ready' : ''}`}
                      key={number}
                    >
                      <span className="module-card__number">{number}</span>
                      <h3>{title}</h3>
                      <p>{description}</p>
                      <strong>{state}</strong>
                    </article>
                  ))}
                </div>
              </section>

              <RecentActivity
                loadEvents={loadRecentActivity}
                onViewAll={() => setActiveView('audit')}
              />
            </>
          )}
        </div>
      </main>
    </div>
  )
}

export function App() {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  )
}

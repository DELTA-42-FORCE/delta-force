import { useCallback, useState } from 'react'

import { listAuditEvents, listRecentAuditEvents } from './audit/auditApi'
import type { AuditCursor, AuditFilters } from './audit/auditApi'
import { AuditHistoryPage } from './audit/AuditHistoryPage'
import { RecentActivity } from './audit/RecentActivity'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { LoginPage } from './auth/LoginPage'
import { SetupPage } from './auth/SetupPage'
import {
  createClientFolder,
  exportClientProfile,
  listClientFolders,
  updateClientFolder,
} from './clients/clientsApi'
import type { ClientCursor, ClientFolder } from './clients/clientsApi'
import { ClientsPage } from './clients/ClientsPage'
import { CommunicationsPage } from './communications/CommunicationsPage'
import {
  createMessageTemplate,
  deleteMessageTemplate,
  listMessageTemplates,
  listRecipientCandidates,
  updateMessageTemplate,
} from './communications/communicationsApi'
import { ContractsPanel } from './contracts/ContractsPanel'
import {
  cancelClientContract,
  createClientContract,
  listClientContracts,
  recordInstallmentPayment,
} from './contracts/contractsApi'
import type {
  ClientContract,
  ContractInstallment,
  CreateContractInput,
} from './contracts/contractsApi'
import type {
  MessageTemplate,
  MessageTemplatePayload,
  RecipientCandidateCursor,
  RecipientDocumentStatus,
} from './communications/communicationsApi'
import { ClientDocumentsPanel } from './documents/ClientDocumentsPanel'
import {
  attachClientDocument,
  exportClientDocument,
  listClientDocuments,
  openClientDocument,
  updateClientDocumentStatus,
} from './documents/documentsApi'
import type {
  ClientDocument,
  DocumentAnnotations,
  DocumentCursor,
  DocumentStatus,
} from './documents/documentsApi'
import { LegacyImportPanel } from './imports/LegacyImportPanel'
import { importLegacyArchive, previewLegacyImport } from './imports/importsApi'
import { isTauriRuntime, pickImportFolder } from './lib/desktopShell'
import { Brand } from './ui/Brand'

function Root() {
  const {
    status,
    user,
    authenticatedGet,
    authenticatedRequest,
    authenticatedUpload,
    authenticatedDownload,
    authenticatedOpenDocument,
    logout,
    retry,
  } = useAuth()
  const [logoutNotice, setLogoutNotice] = useState<string | null>(null)
  const [activeView, setActiveView] = useState<
    'overview' | 'audit' | 'clients' | 'imports' | 'communications'
  >('overview')
  const [documentsFolder, setDocumentsFolder] = useState<ClientFolder | null>(
    null,
  )
  const [contractsFolder, setContractsFolder] = useState<ClientFolder | null>(
    null,
  )

  const loadRecentActivity = useCallback(
    () => listRecentAuditEvents(authenticatedGet),
    [authenticatedGet],
  )

  const loadAuditPage = useCallback(
    (cursor: AuditCursor | null, filters: AuditFilters) =>
      listAuditEvents(authenticatedGet, { limit: 20, cursor, filters }),
    [authenticatedGet],
  )

  const loadClientsPage = useCallback(
    (cursor: ClientCursor | null, query: string | null) =>
      listClientFolders(authenticatedGet, { limit: 20, cursor, query }),
    [authenticatedGet],
  )

  const createClient = useCallback(
    (input: {
      display_name: string
      email: string | null
      profile_data: Record<string, string>
    }) => createClientFolder(authenticatedRequest, input),
    [authenticatedRequest],
  )

  const updateClient = useCallback(
    (
      id: string,
      input: {
        display_name: string
        email: string | null
        profile_data: Record<string, string>
      },
    ) => updateClientFolder(authenticatedRequest, id, input),
    [authenticatedRequest],
  )

  const contractsFolderId = contractsFolder?.id ?? null

  const loadContracts = useCallback(() => {
    if (contractsFolderId === null) {
      return Promise.reject(new Error('no client folder is open'))
    }
    return listClientContracts(authenticatedGet, contractsFolderId)
  }, [authenticatedGet, contractsFolderId])

  const createContract = useCallback(
    (input: CreateContractInput) => {
      if (contractsFolderId === null) {
        return Promise.reject(new Error('no client folder is open'))
      }
      return createClientContract(
        authenticatedRequest,
        contractsFolderId,
        input,
      )
    },
    [authenticatedRequest, contractsFolderId],
  )

  const recordContractPayment = useCallback(
    (
      contract: ClientContract,
      installment: ContractInstallment,
      paidOn: string,
    ) => {
      if (contractsFolderId === null) {
        return Promise.reject(new Error('no client folder is open'))
      }
      return recordInstallmentPayment(authenticatedRequest, {
        clientId: contractsFolderId,
        contractId: contract.id,
        installmentId: installment.id,
        paidOn,
      })
    },
    [authenticatedRequest, contractsFolderId],
  )

  const cancelContract = useCallback(
    (contract: ClientContract) => {
      if (contractsFolderId === null) {
        return Promise.reject(new Error('no client folder is open'))
      }
      return cancelClientContract(
        authenticatedRequest,
        contractsFolderId,
        contract.id,
      )
    },
    [authenticatedRequest, contractsFolderId],
  )

  const exportProfile = useCallback(
    (folder: ClientFolder) =>
      exportClientProfile(authenticatedDownload, folder.id),
    [authenticatedDownload],
  )

  const documentsFolderId = documentsFolder?.id ?? null

  const loadDocumentsPage = useCallback(
    (cursor: DocumentCursor | null) => {
      if (documentsFolderId === null) {
        return Promise.reject(new Error('no client folder is open'))
      }
      return listClientDocuments(authenticatedGet, {
        clientId: documentsFolderId,
        limit: 20,
        cursor,
      })
    },
    [authenticatedGet, documentsFolderId],
  )

  const attachDocument = useCallback(
    (input: { file: File; annotations: DocumentAnnotations }) => {
      if (documentsFolderId === null) {
        return Promise.reject(new Error('no client folder is open'))
      }
      return attachClientDocument(authenticatedUpload, {
        clientId: documentsFolderId,
        file: input.file,
        annotations: input.annotations,
      })
    },
    [authenticatedUpload, documentsFolderId],
  )

  const exportDocument = useCallback(
    (item: { id: string }) => {
      if (documentsFolderId === null) {
        return Promise.reject(new Error('no client folder is open'))
      }
      return exportClientDocument(authenticatedDownload, {
        clientId: documentsFolderId,
        documentId: item.id,
      })
    },
    [authenticatedDownload, documentsFolderId],
  )

  const openDocument = useCallback(
    async (item: ClientDocument) => {
      if (documentsFolderId === null) {
        throw new Error('no client folder is open')
      }
      return openClientDocument(authenticatedOpenDocument, {
        clientId: documentsFolderId,
        documentId: item.id,
        filename: item.original_filename,
      })
    },
    [authenticatedOpenDocument, documentsFolderId],
  )

  const updateDocumentStatus = useCallback(
    (item: ClientDocument, status: DocumentStatus | null) => {
      if (documentsFolderId === null) {
        return Promise.reject(new Error('no client folder is open'))
      }
      return updateClientDocumentStatus(authenticatedRequest, {
        clientId: documentsFolderId,
        documentId: item.id,
        status,
      })
    },
    [authenticatedRequest, documentsFolderId],
  )

  const previewImport = useCallback(
    (sourcePath: string) =>
      previewLegacyImport(authenticatedRequest, sourcePath),
    [authenticatedRequest],
  )

  const runImport = useCallback(
    (sourcePath: string) =>
      importLegacyArchive(authenticatedRequest, sourcePath),
    [authenticatedRequest],
  )

  const loadTemplates = useCallback(
    () => listMessageTemplates(authenticatedGet),
    [authenticatedGet],
  )

  const createTemplate = useCallback(
    (payload: MessageTemplatePayload) =>
      createMessageTemplate(authenticatedRequest, payload),
    [authenticatedRequest],
  )

  const updateTemplate = useCallback(
    (template: MessageTemplate, payload: MessageTemplatePayload) =>
      updateMessageTemplate(authenticatedRequest, template.id, payload),
    [authenticatedRequest],
  )

  const deleteTemplate = useCallback(
    (template: MessageTemplate) =>
      deleteMessageTemplate(authenticatedRequest, template.id),
    [authenticatedRequest],
  )

  const loadCandidates = useCallback(
    (
      documentStatus: RecipientDocumentStatus,
      cursor: RecipientCandidateCursor | null,
    ) =>
      listRecipientCandidates(authenticatedGet, {
        status: documentStatus,
        limit: 20,
        cursor,
      }),
    [authenticatedGet],
  )

  const goTo = useCallback(
    (view: 'overview' | 'audit' | 'clients' | 'imports' | 'communications') => {
      // Trocar de seção fecha a pasta aberta: os documentos pertencem ao cliente
      // que estava em tela, não à navegação seguinte.
      setDocumentsFolder(null)
      setContractsFolder(null)
      setActiveView(view)
    },
    [],
  )

  async function handleLogout() {
    setLogoutNotice(null)
    setActiveView('overview')
    setDocumentsFolder(null)
    setContractsFolder(null)
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
                onClick={() => goTo('overview')}
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
                onClick={() => goTo('audit')}
              >
                <span aria-hidden="true">◷</span>
                <span>Auditoria</span>
              </button>
            </li>
            <li>
              <button
                className={`workspace-nav__item${activeView === 'clients' ? ' workspace-nav__item--active' : ''}`}
                type="button"
                aria-current={activeView === 'clients' ? 'page' : undefined}
                onClick={() => goTo('clients')}
              >
                <span aria-hidden="true">◎</span>
                <span>Clientes</span>
              </button>
            </li>
            <li>
              <button
                className={`workspace-nav__item${activeView === 'imports' ? ' workspace-nav__item--active' : ''}`}
                type="button"
                aria-current={activeView === 'imports' ? 'page' : undefined}
                onClick={() => goTo('imports')}
              >
                <span aria-hidden="true">⇪</span>
                <span>Importar acervo</span>
              </button>
            </li>
            <li className="workspace-nav__item">
              <span aria-hidden="true">▤</span> Documentos{' '}
              <small>na pasta do cliente</small>
            </li>
            <li>
              <button
                className={`workspace-nav__item${activeView === 'communications' ? ' workspace-nav__item--active' : ''}`}
                type="button"
                aria-current={
                  activeView === 'communications' ? 'page' : undefined
                }
                onClick={() => goTo('communications')}
              >
                <span aria-hidden="true">✉</span>
                <span>E-mails</span>
                <small>preparação</small>
              </button>
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
          ) : activeView === 'imports' ? (
            <LegacyImportPanel
              previewImport={previewImport}
              runImport={runImport}
              onBack={() => setActiveView('overview')}
              pickFolder={isTauriRuntime() ? pickImportFolder : undefined}
            />
          ) : activeView === 'communications' ? (
            <CommunicationsPage
              loadTemplates={loadTemplates}
              createTemplate={createTemplate}
              updateTemplate={updateTemplate}
              deleteTemplate={deleteTemplate}
              loadCandidates={loadCandidates}
              onBack={() => setActiveView('overview')}
            />
          ) : activeView === 'clients' && contractsFolder !== null ? (
            <ContractsPanel
              folder={contractsFolder}
              loadContracts={loadContracts}
              createContract={createContract}
              recordPayment={recordContractPayment}
              cancelContract={cancelContract}
              onBack={() => setContractsFolder(null)}
            />
          ) : activeView === 'clients' && documentsFolder !== null ? (
            <ClientDocumentsPanel
              folder={documentsFolder}
              loadPage={loadDocumentsPage}
              attachDocument={attachDocument}
              exportDocument={exportDocument}
              openDocument={openDocument}
              updateStatus={updateDocumentStatus}
              onBack={() => setDocumentsFolder(null)}
            />
          ) : activeView === 'clients' ? (
            <ClientsPage
              loadPage={loadClientsPage}
              createFolder={createClient}
              updateFolder={updateClient}
              onOpenDocuments={(folder) => {
                setContractsFolder(null)
                setDocumentsFolder(folder)
              }}
              onOpenContracts={(folder) => {
                setDocumentsFolder(null)
                setContractsFolder(folder)
              }}
              exportProfile={exportProfile}
            />
          ) : (
            <>
              <section className="welcome-panel">
                <div>
                  <p className="eyebrow">Visão geral</p>
                  <h1>Bem-vindo, {user.full_name}</h1>
                  <p>
                    Clientes, documentos, contratos e modelos já estão
                    disponíveis. O envio de e-mails aguarda a configuração
                    segura do remetente.
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
                  <span>4 completos · 1 em preparação</span>
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
                      'Disponível',
                    ],
                    [
                      '03',
                      'Documentos',
                      'PDFs e fotos JPEG por cliente.',
                      'Disponível',
                    ],
                    [
                      '04',
                      'Contratos',
                      'Parcelas, vencimentos e pagamentos.',
                      'Disponível',
                    ],
                    [
                      '05',
                      'Comunicação',
                      'Modelos e triagem; envio aguarda remetente.',
                      'Preparação disponível',
                    ],
                  ].map(([number, title, description, state], index) => (
                    <article
                      className={`module-card${index <= 4 ? ' module-card--ready' : ''}`}
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

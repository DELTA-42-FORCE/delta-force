import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'

import {
  describeCandidateFailure,
  describeTemplateFailure,
} from './communicationMessages'
import { ApiError } from '../lib/apiClient'
import type {
  MessageTemplate,
  MessageTemplatePayload,
  EmailDispatch,
  EmailSenderSettings,
  RecipientCandidate,
  RecipientCandidateCursor,
  RecipientCandidatePage,
  RecipientDocumentStatus,
} from './communicationsApi'

interface CommunicationsPageProps {
  loadTemplates: () => Promise<MessageTemplate[]>
  createTemplate: (payload: MessageTemplatePayload) => Promise<MessageTemplate>
  updateTemplate: (
    template: MessageTemplate,
    payload: MessageTemplatePayload,
  ) => Promise<MessageTemplate>
  deleteTemplate: (template: MessageTemplate) => Promise<void>
  loadCandidates: (
    status: RecipientDocumentStatus,
    cursor: RecipientCandidateCursor | null,
  ) => Promise<RecipientCandidatePage>
  loadSenderSettings: () => Promise<EmailSenderSettings>
  saveSenderSettings: (
    settings: EmailSenderSettings,
  ) => Promise<EmailSenderSettings>
  sendBatch: (input: {
    template_id: string
    client_ids: string[]
    credential: string | null
    confirm_repeat: boolean
  }) => Promise<EmailDispatch[]>
  loadDispatches: () => Promise<EmailDispatch[]>
  onBack: () => void
}

type EditorState =
  | { mode: 'closed' }
  | { mode: 'create' }
  | { mode: 'edit'; template: MessageTemplate }

const DATE_FORMATTER = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
})

const DELIVERY_STATUS_LABELS: Record<EmailDispatch['status'], string> = {
  pending: 'Envio em andamento',
  sent: 'Aceito pelo provedor',
  rejected: 'Rejeitado pelo provedor',
  unknown: 'Resultado desconhecido',
  skipped_duplicate: 'Reenvio não realizado',
  missing_email: 'Cliente sem e-mail',
}

function formatUpdatedAt(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.valueOf())
    ? 'Atualização indisponível'
    : `Atualizado em ${DATE_FORMATTER.format(date)}`
}

function CandidateList({
  items,
  selected,
  onToggle,
}: {
  items: RecipientCandidate[]
  selected: Set<string>
  onToggle: (clientId: string) => void
}) {
  return (
    <ul className="recipient-list">
      {items.map((candidate) => (
        <li className="recipient-list__item" key={candidate.client_id}>
          <input
            type="checkbox"
            aria-label={`Selecionar ${candidate.display_name}`}
            checked={selected.has(candidate.client_id)}
            onChange={() => onToggle(candidate.client_id)}
          />
          <div>
            <strong>{candidate.display_name}</strong>
            <small>
              {candidate.matching_documents}{' '}
              {candidate.matching_documents === 1
                ? 'documento nesta situação'
                : 'documentos nesta situação'}
            </small>
          </div>
          <span
            className={`document-state document-state--${candidate.document_status}`}
          >
            {candidate.document_status === 'pending' ? 'Pendente' : 'Incorreto'}
          </span>
        </li>
      ))}
    </ul>
  )
}

export function CommunicationsPage({
  loadTemplates,
  createTemplate,
  updateTemplate,
  deleteTemplate,
  loadCandidates,
  loadSenderSettings,
  saveSenderSettings,
  sendBatch,
  loadDispatches,
  onBack,
}: CommunicationsPageProps) {
  const [templates, setTemplates] = useState<MessageTemplate[]>([])
  const [templatesState, setTemplatesState] = useState<
    'loading' | 'ready' | 'error'
  >('loading')
  const [templateSequence, setTemplateSequence] = useState(0)
  const [editor, setEditor] = useState<EditorState>({ mode: 'closed' })
  const [name, setName] = useState('')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [saveState, setSaveState] = useState<'idle' | 'saving'>('idle')
  const [templateError, setTemplateError] = useState<string | null>(null)
  const [templateNotice, setTemplateNotice] = useState<string | null>(null)
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const templatesRequestRef = useRef<{
    sequence: number
    request: Promise<MessageTemplate[]>
  } | null>(null)

  const [candidateStatus, setCandidateStatus] =
    useState<RecipientDocumentStatus>('pending')
  const [candidates, setCandidates] = useState<RecipientCandidate[]>([])
  const [candidateCursor, setCandidateCursor] =
    useState<RecipientCandidateCursor | null>(null)
  const [candidateState, setCandidateState] = useState<
    'loading' | 'ready' | 'error'
  >('loading')
  const [candidateError, setCandidateError] = useState<string | null>(null)
  const [candidateMoreState, setCandidateMoreState] = useState<
    'idle' | 'loading' | 'error'
  >('idle')
  const [candidateSequence, setCandidateSequence] = useState(0)
  const candidateGenerationRef = useRef(0)
  const candidateRequestRef = useRef<{
    key: string
    request: Promise<RecipientCandidatePage>
  } | null>(null)
  const [selectedClients, setSelectedClients] = useState<Set<string>>(new Set())
  const [selectedTemplateId, setSelectedTemplateId] = useState('')
  const [credential, setCredential] = useState('')
  const [showCredential, setShowCredential] = useState(false)
  const [confirmRepeat, setConfirmRepeat] = useState(false)
  const [sendConfirmationPending, setSendConfirmationPending] = useState(false)
  const [sendState, setSendState] = useState<'idle' | 'sending'>('idle')
  const [sendNotice, setSendNotice] = useState<string | null>(null)
  const [sendError, setSendError] = useState<string | null>(null)
  const [dispatches, setDispatches] = useState<EmailDispatch[]>([])
  const [historyState, setHistoryState] = useState<
    'loading' | 'ready' | 'error'
  >('loading')
  const [senderState, setSenderState] = useState<
    'loading' | 'unconfigured' | 'ready' | 'saving' | 'error'
  >('loading')
  const [senderError, setSenderError] = useState<string | null>(null)
  const [senderSettings, setSenderSettings] = useState<EmailSenderSettings>({
    sender_name: '',
    sender_email: '',
    smtp_host: '',
    smtp_port: 587,
    security: 'starttls',
    username: null,
    max_recipients: 50,
  })

  useEffect(() => {
    let active = true
    const cachedRequest = templatesRequestRef.current
    const request =
      cachedRequest?.sequence === templateSequence
        ? cachedRequest.request
        : loadTemplates()
    templatesRequestRef.current = { sequence: templateSequence, request }

    void request
      .then((items) => {
        if (!active) return
        setTemplates(items)
        setTemplatesState('ready')
      })
      .catch((error: unknown) => {
        if (!active) return
        setTemplateError(describeTemplateFailure(error, 'load'))
        setTemplatesState('error')
      })

    return () => {
      active = false
    }
  }, [loadTemplates, templateSequence])

  useEffect(() => {
    let active = true
    const requestKey = `${candidateStatus}:${candidateSequence}`
    const cachedRequest = candidateRequestRef.current
    const request =
      cachedRequest?.key === requestKey
        ? cachedRequest.request
        : loadCandidates(candidateStatus, null)
    candidateRequestRef.current = { key: requestKey, request }

    void request
      .then((page) => {
        if (!active) return
        setCandidates(page.items)
        setCandidateCursor(page.nextCursor)
        setCandidateState('ready')
      })
      .catch((error: unknown) => {
        if (!active) return
        setCandidateError(describeCandidateFailure(error))
        setCandidateState('error')
      })

    return () => {
      active = false
    }
  }, [candidateSequence, candidateStatus, loadCandidates])

  useEffect(() => {
    let active = true
    void loadSenderSettings()
      .then((settings) => {
        if (!active) return
        setSenderSettings(settings)
        setSenderState('ready')
      })
      .catch((error: unknown) => {
        if (!active) return
        if (error instanceof ApiError && error.status === 404) {
          setSenderState('unconfigured')
          return
        }
        setSenderError(
          'Não foi possível consultar a configuração do remetente.',
        )
        setSenderState('error')
      })
    void loadDispatches()
      .then((items) => {
        if (!active) return
        setDispatches(items)
        setHistoryState('ready')
      })
      .catch(() => {
        if (active) setHistoryState('error')
      })
    return () => {
      active = false
    }
  }, [loadDispatches, loadSenderSettings])

  const refreshTemplates = useCallback(() => {
    templatesRequestRef.current = null
    setTemplateError(null)
    setTemplatesState('loading')
    setTemplateSequence((current) => current + 1)
  }, [])

  const resetCandidates = useCallback(() => {
    candidateGenerationRef.current += 1
    candidateRequestRef.current = null
    setCandidates([])
    setCandidateCursor(null)
    setCandidateMoreState('idle')
    setCandidateError(null)
    setCandidateState('loading')
    setCandidateSequence((current) => current + 1)
  }, [])

  function openCreateEditor() {
    setName('')
    setSubject('')
    setBody('')
    setTemplateError(null)
    setTemplateNotice(null)
    setPendingDeleteId(null)
    setEditor({ mode: 'create' })
  }

  function openEditEditor(template: MessageTemplate) {
    setName(template.name)
    setSubject(template.subject)
    setBody(template.body)
    setTemplateError(null)
    setTemplateNotice(null)
    setPendingDeleteId(null)
    setEditor({ mode: 'edit', template })
  }

  function closeEditor() {
    setTemplateError(null)
    setEditor({ mode: 'closed' })
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setTemplateError(null)
    setTemplateNotice(null)
    const payload = {
      name: name.trim(),
      subject: subject.trim(),
      body: body.trim(),
    }
    if (!payload.name || !payload.subject || !payload.body) {
      setTemplateError('Preencha o nome, o assunto e o conteúdo do modelo.')
      return
    }

    setSaveState('saving')
    try {
      if (editor.mode === 'edit') {
        const updated = await updateTemplate(editor.template, payload)
        setTemplates((current) =>
          current.map((template) =>
            template.id === updated.id ? updated : template,
          ),
        )
        setTemplateNotice(`Modelo “${updated.name}” atualizado.`)
      } else {
        const created = await createTemplate(payload)
        setTemplates((current) => [created, ...current])
        setTemplateNotice(`Modelo “${created.name}” criado.`)
      }
      setEditor({ mode: 'closed' })
      setSendConfirmationPending(false)
      setTemplatesState('ready')
    } catch (error) {
      setTemplateError(describeTemplateFailure(error, 'save'))
    } finally {
      setSaveState('idle')
    }
  }

  async function handleDelete(template: MessageTemplate) {
    setTemplateError(null)
    setTemplateNotice(null)
    setDeletingId(template.id)
    try {
      await deleteTemplate(template)
      setTemplates((current) =>
        current.filter((item) => item.id !== template.id),
      )
      setPendingDeleteId(null)
      setSendConfirmationPending(false)
      setTemplateNotice(`Modelo “${template.name}” removido.`)
    } catch (error) {
      setTemplateError(describeTemplateFailure(error, 'delete'))
    } finally {
      setDeletingId(null)
    }
  }

  function changeCandidateStatus(status: RecipientDocumentStatus) {
    if (status === candidateStatus) return
    candidateGenerationRef.current += 1
    candidateRequestRef.current = null
    setCandidates([])
    setCandidateCursor(null)
    setCandidateMoreState('idle')
    setCandidateError(null)
    setSelectedClients(new Set())
    setSendConfirmationPending(false)
    setCandidateState('loading')
    setCandidateStatus(status)
  }

  function toggleCandidate(clientId: string) {
    setSendConfirmationPending(false)
    setSelectedClients((current) => {
      const next = new Set(current)
      if (next.has(clientId)) next.delete(clientId)
      else next.add(clientId)
      return next
    })
  }

  async function handleSaveSender(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSenderError(null)
    if (
      !senderSettings.sender_name.trim() ||
      !senderSettings.sender_email.trim() ||
      !senderSettings.smtp_host.trim() ||
      !Number.isInteger(senderSettings.smtp_port) ||
      senderSettings.smtp_port < 1 ||
      senderSettings.smtp_port > 65535 ||
      !Number.isInteger(senderSettings.max_recipients) ||
      senderSettings.max_recipients < 1 ||
      senderSettings.max_recipients > 100
    ) {
      setSenderError(
        'Revise os dados do remetente, a porta e o limite do lote.',
      )
      return
    }
    setSenderState('saving')
    try {
      const saved = await saveSenderSettings(senderSettings)
      setSenderSettings(saved)
      setSendConfirmationPending(false)
      setSenderState('ready')
    } catch {
      setSenderError('Não foi possível salvar a configuração do remetente.')
      setSenderState('error')
    }
  }

  async function handleSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSendError(null)
    setSendNotice(null)
    if (!selectedTemplateId || selectedClients.size === 0) {
      setSendError('Escolha um modelo e pelo menos um cliente.')
      return
    }
    if (senderSettings.username && !credential) {
      setSendError('Informe a senha ou senha de aplicativo desta sessão.')
      return
    }
    if (!sendConfirmationPending) {
      setSendConfirmationPending(true)
      return
    }
    setSendState('sending')
    try {
      const results = await sendBatch({
        template_id: selectedTemplateId,
        client_ids: [...selectedClients],
        credential: credential || null,
        confirm_repeat: confirmRepeat,
      })
      const sent = results.filter((item) => item.status === 'sent').length
      const unknown = results.filter((item) => item.status === 'unknown').length
      const rejected = results.filter(
        (item) => item.status === 'rejected',
      ).length
      const missing = results.filter(
        (item) => item.status === 'missing_email',
      ).length
      setSendNotice(
        `${sent} aceita(s), ${rejected} rejeitada(s), ${unknown} com resultado desconhecido e ${missing} sem e-mail.`,
      )
      setCredential('')
      setConfirmRepeat(false)
      setSendConfirmationPending(false)
      try {
        const history = await loadDispatches()
        setDispatches(history)
        setHistoryState('ready')
      } catch {
        // O envio externo já ocorreu. Falhar ao atualizar a tela não pode ser
        // apresentado como falha de envio, pois isso incentivaria duplicidade.
        setHistoryState('error')
      }
    } catch (error) {
      if (
        error instanceof ApiError &&
        error.status === 409 &&
        error.message === 'repeat confirmation required'
      ) {
        setSendError(
          'Há destinatários com envio confirmado, resultado desconhecido ou tentativa em andamento. Marque a confirmação de reenvio para assumir o risco de duplicidade.',
        )
      } else {
        setSendError(
          'Não foi possível concluir o envio. Revise a configuração.',
        )
      }
    } finally {
      setSendState('idle')
    }
  }

  async function retryDispatchHistory() {
    setHistoryState('loading')
    try {
      setDispatches(await loadDispatches())
      setHistoryState('ready')
    } catch {
      setHistoryState('error')
    }
  }

  async function loadMoreCandidates() {
    if (candidateCursor === null || candidateMoreState === 'loading') return
    const requestGeneration = candidateGenerationRef.current
    setCandidateMoreState('loading')
    try {
      const page = await loadCandidates(candidateStatus, candidateCursor)
      if (candidateGenerationRef.current !== requestGeneration) return
      setCandidates((current) => [...current, ...page.items])
      setCandidateCursor(page.nextCursor)
      setCandidateMoreState('idle')
    } catch {
      if (candidateGenerationRef.current !== requestGeneration) return
      setCandidateMoreState('error')
    }
  }

  const editing = editor.mode !== 'closed'

  return (
    <section
      className="communications-page"
      aria-labelledby="communications-title"
    >
      <button
        className="text-button communications-page__back"
        type="button"
        onClick={onBack}
      >
        ← Voltar para visão geral
      </button>

      <div className="communications-page__heading">
        <div>
          <p className="eyebrow">Comunicações</p>
          <h1 id="communications-title">Preparação de e-mails</h1>
          <p>
            Mantenha textos reutilizáveis, selecione clientes por situação
            documental e acompanhe cada envio.
          </p>
        </div>
        <span className="status-pill status-pill--waiting">
          <span aria-hidden="true">●</span>{' '}
          {senderState === 'ready'
            ? 'Envio configurado'
            : 'Configure o remetente'}
        </span>
      </div>

      <ol
        className="communication-readiness"
        aria-label="Etapas da comunicação"
      >
        <li className="communication-readiness__step communication-readiness__step--active">
          <span>01</span>
          <div>
            <strong>Modelos</strong>
            <small>Disponível</small>
          </div>
        </li>
        <li className="communication-readiness__step communication-readiness__step--active">
          <span>02</span>
          <div>
            <strong>Triagem documental</strong>
            <small>Disponível</small>
          </div>
        </li>
        <li
          className={`communication-readiness__step${senderState === 'ready' ? ' communication-readiness__step--active' : ''}`}
        >
          <span>03</span>
          <div>
            <strong>Envio e histórico</strong>
            <small>
              {senderState === 'ready'
                ? 'Disponível'
                : 'Configuração necessária'}
            </small>
          </div>
        </li>
      </ol>

      <div className="communication-workspace">
        <form
          className="communication-card"
          aria-labelledby="sender-settings-title"
          onSubmit={handleSaveSender}
          noValidate
        >
          <div className="communication-card__heading">
            <div>
              <p className="eyebrow">Remetente</p>
              <h2 id="sender-settings-title">Configuração SMTP</h2>
              <p>A senha não é salva; ela será pedida somente no envio.</p>
            </div>
          </div>
          <div className="message-template-form__field">
            <label htmlFor="sender-name">Nome do remetente</label>
            <input
              id="sender-name"
              required
              value={senderSettings.sender_name}
              onChange={(event) =>
                setSenderSettings((current) => ({
                  ...current,
                  sender_name: event.target.value,
                }))
              }
            />
          </div>
          <div className="message-template-form__field">
            <label htmlFor="sender-email">E-mail do remetente</label>
            <input
              id="sender-email"
              type="email"
              required
              value={senderSettings.sender_email}
              onChange={(event) =>
                setSenderSettings((current) => ({
                  ...current,
                  sender_email: event.target.value,
                }))
              }
            />
          </div>
          <div className="message-template-form__field">
            <label htmlFor="smtp-host">Servidor SMTP</label>
            <input
              id="smtp-host"
              required
              placeholder="smtp.exemplo.com"
              value={senderSettings.smtp_host}
              onChange={(event) =>
                setSenderSettings((current) => ({
                  ...current,
                  smtp_host: event.target.value,
                }))
              }
            />
          </div>
          <div className="message-template-form__field">
            <label htmlFor="smtp-port">Porta</label>
            <input
              id="smtp-port"
              type="number"
              min={1}
              max={65535}
              required
              value={senderSettings.smtp_port}
              onChange={(event) =>
                setSenderSettings((current) => ({
                  ...current,
                  smtp_port: Number(event.target.value),
                }))
              }
            />
          </div>
          <div className="message-template-form__field">
            <label htmlFor="smtp-security">Segurança</label>
            <select
              id="smtp-security"
              value={senderSettings.security}
              onChange={(event) =>
                setSenderSettings((current) => ({
                  ...current,
                  security: event.target
                    .value as EmailSenderSettings['security'],
                }))
              }
            >
              <option value="starttls">STARTTLS</option>
              <option value="tls">TLS direto</option>
            </select>
          </div>
          <div className="message-template-form__field">
            <label htmlFor="smtp-username">Usuário SMTP (opcional)</label>
            <input
              id="smtp-username"
              value={senderSettings.username ?? ''}
              autoComplete="username"
              onChange={(event) =>
                setSenderSettings((current) => ({
                  ...current,
                  username: event.target.value || null,
                }))
              }
            />
          </div>
          <div className="message-template-form__field">
            <label htmlFor="smtp-max-recipients">
              Máximo de destinatários por lote
            </label>
            <input
              id="smtp-max-recipients"
              type="number"
              min={1}
              max={100}
              value={senderSettings.max_recipients}
              onChange={(event) =>
                setSenderSettings((current) => ({
                  ...current,
                  max_recipients: Number(event.target.value),
                }))
              }
            />
          </div>
          {senderError !== null && <p role="alert">{senderError}</p>}
          <button
            className="primary-button compact-button"
            type="submit"
            disabled={senderState === 'saving'}
          >
            {senderState === 'saving' ? 'Salvando…' : 'Salvar configuração'}
          </button>
        </form>

        <form
          className="communication-card"
          aria-labelledby="batch-send-title"
          onSubmit={handleSend}
          noValidate
        >
          <div className="communication-card__heading">
            <div>
              <p className="eyebrow">Disparo</p>
              <h2 id="batch-send-title">Enviar selecionados</h2>
              <p>O envio é individual e o resultado fica no histórico.</p>
            </div>
          </div>
          <div className="message-template-form__field">
            <label htmlFor="send-template">Modelo</label>
            <select
              id="send-template"
              value={selectedTemplateId}
              onChange={(event) => {
                setSelectedTemplateId(event.target.value)
                setSendConfirmationPending(false)
              }}
            >
              <option value="">Selecione um modelo</option>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
          </div>
          <div className="message-template-form__field">
            <label htmlFor="smtp-credential">
              Senha ou senha de aplicativo
            </label>
            <div className="password-input">
              <input
                id="smtp-credential"
                type={showCredential ? 'text' : 'password'}
                autoComplete="current-password"
                value={credential}
                onChange={(event) => setCredential(event.target.value)}
              />
              <button
                className="text-button"
                type="button"
                aria-pressed={showCredential}
                onClick={() => setShowCredential((current) => !current)}
              >
                {showCredential ? 'Ocultar' : 'Mostrar'}
              </button>
            </div>
          </div>
          <label>
            <input
              type="checkbox"
              checked={confirmRepeat}
              onChange={(event) => {
                setConfirmRepeat(event.target.checked)
                setSendConfirmationPending(false)
              }}
            />{' '}
            Confirmo o reenvio mesmo quando houver entrega confirmada, resultado
            desconhecido ou tentativa ainda pendente
          </label>
          <p>{selectedClients.size} cliente(s) selecionado(s).</p>
          {sendConfirmationPending && (
            <div className="feedback feedback--warning" role="status">
              Revise o modelo e os {selectedClients.size} destinatário(s). O
              próximo clique iniciará um envio externo que não pode ser
              desfeito.
            </div>
          )}
          {sendError !== null && <p role="alert">{sendError}</p>}
          {sendNotice !== null && <p role="status">{sendNotice}</p>}
          <button
            className="primary-button compact-button"
            type="submit"
            disabled={senderState !== 'ready' || sendState === 'sending'}
          >
            {sendState === 'sending'
              ? 'Enviando…'
              : sendConfirmationPending
                ? 'Confirmar e enviar'
                : 'Revisar envio'}
          </button>
        </form>
      </div>

      <div className="communication-workspace">
        <section
          className="communication-card communication-card--templates"
          aria-labelledby="templates-title"
        >
          <div className="communication-card__heading">
            <div>
              <p className="eyebrow">Biblioteca</p>
              <h2 id="templates-title">Modelos de e-mail</h2>
              <p>Textos salvos para preparar comunicações futuras.</p>
            </div>
            {!editing && (
              <button
                className="primary-button compact-button"
                type="button"
                onClick={openCreateEditor}
              >
                Novo modelo
              </button>
            )}
          </div>

          {templateNotice !== null && (
            <p className="feedback feedback--success" role="status">
              {templateNotice}
            </p>
          )}
          {templateError !== null && (
            <p className="feedback feedback--error" role="alert">
              {templateError}
            </p>
          )}

          {editing && (
            <form
              className="message-template-form"
              onSubmit={handleSave}
              noValidate
            >
              <div className="message-template-form__title">
                <div>
                  <p className="eyebrow">
                    {editor.mode === 'create' ? 'Novo modelo' : 'Edição'}
                  </p>
                  <h3>
                    {editor.mode === 'create'
                      ? 'Criar texto reutilizável'
                      : editor.template.name}
                  </h3>
                </div>
                <span>Texto estático</span>
              </div>

              <div className="message-template-form__field">
                <label htmlFor="message-template-name">Nome do modelo</label>
                <input
                  id="message-template-name"
                  value={name}
                  maxLength={120}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Ex.: Pendência documental"
                />
                <small aria-hidden="true">{name.length}/120</small>
              </div>

              <div className="message-template-form__field">
                <label htmlFor="message-template-subject">Assunto</label>
                <input
                  id="message-template-subject"
                  value={subject}
                  maxLength={200}
                  onChange={(event) => setSubject(event.target.value)}
                  placeholder="Assunto que será revisado antes do envio"
                />
                <small aria-hidden="true">{subject.length}/200</small>
              </div>

              <div className="message-template-form__field">
                <label htmlFor="message-template-body">Conteúdo</label>
                <textarea
                  id="message-template-body"
                  className="resize-none"
                  value={body}
                  maxLength={20_000}
                  rows={10}
                  onChange={(event) => setBody(event.target.value)}
                  placeholder="Escreva o conteúdo do modelo"
                />
                <small aria-hidden="true">{body.length}/20.000</small>
              </div>

              <p className="message-template-form__note">
                Use {'{{nome}}'} para inserir o nome do cliente. Outras
                variáveis não são aceitas nesta versão.
              </p>

              <div className="message-template-form__actions">
                <button
                  className="secondary-button"
                  type="button"
                  disabled={saveState === 'saving'}
                  onClick={closeEditor}
                >
                  Cancelar
                </button>
                <button
                  className="primary-button compact-button"
                  type="submit"
                  disabled={saveState === 'saving'}
                >
                  {saveState === 'saving' ? 'Salvando…' : 'Salvar modelo'}
                </button>
              </div>
            </form>
          )}

          {!editing && templatesState === 'loading' && (
            <div className="activity-state" aria-busy="true">
              <span className="loader" aria-hidden="true" />
              <p>Carregando modelos…</p>
            </div>
          )}

          {!editing && templatesState === 'error' && (
            <div className="activity-state">
              <button
                className="secondary-button"
                type="button"
                onClick={refreshTemplates}
              >
                Tentar novamente
              </button>
            </div>
          )}

          {!editing && templatesState === 'ready' && templates.length === 0 && (
            <div className="activity-state communication-empty-state">
              <span className="activity-state__icon" aria-hidden="true">
                ✉
              </span>
              <div>
                <strong>Nenhum modelo criado</strong>
                <p>Crie o primeiro texto que poderá ser reutilizado depois.</p>
              </div>
            </div>
          )}

          {!editing && templatesState === 'ready' && templates.length > 0 && (
            <ul className="message-template-list">
              {templates.map((template) => (
                <li className="message-template-list__item" key={template.id}>
                  <div className="message-template-list__identity">
                    <span aria-hidden="true">✉</span>
                    <div>
                      <strong>{template.name}</strong>
                      <small>{formatUpdatedAt(template.updated_at)}</small>
                    </div>
                  </div>
                  <p className="message-template-list__subject">
                    {template.subject}
                  </p>
                  <p className="message-template-list__preview">
                    {template.body}
                  </p>
                  {pendingDeleteId === template.id ? (
                    <div className="message-template-list__confirmation">
                      <p>
                        Remover este modelo? Esta ação não pode ser desfeita.
                      </p>
                      <div>
                        <button
                          className="text-button"
                          type="button"
                          disabled={deletingId !== null}
                          onClick={() => setPendingDeleteId(null)}
                        >
                          Cancelar
                        </button>
                        <button
                          className="text-button text-button--danger"
                          type="button"
                          disabled={deletingId !== null}
                          onClick={() => void handleDelete(template)}
                        >
                          {deletingId === template.id
                            ? 'Removendo…'
                            : 'Remover'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="message-template-list__actions">
                      <button
                        className="text-button"
                        type="button"
                        onClick={() => openEditEditor(template)}
                      >
                        Editar
                      </button>
                      <button
                        className="text-button text-button--danger"
                        type="button"
                        onClick={() => setPendingDeleteId(template.id)}
                      >
                        Excluir
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <aside
          className="communication-card communication-card--recipients"
          aria-labelledby="recipients-title"
        >
          <div className="communication-card__heading">
            <div>
              <p className="eyebrow">Triagem</p>
              <h2 id="recipients-title">Clientes para revisar</h2>
              <p>Somente nome e quantidade de documentos são exibidos.</p>
            </div>
            {candidateState === 'ready' && (
              <span className="candidate-count">
                {candidates.length}{' '}
                {candidates.length === 1 ? 'exibido' : 'exibidos'}
              </span>
            )}
          </div>

          <div className="candidate-filter" aria-label="Situação documental">
            <button
              type="button"
              aria-pressed={candidateStatus === 'pending'}
              onClick={() => changeCandidateStatus('pending')}
            >
              Pendentes
            </button>
            <button
              type="button"
              aria-pressed={candidateStatus === 'incorrect_incomplete'}
              onClick={() => changeCandidateStatus('incorrect_incomplete')}
            >
              Incorretos ou incompletos
            </button>
          </div>

          {candidateState === 'loading' && (
            <div className="activity-state" aria-busy="true">
              <span className="loader" aria-hidden="true" />
              <p>Consultando clientes…</p>
            </div>
          )}

          {candidateState === 'error' && (
            <div className="activity-state">
              <p role="alert">{candidateError}</p>
              <button
                className="secondary-button"
                type="button"
                onClick={resetCandidates}
              >
                Tentar novamente
              </button>
            </div>
          )}

          {candidateState === 'ready' && candidates.length === 0 && (
            <div className="activity-state communication-empty-state">
              <span className="activity-state__icon" aria-hidden="true">
                ✓
              </span>
              <div>
                <strong>Nenhum cliente nesta situação</strong>
                <p>A triagem documental está em dia para este filtro.</p>
              </div>
            </div>
          )}

          {candidateState === 'ready' && candidates.length > 0 && (
            <>
              <CandidateList
                items={candidates}
                selected={selectedClients}
                onToggle={toggleCandidate}
              />
              {(candidateCursor !== null || candidateMoreState === 'error') && (
                <div className="candidate-more">
                  {candidateMoreState === 'error' && (
                    <p role="alert">Não foi possível carregar mais clientes.</p>
                  )}
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={candidateMoreState === 'loading'}
                    onClick={() => void loadMoreCandidates()}
                  >
                    {candidateMoreState === 'loading'
                      ? 'Carregando…'
                      : candidateMoreState === 'error'
                        ? 'Tentar novamente'
                        : 'Carregar mais'}
                  </button>
                </div>
              )}
            </>
          )}

          <div className="communication-lock-note">
            <span aria-hidden="true">◇</span>
            <p>
              <strong>Privacidade preservada</strong>
              Endereços de e-mail não aparecem nesta lista e nenhum disparo é
              realizado sem a configuração segura do remetente.
            </p>
          </div>
        </aside>
      </div>

      <section
        className="communication-card"
        aria-labelledby="dispatch-history-title"
      >
        <div className="communication-card__heading">
          <div>
            <p className="eyebrow">Rastreabilidade</p>
            <h2 id="dispatch-history-title">Histórico de envios</h2>
          </div>
        </div>
        {historyState === 'loading' ? (
          <div className="activity-state" aria-busy="true">
            <span className="loader" aria-hidden="true" />
            <p>Carregando histórico…</p>
          </div>
        ) : historyState === 'error' ? (
          <div className="activity-state">
            <p role="alert">Não foi possível consultar o histórico.</p>
            <button
              className="secondary-button"
              type="button"
              onClick={() => void retryDispatchHistory()}
            >
              Tentar novamente
            </button>
          </div>
        ) : dispatches.length === 0 ? (
          <p>Nenhum envio registrado.</p>
        ) : (
          <ul className="message-template-list">
            {dispatches.map((dispatch) => (
              <li className="message-template-list__item" key={dispatch.id}>
                <strong>{dispatch.subject}</strong>
                <span>{dispatch.recipient_email ?? 'Cliente sem e-mail'}</span>
                <small>{DELIVERY_STATUS_LABELS[dispatch.status]}</small>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  )
}

import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'

import {
  describeCandidateFailure,
  describeTemplateFailure,
} from './communicationMessages'
import type {
  MessageTemplate,
  MessageTemplatePayload,
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

function formatUpdatedAt(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.valueOf())
    ? 'Atualização indisponível'
    : `Atualizado em ${DATE_FORMATTER.format(date)}`
}

function CandidateList({ items }: { items: RecipientCandidate[] }) {
  return (
    <ul className="recipient-list">
      {items.map((candidate) => (
        <li className="recipient-list__item" key={candidate.client_id}>
          <span className="recipient-list__marker" aria-hidden="true" />
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
    setCandidateState('loading')
    setCandidateStatus(status)
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
            Mantenha textos reutilizáveis e consulte clientes por situação
            documental. Nenhuma mensagem é enviada nesta etapa.
          </p>
        </div>
        <span className="status-pill status-pill--waiting">
          <span aria-hidden="true">●</span> Envio desativado
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
        <li className="communication-readiness__step">
          <span>03</span>
          <div>
            <strong>Envio e histórico</strong>
            <small>Aguardando remetente</small>
          </div>
        </li>
      </ol>

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
              <CandidateList items={candidates} />
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
    </section>
  )
}

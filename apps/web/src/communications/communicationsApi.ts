import type { DocumentStatus } from '../documents/documentsApi'

export interface MessageTemplate {
  id: string
  name: string
  subject: string
  body: string
  created_at: string
  updated_at: string
}

export interface MessageTemplatePayload {
  name: string
  subject: string
  body: string
}

export type RecipientDocumentStatus = Extract<
  DocumentStatus,
  'pending' | 'incorrect_incomplete'
>

export interface RecipientCandidate {
  client_id: string
  display_name: string
  document_status: RecipientDocumentStatus
  matching_documents: number
}

export interface RecipientCandidateCursor {
  display_name: string
  client_id: string
}

export interface RecipientCandidatePage {
  items: RecipientCandidate[]
  nextCursor: RecipientCandidateCursor | null
}

export type SmtpSecurity = 'starttls' | 'tls' | 'none_dev'

export interface EmailSenderSettings {
  sender_name: string
  sender_email: string
  smtp_host: string
  smtp_port: number
  security: SmtpSecurity
  username: string | null
  max_recipients: number
}

export type EmailDeliveryStatus =
  | 'pending'
  | 'sent'
  | 'rejected'
  | 'unknown'
  | 'skipped_duplicate'
  | 'missing_email'

export interface EmailDispatch {
  id: string
  template_id: string
  client_id: string
  recipient_email: string | null
  subject: string
  body: string
  message_id: string
  status: EmailDeliveryStatus
  detail: string | null
  retry_of: string | null
  attempted_at: string
}

interface RecipientCandidateListResponse {
  items: RecipientCandidate[]
  next_cursor: RecipientCandidateCursor | null
}

type AuthenticatedGet = <T>(path: string) => Promise<T>
type AuthenticatedRequest = <T>(
  path: string,
  options: { method: string; body?: unknown },
) => Promise<T>

export function listMessageTemplates(
  authenticatedGet: AuthenticatedGet,
): Promise<MessageTemplate[]> {
  return authenticatedGet<MessageTemplate[]>('/message-templates')
}

export function createMessageTemplate(
  authenticatedRequest: AuthenticatedRequest,
  payload: MessageTemplatePayload,
): Promise<MessageTemplate> {
  return authenticatedRequest<MessageTemplate>('/message-templates', {
    method: 'POST',
    body: payload,
  })
}

export function updateMessageTemplate(
  authenticatedRequest: AuthenticatedRequest,
  templateId: string,
  payload: MessageTemplatePayload,
): Promise<MessageTemplate> {
  return authenticatedRequest<MessageTemplate>(
    `/message-templates/${templateId}`,
    { method: 'PUT', body: payload },
  )
}

export function deleteMessageTemplate(
  authenticatedRequest: AuthenticatedRequest,
  templateId: string,
): Promise<void> {
  return authenticatedRequest<void>(`/message-templates/${templateId}`, {
    method: 'DELETE',
  })
}

export async function listRecipientCandidates(
  authenticatedGet: AuthenticatedGet,
  options: {
    status: RecipientDocumentStatus
    limit: number
    cursor?: RecipientCandidateCursor | null
  },
): Promise<RecipientCandidatePage> {
  const query = new URLSearchParams({
    status: options.status,
    limit: String(options.limit),
  })
  if (options.cursor != null) {
    query.set('before_display_name', options.cursor.display_name)
    query.set('before_client_id', options.cursor.client_id)
  }

  const response = await authenticatedGet<RecipientCandidateListResponse>(
    `/email-recipient-candidates?${query.toString()}`,
  )
  return { items: response.items, nextCursor: response.next_cursor }
}

export function getEmailSenderSettings(
  authenticatedGet: AuthenticatedGet,
): Promise<EmailSenderSettings> {
  return authenticatedGet<EmailSenderSettings>('/email-sender-settings')
}

export function saveEmailSenderSettings(
  authenticatedRequest: AuthenticatedRequest,
  payload: EmailSenderSettings,
): Promise<EmailSenderSettings> {
  return authenticatedRequest<EmailSenderSettings>('/email-sender-settings', {
    method: 'PUT',
    body: payload,
  })
}

export function sendEmailBatch(
  authenticatedRequest: AuthenticatedRequest,
  payload: {
    template_id: string
    client_ids: string[]
    credential: string | null
    confirm_repeat: boolean
  },
): Promise<EmailDispatch[]> {
  return authenticatedRequest<EmailDispatch[]>('/email-dispatches', {
    method: 'POST',
    body: payload,
  })
}

export async function listEmailDispatches(
  authenticatedGet: AuthenticatedGet,
): Promise<EmailDispatch[]> {
  const response = await authenticatedGet<{ items: EmailDispatch[] }>(
    '/email-dispatches?limit=50',
  )
  return response.items
}

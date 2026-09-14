import { ApiError } from '../lib/apiClient'

type TemplateOperation = 'load' | 'save' | 'delete'

export function describeTemplateFailure(
  error: unknown,
  operation: TemplateOperation,
): string {
  if (!(error instanceof ApiError)) {
    return 'Não foi possível falar com o serviço local do CRM. Verifique se ele está em execução e tente novamente.'
  }

  if (error.status === 401) {
    return 'Sua sessão expirou. Entre novamente para continuar.'
  }
  if (error.status === 404) {
    return 'Este modelo não existe mais. Atualize a lista e tente novamente.'
  }
  if (error.status === 422) {
    return 'Revise o nome, o assunto e o conteúdo. Todos são obrigatórios e devem respeitar os limites indicados.'
  }

  if (operation === 'load') {
    return 'Não foi possível consultar os modelos agora. Tente novamente.'
  }
  if (operation === 'delete') {
    return 'Não foi possível remover o modelo. Nada foi alterado; tente novamente.'
  }
  return 'Não foi possível salvar o modelo. Nada foi alterado; tente novamente.'
}

export function describeCandidateFailure(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return 'Não foi possível falar com o serviço local do CRM. Verifique se ele está em execução e tente novamente.'
  }
  if (error.status === 401) {
    return 'Sua sessão expirou. Entre novamente para consultar os clientes.'
  }
  return 'Não foi possível consultar os clientes com esta situação documental agora.'
}

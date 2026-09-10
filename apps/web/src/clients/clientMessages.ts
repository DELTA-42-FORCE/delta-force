import { ApiError } from '../lib/apiClient'

/**
 * Traduz a falha da geração da ficha cadastral em PDF (#34) numa frase clara
 * para o proprietário. A ausência de campos opcionais nunca é erro: o PDF é
 * gerado com o que houver, então aqui só tratamos sessão, acesso e falhas reais.
 */
export function describeProfileExportFailure(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return 'Não foi possível falar com o serviço local do CRM. Verifique se ele está em execução e tente de novo.'
  }

  switch (error.status) {
    case 401:
      return 'Sua sessão expirou. Entre novamente para gerar a ficha.'
    case 403:
      return 'Seu acesso a esta pasta de cliente foi negado.'
    case 404:
      return 'Esta pasta de cliente não existe mais. Atualize a lista e tente de novo.'
    default:
      return 'Não foi possível gerar a ficha cadastral agora. Tente novamente.'
  }
}

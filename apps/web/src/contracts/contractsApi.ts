import type {
  AuthenticatedGet,
  AuthenticatedRequest,
} from '../clients/clientsApi'

export type ContractStatus = 'active' | 'paid' | 'cancelled'

export interface ContractInstallment {
  id: string
  number: number
  amount_cents: number
  due_date: string
  paid_on: string | null
}

export interface ClientContract {
  id: string
  client_folder_id: string
  total_amount_cents: number
  deposit_amount_cents: number
  balance_amount_cents: number
  installment_count: number
  signal_paid_on: string
  status: ContractStatus
  is_overdue: boolean
  cancelled_at: string | null
  installments: ContractInstallment[]
  created_at: string
  updated_at: string
}

export interface CreateContractInput {
  total_amount: string
  installment_count: number
  signal_paid_on: string
}

export function listClientContracts(
  authenticatedGet: AuthenticatedGet,
  clientId: string,
): Promise<ClientContract[]> {
  return authenticatedGet<ClientContract[]>(`/clients/${clientId}/contracts`)
}

export function createClientContract(
  authenticatedRequest: AuthenticatedRequest,
  clientId: string,
  input: CreateContractInput,
): Promise<ClientContract> {
  return authenticatedRequest<ClientContract>(
    `/clients/${clientId}/contracts`,
    {
      method: 'POST',
      body: input,
    },
  )
}

export function recordInstallmentPayment(
  authenticatedRequest: AuthenticatedRequest,
  options: {
    clientId: string
    contractId: string
    installmentId: string
    paidOn: string
  },
): Promise<ClientContract> {
  return authenticatedRequest<ClientContract>(
    `/clients/${options.clientId}/contracts/${options.contractId}/installments/${options.installmentId}/payments`,
    { method: 'POST', body: { paid_on: options.paidOn } },
  )
}

export function cancelClientContract(
  authenticatedRequest: AuthenticatedRequest,
  clientId: string,
  contractId: string,
): Promise<ClientContract> {
  return authenticatedRequest<ClientContract>(
    `/clients/${clientId}/contracts/${contractId}/cancel`,
    { method: 'POST' },
  )
}

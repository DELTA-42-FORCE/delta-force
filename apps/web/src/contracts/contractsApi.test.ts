import { describe, expect, it, vi } from 'vitest'

import {
  cancelClientContract,
  createClientContract,
  listClientContracts,
  recordInstallmentPayment,
} from './contractsApi'

const CLIENT_ID = '00000000-0000-0000-0000-000000000029'
const CONTRACT_ID = '00000000-0000-0000-0000-000000000030'
const INSTALLMENT_ID = '00000000-0000-0000-0000-000000000031'

describe('contracts API', () => {
  it('uses authenticated nested client routes', async () => {
    const authenticatedGet = vi.fn().mockResolvedValue([])
    const authenticatedRequest = vi.fn().mockResolvedValue({})

    await listClientContracts(authenticatedGet, CLIENT_ID)
    await createClientContract(authenticatedRequest, CLIENT_ID, {
      total_amount: '10000.03',
      installment_count: 3,
      signal_paid_on: '2026-09-01',
    })
    await recordInstallmentPayment(authenticatedRequest, {
      clientId: CLIENT_ID,
      contractId: CONTRACT_ID,
      installmentId: INSTALLMENT_ID,
      paidOn: '2026-09-19',
    })
    await cancelClientContract(authenticatedRequest, CLIENT_ID, CONTRACT_ID)

    expect(authenticatedGet).toHaveBeenCalledWith(
      `/clients/${CLIENT_ID}/contracts`,
    )
    expect(authenticatedRequest).toHaveBeenNthCalledWith(
      1,
      `/clients/${CLIENT_ID}/contracts`,
      {
        method: 'POST',
        body: {
          total_amount: '10000.03',
          installment_count: 3,
          signal_paid_on: '2026-09-01',
        },
      },
    )
    expect(authenticatedRequest).toHaveBeenNthCalledWith(
      2,
      `/clients/${CLIENT_ID}/contracts/${CONTRACT_ID}/installments/${INSTALLMENT_ID}/payments`,
      { method: 'POST', body: { paid_on: '2026-09-19' } },
    )
    expect(authenticatedRequest).toHaveBeenNthCalledWith(
      3,
      `/clients/${CLIENT_ID}/contracts/${CONTRACT_ID}/cancel`,
      { method: 'POST' },
    )
  })
})

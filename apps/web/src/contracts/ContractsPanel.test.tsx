import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ClientFolder } from '../clients/clientsApi'
import { ContractsPanel } from './ContractsPanel'
import type { ClientContract } from './contractsApi'

const folder: ClientFolder = {
  id: '00000000-0000-0000-0000-000000000029',
  display_name: 'Cliente Sintético',
  profile_data: {},
  created_at: '2026-09-01T00:00:00Z',
  updated_at: '2026-09-01T00:00:00Z',
}

function contract(status: ClientContract['status'] = 'active'): ClientContract {
  const paidOn = status === 'paid' ? '2026-09-10' : null
  return {
    id: '00000000-0000-0000-0000-000000000030',
    client_folder_id: folder.id,
    total_amount_cents: 1_200_003,
    deposit_amount_cents: 200_000,
    balance_amount_cents: 1_000_003,
    installment_count: 1,
    signal_paid_on: '2026-08-10',
    status,
    is_overdue: false,
    cancelled_at: status === 'cancelled' ? '2026-09-19T12:00:00Z' : null,
    installments: [
      {
        id: '00000000-0000-0000-0000-000000000031',
        number: 1,
        amount_cents: 1_000_003,
        due_date: '2026-09-10',
        paid_on: paidOn,
      },
    ],
    created_at: '2026-08-10T12:00:00Z',
    updated_at: '2026-08-10T12:00:00Z',
  }
}

afterEach(cleanup)

describe('ContractsPanel', () => {
  it('shows the exact schedule and records the final payment', async () => {
    const active = contract()
    const paid = contract('paid')
    const recordPayment = vi.fn().mockResolvedValue(paid)
    const user = userEvent.setup()

    render(
      <ContractsPanel
        folder={folder}
        loadContracts={() => Promise.resolve([active])}
        createContract={vi.fn()}
        recordPayment={recordPayment}
        cancelContract={vi.fn()}
        onBack={vi.fn()}
      />,
    )

    expect(await screen.findByText('R$ 12.000,03')).toBeVisible()
    expect(screen.getByText(/R\$ 10\.000,03 · vence/)).toBeVisible()
    await user.clear(screen.getByLabelText('Pagamento da parcela 1'))
    await user.type(
      screen.getByLabelText('Pagamento da parcela 1'),
      '2026-09-10',
    )
    await user.click(
      screen.getByRole('button', { name: 'Registrar pagamento' }),
    )

    await waitFor(() =>
      expect(recordPayment).toHaveBeenCalledWith(
        active,
        active.installments[0],
        '2026-09-10',
      ),
    )
    expect(await screen.findByText('Quitado')).toBeVisible()
    expect(screen.getByText('Pago em 10/09/2026')).toBeVisible()
  })

  it('creates a contract with a decimal string instead of a float', async () => {
    const createContract = vi.fn().mockResolvedValue(contract())
    const user = userEvent.setup()
    render(
      <ContractsPanel
        folder={folder}
        loadContracts={() => Promise.resolve([])}
        createContract={createContract}
        recordPayment={vi.fn()}
        cancelContract={vi.fn()}
        onBack={vi.fn()}
      />,
    )

    await screen.findByText('Nenhum contrato cadastrado para este cliente.')
    await user.type(screen.getByLabelText('Valor total'), '12000,03')
    await user.type(screen.getByLabelText('Quantidade de parcelas'), '3')
    await user.type(
      screen.getByLabelText('Data do pagamento do sinal'),
      '2026-09-01',
    )
    await user.click(screen.getByRole('button', { name: 'Cadastrar contrato' }))

    await waitFor(() =>
      expect(createContract).toHaveBeenCalledWith({
        total_amount: '12000.03',
        installment_count: 3,
        signal_paid_on: '2026-09-01',
      }),
    )
    expect(
      await screen.findByText('Contrato cadastrado com sucesso.'),
    ).toBeVisible()
  })

  it('requires a second action before cancelling an active contract', async () => {
    const active = contract()
    const cancelled = contract('cancelled')
    const cancelContract = vi.fn().mockResolvedValue(cancelled)
    const user = userEvent.setup()
    render(
      <ContractsPanel
        folder={folder}
        loadContracts={() => Promise.resolve([active])}
        createContract={vi.fn()}
        recordPayment={vi.fn()}
        cancelContract={cancelContract}
        onBack={vi.fn()}
      />,
    )

    await user.click(
      await screen.findByRole('button', { name: 'Cancelar contrato' }),
    )
    expect(cancelContract).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Sim, cancelar' }))

    await waitFor(() => expect(cancelContract).toHaveBeenCalledWith(active))
    expect(await screen.findByText('Cancelado')).toBeVisible()
  })
})

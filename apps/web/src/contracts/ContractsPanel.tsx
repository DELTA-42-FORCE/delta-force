import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'

import type { ClientFolder } from '../clients/clientsApi'
import type {
  ClientContract,
  ContractInstallment,
  CreateContractInput,
} from './contractsApi'

interface ContractsPanelProps {
  folder: ClientFolder
  loadContracts: () => Promise<ClientContract[]>
  createContract: (input: CreateContractInput) => Promise<ClientContract>
  recordPayment: (
    contract: ClientContract,
    installment: ContractInstallment,
    paidOn: string,
  ) => Promise<ClientContract>
  cancelContract: (contract: ClientContract) => Promise<ClientContract>
  onBack: () => void
}

const money = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

function formatMoney(cents: number): string {
  return money.format(cents / 100)
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('pt-BR', { timeZone: 'UTC' }).format(
    new Date(`${value}T00:00:00Z`),
  )
}

function today(): string {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

const STATUS_LABELS = {
  active: 'Ativo',
  paid: 'Quitado',
  cancelled: 'Cancelado',
} as const

export function ContractsPanel({
  folder,
  loadContracts,
  createContract,
  recordPayment,
  cancelContract,
  onBack,
}: ContractsPanelProps) {
  const [contracts, setContracts] = useState<ClientContract[]>([])
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [loadSequence, setLoadSequence] = useState(0)
  const [totalAmount, setTotalAmount] = useState('')
  const [installmentCount, setInstallmentCount] = useState('')
  const [signalPaidOn, setSignalPaidOn] = useState('')
  const [formState, setFormState] = useState<'idle' | 'saving'>('idle')
  const [feedback, setFeedback] = useState<{
    kind: 'error' | 'success'
    message: string
  } | null>(null)
  const [paymentDates, setPaymentDates] = useState<Record<string, string>>({})
  const [updatingId, setUpdatingId] = useState<string | null>(null)
  const [cancelConfirmation, setCancelConfirmation] = useState<string | null>(
    null,
  )
  const initialRequestRef = useRef<Promise<ClientContract[]> | null>(null)

  useEffect(() => {
    let active = true
    const request = initialRequestRef.current ?? loadContracts()
    initialRequestRef.current = request
    void request
      .then((items) => {
        if (!active) return
        setContracts(items)
        setState('ready')
      })
      .catch(() => {
        if (active) setState('error')
      })
    return () => {
      active = false
    }
  }, [loadContracts, loadSequence])

  const reload = useCallback(() => {
    initialRequestRef.current = null
    setState('loading')
    setLoadSequence((current) => current + 1)
  }, [])

  function replaceContract(updated: ClientContract) {
    setContracts((current) =>
      current.map((contract) =>
        contract.id === updated.id ? updated : contract,
      ),
    )
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFeedback(null)
    setFormState('saving')
    try {
      const created = await createContract({
        total_amount: totalAmount.replace(',', '.'),
        installment_count: Number(installmentCount),
        signal_paid_on: signalPaidOn,
      })
      setContracts((current) => [created, ...current])
      setTotalAmount('')
      setInstallmentCount('')
      setSignalPaidOn('')
      setFeedback({
        kind: 'success',
        message: 'Contrato cadastrado com sucesso.',
      })
    } catch {
      setFeedback({
        kind: 'error',
        message: 'Não foi possível cadastrar o contrato. Revise os dados.',
      })
    } finally {
      setFormState('idle')
    }
  }

  async function handlePayment(
    contract: ClientContract,
    installment: ContractInstallment,
  ) {
    setFeedback(null)
    setUpdatingId(installment.id)
    try {
      const updated = await recordPayment(
        contract,
        installment,
        paymentDates[installment.id] ?? today(),
      )
      replaceContract(updated)
      setFeedback({ kind: 'success', message: 'Pagamento registrado.' })
    } catch {
      setFeedback({
        kind: 'error',
        message: 'Não foi possível registrar o pagamento.',
      })
    } finally {
      setUpdatingId(null)
    }
  }

  async function handleCancel(contract: ClientContract) {
    setFeedback(null)
    setUpdatingId(contract.id)
    try {
      replaceContract(await cancelContract(contract))
      setCancelConfirmation(null)
      setFeedback({ kind: 'success', message: 'Contrato cancelado.' })
    } catch {
      setFeedback({
        kind: 'error',
        message: 'Não foi possível cancelar o contrato.',
      })
    } finally {
      setUpdatingId(null)
    }
  }

  return (
    <section className="contracts-panel" aria-labelledby="contracts-title">
      <div className="clients-page__heading">
        <div>
          <p className="eyebrow">Contratos</p>
          <h1 id="contracts-title">{folder.display_name}</h1>
          <p>Sinal fixo de R$ 2.000,00 e saldo dividido em parcelas mensais.</p>
        </div>
        <button
          className="secondary-button compact-button"
          type="button"
          onClick={onBack}
        >
          Voltar
        </button>
      </div>

      <form
        className="contract-form"
        onSubmit={(event) => void handleCreate(event)}
      >
        <div>
          <label htmlFor="contract-total">Valor total</label>
          <input
            id="contract-total"
            inputMode="decimal"
            placeholder="Ex.: 10000,00"
            required
            value={totalAmount}
            onChange={(event) => setTotalAmount(event.target.value)}
          />
        </div>
        <div>
          <label htmlFor="contract-installments">Quantidade de parcelas</label>
          <input
            id="contract-installments"
            type="number"
            min="1"
            max="600"
            required
            value={installmentCount}
            onChange={(event) => setInstallmentCount(event.target.value)}
          />
        </div>
        <div>
          <label htmlFor="contract-signal-date">
            Data do pagamento do sinal
          </label>
          <input
            id="contract-signal-date"
            type="date"
            max={today()}
            required
            value={signalPaidOn}
            onChange={(event) => setSignalPaidOn(event.target.value)}
          />
        </div>
        <button
          className="primary-button compact-button"
          type="submit"
          disabled={formState === 'saving'}
        >
          {formState === 'saving' ? 'Cadastrando…' : 'Cadastrar contrato'}
        </button>
      </form>

      {feedback !== null && (
        <p
          className={`feedback feedback--${feedback.kind}`}
          role={feedback.kind === 'error' ? 'alert' : 'status'}
        >
          {feedback.message}
        </p>
      )}

      {state === 'loading' && (
        <div className="activity-state" aria-busy="true">
          <span className="loader" aria-hidden="true" />
          <p>Carregando contratos…</p>
        </div>
      )}
      {state === 'error' && (
        <div className="activity-state">
          <p role="alert">Não foi possível consultar os contratos.</p>
          <button className="secondary-button" type="button" onClick={reload}>
            Tentar novamente
          </button>
        </div>
      )}
      {state === 'ready' && contracts.length === 0 && (
        <div className="activity-state">
          <p>Nenhum contrato cadastrado para este cliente.</p>
        </div>
      )}
      {state === 'ready' && contracts.length > 0 && (
        <div className="contract-list">
          {contracts.map((contract) => (
            <article className="contract-card" key={contract.id}>
              <header>
                <div>
                  <strong>{formatMoney(contract.total_amount_cents)}</strong>
                  <small>
                    Sinal {formatMoney(contract.deposit_amount_cents)} · saldo{' '}
                    {formatMoney(contract.balance_amount_cents)}
                  </small>
                </div>
                <span
                  className={`contract-status contract-status--${
                    contract.is_overdue ? 'overdue' : contract.status
                  }`}
                >
                  {contract.is_overdue
                    ? 'Em atraso'
                    : STATUS_LABELS[contract.status]}
                </span>
              </header>
              <p className="contract-signal">
                Sinal pago em {formatDate(contract.signal_paid_on)}
              </p>
              <div className="contract-installments">
                {contract.installments.map((installment) => (
                  <div className="contract-installment" key={installment.id}>
                    <span>
                      <strong>Parcela {installment.number}</strong>
                      <small>
                        {formatMoney(installment.amount_cents)} · vence{' '}
                        {formatDate(installment.due_date)}
                      </small>
                    </span>
                    {installment.paid_on !== null ? (
                      <span className="payment-recorded">
                        Pago em {formatDate(installment.paid_on)}
                      </span>
                    ) : contract.status === 'active' ? (
                      <span className="payment-action">
                        <label>
                          <span className="sr-only">
                            Pagamento da parcela {installment.number}
                          </span>
                          <input
                            aria-label={`Pagamento da parcela ${installment.number}`}
                            type="date"
                            min={contract.signal_paid_on}
                            max={today()}
                            value={paymentDates[installment.id] ?? today()}
                            onChange={(event) =>
                              setPaymentDates((current) => ({
                                ...current,
                                [installment.id]: event.target.value,
                              }))
                            }
                          />
                        </label>
                        <button
                          className="text-button"
                          type="button"
                          disabled={updatingId !== null}
                          onClick={() =>
                            void handlePayment(contract, installment)
                          }
                        >
                          {updatingId === installment.id
                            ? 'Salvando…'
                            : 'Registrar pagamento'}
                        </button>
                      </span>
                    ) : (
                      <span className="payment-pending">Não pago</span>
                    )}
                  </div>
                ))}
              </div>
              {contract.status === 'active' && (
                <footer>
                  {cancelConfirmation === contract.id ? (
                    <span className="contract-cancel-confirmation">
                      <span>Confirmar cancelamento?</span>
                      <button
                        className="text-button text-button--danger"
                        type="button"
                        disabled={updatingId !== null}
                        onClick={() => void handleCancel(contract)}
                      >
                        Sim, cancelar
                      </button>
                      <button
                        className="text-button"
                        type="button"
                        onClick={() => setCancelConfirmation(null)}
                      >
                        Voltar
                      </button>
                    </span>
                  ) : (
                    <button
                      className="text-button text-button--danger"
                      type="button"
                      onClick={() => setCancelConfirmation(contract.id)}
                    >
                      Cancelar contrato
                    </button>
                  )}
                </footer>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

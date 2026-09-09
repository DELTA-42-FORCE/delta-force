import { useCallback, useState } from 'react'

import {
  describeImportFailure,
  describeImportOutcome,
  describeImportStatus,
  describeSummaryKey,
} from './importMessages'
import type { LegacyImportPreview, LegacyImportResult } from './importsApi'

/**
 * Fluxo web da importação do acervo legado (#45).
 *
 * O proprietário informa a pasta de origem, executa uma prévia sem escrita,
 * revisa o que seria importado e só então confirma a importação. Trocar a pasta
 * depois da prévia zera o ensaio: a confirmação sempre corresponde ao que está
 * na tela. A origem nunca é alterada — o servidor apenas copia os elegíveis.
 */

interface LegacyImportPanelProps {
  previewImport: (sourcePath: string) => Promise<LegacyImportPreview>
  runImport: (sourcePath: string) => Promise<LegacyImportResult>
  onBack: () => void
}

type Phase = 'idle' | 'previewing' | 'previewed' | 'importing' | 'done'

const PREVIEW_KEY_ORDER = [
  'matched',
  'client_not_found',
  'client_ambiguous',
  'unsupported_format',
  'unreadable',
  'total',
]

const RESULT_KEY_ORDER = [
  'imported',
  'duplicate',
  'skipped',
  'unsupported_format',
  'unreadable',
  'insufficient_space',
  'failed',
  'total',
]

function describeMediaType(mediaType: string | null): string {
  if (mediaType === 'application/pdf') return 'PDF'
  if (mediaType === 'image/jpeg') return 'JPEG'
  return '—'
}

function SummaryList({
  summary,
  order,
}: {
  summary: Record<string, number>
  order: string[]
}) {
  return (
    <dl className="import-summary">
      {order
        .filter((key) => key in summary)
        .map((key) => (
          <div key={key} className="import-summary__row">
            <dt>{describeSummaryKey(key)}</dt>
            <dd>{summary[key]}</dd>
          </div>
        ))}
    </dl>
  )
}

export function LegacyImportPanel({
  previewImport,
  runImport,
  onBack,
}: LegacyImportPanelProps) {
  const [sourcePath, setSourcePath] = useState('')
  const [phase, setPhase] = useState<Phase>('idle')
  const [preview, setPreview] = useState<LegacyImportPreview | null>(null)
  const [result, setResult] = useState<LegacyImportResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const resetReview = useCallback(() => {
    setPreview(null)
    setResult(null)
    setError(null)
    setPhase('idle')
  }, [])

  const handlePathChange = useCallback(
    (value: string) => {
      setSourcePath(value)
      // Uma prévia só vale para a pasta que a gerou; ao editar o caminho, o
      // ensaio e o relatório anteriores deixam de descrever a tela.
      if (preview !== null || result !== null || error !== null) {
        resetReview()
      }
    },
    [preview, result, error, resetReview],
  )

  const handlePreview = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault()
      const trimmed = sourcePath.trim()
      if (trimmed === '') return
      setError(null)
      setResult(null)
      setPhase('previewing')
      try {
        const next = await previewImport(trimmed)
        setPreview(next)
        setPhase('previewed')
      } catch (caught) {
        setError(describeImportFailure(caught))
        setPreview(null)
        setPhase('idle')
      }
    },
    [sourcePath, previewImport],
  )

  const handleImport = useCallback(async () => {
    if (preview === null) return
    setError(null)
    setPhase('importing')
    try {
      const next = await runImport(sourcePath.trim())
      setResult(next)
      setPhase('done')
    } catch (caught) {
      setError(describeImportFailure(caught))
      setPhase('previewed')
    }
  }, [preview, runImport, sourcePath])

  const importable = preview?.summary.matched ?? 0
  const busy = phase === 'previewing' || phase === 'importing'

  return (
    <section className="import-panel" aria-labelledby="import-title">
      <header className="section-heading">
        <div>
          <p className="eyebrow">Documentos</p>
          <h1 id="import-title">Importar acervo legado</h1>
          <p>
            Aponte a pasta com as pastas de clientes já existentes neste
            computador. A prévia não escreve nada e a importação apenas copia os
            arquivos elegíveis — a pasta de origem nunca é alterada nem apagada.
          </p>
        </div>
        <button className="secondary-button" type="button" onClick={onBack}>
          Voltar
        </button>
      </header>

      <form
        className="import-form"
        onSubmit={(event) => void handlePreview(event)}
      >
        <label htmlFor="import-source">Pasta de origem</label>
        <input
          id="import-source"
          type="text"
          value={sourcePath}
          onChange={(event) => handlePathChange(event.target.value)}
          placeholder="Ex.: C:\\Clientes"
          autoComplete="off"
          spellCheck={false}
        />
        <button
          className="primary-button"
          type="submit"
          disabled={sourcePath.trim() === '' || busy}
        >
          {phase === 'previewing' ? 'Analisando…' : 'Pré-visualizar'}
        </button>
      </form>

      {error !== null && (
        <p className="import-error" role="alert">
          {error}
        </p>
      )}

      {preview !== null && result === null && (
        <section
          className="import-review"
          aria-label="Prévia da importação"
          aria-busy={phase === 'importing'}
        >
          <h2>Prévia — nada foi importado ainda</h2>
          <SummaryList summary={preview.summary} order={PREVIEW_KEY_ORDER} />

          {preview.items.length === 0 ? (
            <p className="import-empty">
              Nenhum arquivo foi encontrado na pasta de origem informada.
            </p>
          ) : (
            <table className="import-table">
              <caption className="visually-hidden">
                Arquivos encontrados e a situação de cada um
              </caption>
              <thead>
                <tr>
                  <th scope="col">Arquivo</th>
                  <th scope="col">Pasta de cliente</th>
                  <th scope="col">Tipo</th>
                  <th scope="col">Situação</th>
                </tr>
              </thead>
              <tbody>
                {preview.items.map((item) => (
                  <tr key={item.relative_path}>
                    <td>{item.relative_path}</td>
                    <td>{item.client_folder_name ?? '—'}</td>
                    <td>{describeMediaType(item.media_type)}</td>
                    <td>{describeImportStatus(item.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div className="import-confirm">
            <p>
              {importable === 0
                ? 'Nenhum arquivo tem cliente identificado, então a importação não copiaria nada. Itens ambíguos ou sem cliente ficam de fora por segurança.'
                : `${importable} arquivo(s) com cliente identificado serão copiados. Os demais são apenas relatados, sem interromper os elegíveis.`}
            </p>
            <button
              className="primary-button"
              type="button"
              onClick={() => void handleImport()}
              disabled={importable === 0 || busy}
            >
              {phase === 'importing' ? 'Importando…' : 'Importar acervo'}
            </button>
          </div>
        </section>
      )}

      {result !== null && (
        <section className="import-result" aria-label="Relatório da importação">
          <h2>Importação concluída</h2>
          <p className="import-success">
            A operação foi registrada na auditoria. A pasta de origem permanece
            intacta.
          </p>
          <SummaryList summary={result.summary} order={RESULT_KEY_ORDER} />

          <table className="import-table">
            <caption className="visually-hidden">
              Desfecho de cada arquivo processado
            </caption>
            <thead>
              <tr>
                <th scope="col">Arquivo</th>
                <th scope="col">Pasta de cliente</th>
                <th scope="col">Desfecho</th>
              </tr>
            </thead>
            <tbody>
              {result.items.map((item) => (
                <tr key={item.relative_path}>
                  <td>{item.relative_path}</td>
                  <td>{item.client_folder_name ?? '—'}</td>
                  <td>{describeImportOutcome(item.outcome)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </section>
  )
}

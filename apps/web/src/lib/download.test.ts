import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DownloadedFile } from './apiClient'
import { saveDownloadedFile } from './download'

afterEach(() => {
  vi.restoreAllMocks()
})

function stubObjectUrl() {
  const createObjectURL = vi.fn(() => 'blob:fake')
  const revokeObjectURL = vi.fn()
  // jsdom não implementa a API de object URL usada no download.
  Object.assign(URL, { createObjectURL, revokeObjectURL })
  return { createObjectURL, revokeObjectURL }
}

describe('saveDownloadedFile', () => {
  it('downloads with the server-provided filename and revokes the URL', () => {
    const { createObjectURL, revokeObjectURL } = stubObjectUrl()
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {})

    const file: DownloadedFile = {
      blob: new Blob(['%PDF']),
      filename: 'ficha-cadastral-ana-souza.pdf',
    }
    saveDownloadedFile(file, 'fallback.pdf')

    expect(createObjectURL).toHaveBeenCalledWith(file.blob)
    expect(clickSpy).toHaveBeenCalledTimes(1)
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:fake')
  })

  it('falls back to the given name when the server sends none', () => {
    stubObjectUrl()
    let downloadName: string | null = null
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      downloadName = this.download
    })

    saveDownloadedFile(
      { blob: new Blob(['%PDF']), filename: null },
      'ficha.pdf',
    )

    expect(downloadName).toBe('ficha.pdf')
  })
})
